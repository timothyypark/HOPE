#include "hope_planner_cpp/v2_incoming_runtime.hpp"

namespace hope_planner_cpp {
namespace {
template<class Wire> void vector(Wire& wire, const Vec3& value) {
  wire.x = value.x(); wire.y = value.y(); wire.z = value.z();
}
std::int64_t steady_ns() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}
}
V2IncomingRuntime::V2IncomingRuntime(rclcpp::Node& node, const BallPhysics& physics,
                                   const TableParams& table, std::function<void()> wake,
                                   std::function<std::pair<std::uint64_t, bool>()> reference)
    : node_(node) {
  auto text = [&](const char* key, const char* fallback = "") {
    return node.declare_parameter<std::string>(std::string("v2_incoming.") + key, fallback);
  };
  if (text("output_mode", "shadow") != "shadow")
    throw std::invalid_argument("v2_incoming requires separately authorized deployment; use shadow");
  contract_.session = text("session_id");
  contract_.frame = text("frame_id");
  contract_.registration = text("calibration_id");
  contract_.clock_domain = text("clock_domain");
  contract_.clock_mapping = text("clock_mapping_id");
  contract_.ball = text("ball_id");
  const auto calibration = node.declare_parameter<std::int64_t>("v2_incoming.base_calibration_id", 0);
  const auto world = node.declare_parameter<std::int64_t>("v2_incoming.base_world_id", 0);
  if (calibration <= 0 || world <= 0)
    throw std::invalid_argument("v2_incoming requires explicit registered base calibration/world identities");
  base_calibration_ = calibration; base_world_ = world;
  producer_ = text("producer_id", "v2-incoming-planner");
  continuous_output_ = node.declare_parameter("v2_incoming.continuous_output", true);
  full_rate_hz_ = node.declare_parameter("v2_incoming.full_output_rate_hz", 50.);
  if (!std::isfinite(full_rate_hz_) || full_rate_hz_ < 0 || full_rate_hz_ > 300)
    throw std::invalid_argument("full_output_rate_hz must be in [0,300]; zero disables full output");
  ProbabilisticConfig config; config.physics = physics; config.table = table;
  owner_ = std::make_unique<V2IncomingCoordinator>(config, ShotSettings{}, contract_);
  compact_ = node.create_publisher<hope_msgs::msg::FlightPredictionV2>(
      std::string(prefix)+"prediction", rclcpp::QoS(1).reliable());
  full_ = node.create_publisher<hope_msgs::msg::FlightPredictionV2>(
      std::string(prefix)+"trajectory", rclcpp::QoS(1).best_effort());
  candidates_ = node.create_publisher<hope_msgs::msg::StrikeCandidateV1>(
      std::string(prefix)+"candidate", rclcpp::QoS(1).reliable());
  // Separate retained status stream prevents latest-value candidate traffic
  // from hiding a revocation of an earlier one-shot command.
  revocations_ = node.create_publisher<hope_msgs::msg::StrikeCandidateV1>(
      std::string(prefix)+"revocation", rclcpp::QoS(64).reliable().transient_local());
  if (std::string(compact_->get_topic_name()) != std::string(prefix)+"prediction" ||
      std::string(full_->get_topic_name()) != std::string(prefix)+"trajectory" ||
      std::string(candidates_->get_topic_name()) != std::string(prefix)+"candidate" ||
      std::string(revocations_->get_topic_name()) != std::string(prefix)+"revocation")
    throw std::invalid_argument("V2 incoming shadow outputs cannot be remapped");
  observations_ = node.create_subscription<hope_msgs::msg::BallObservationV2>(
      text("observation_topic", "/ball/observation_v2"), rclcpp::QoS(8).best_effort(),
      [this, wake](hope_msgs::msg::BallObservationV2::ConstSharedPtr message) {
        auto sample = decode_observation(*message);
        sample.receipt_steady_ns = steady_ns();
        sample.receipt_wall_ns = node_.now().nanoseconds();
        owner_->observe(sample, sample.receipt_wall_ns);
        latest_source_ns_.store(owner_->counters().latest_source_ns);
        if (pending_.exchange(true)) ++superseded_;
        wake();
      });
  expiry_ = node.create_wall_timer(std::chrono::milliseconds(5), [this, reference] {
    owner_->update_reference(reference);
    owner_->expire(node_.now().nanoseconds());
    flush_statuses();
  });
}

void V2IncomingRuntime::update_reference(
    const std::function<std::pair<std::uint64_t, bool>()>& update) {
  owner_->update_reference(update);
  pending_.store(true);
}

void V2IncomingRuntime::candidate(const V2StrikeCandidate& value,
                                const IncomingQuery* query, const FlightPrediction* prediction) {
  hope_msgs::msg::StrikeCandidateV1 wire;
  wire.session_id = contract_.session; wire.producer_id = producer_;
  wire.frame_id = contract_.frame; wire.calibration_id = contract_.registration;
  wire.clock_domain = contract_.clock_domain; wire.clock_mapping_id = contract_.clock_mapping;
  wire.ball_id = contract_.ball; wire.model_config_id = value.model_config_id;
  wire.home_epoch = value.plane.selection.epoch;
  wire.physical_shot_generation = value.token.generation;
  wire.context_revision = value.token.context_revision; wire.prediction_revision = value.revision;
  wire.semantic_epoch = value.semantic_epoch; wire.revokes_revision = value.revokes_revision;
  wire.command_sequence = value.command_sequence; wire.command_flight_id = value.command_flight_id;
  wire.source_time_ns = value.source_ns; wire.expires_at_ns = value.expires_ns;
  wire.physical_state_available = value.physical_state_available;
  wire.strike_contact_supported = value.strike_contact_supported;
  wire.command_eligible = value.command_eligible;
  wire.runner_commitment_state = "UNKNOWN";  // Shadow decoding is not engagement feedback.
  wire.status = name(value.status); wire.reason = value.reason;
  wire.plane_available = value.plane.snapshot.calibrated;
  wire.plane_tentative = value.plane.tentative;
  wire.plane_mode = static_cast<std::uint8_t>(value.plane.selection.mode);
  wire.plane_flight_id = value.plane.selection.flight;
  wire.plane_reference_x = value.plane.selection.reference_x;
  wire.plane_x = value.plane.snapshot.x_hit_m;
  wire.contact_time_std_s = value.contact_time_std_s;
  wire.uncertainty_provenance = value.uncertainty_provenance;
  wire.contact_covariance.fill(std::numeric_limits<double>::quiet_NaN());
  if (value.contact) {
    wire.contact_time_ns = value.contact->arrival_ns;
    vector(wire.contact_position, value.contact->contact.pre.position);
    vector(wire.contact_velocity, value.contact->contact.pre.velocity);
    for (int row=0; row<7; ++row) for (int col=0; col<7; ++col)
      wire.contact_covariance[row*7+col] = value.contact->covariance(row,col);
  }
  if (query && prediction) wire.event_evidence = encode_prediction(*prediction, query->pipeline.shot()).events;
  wire.published_at_ns = node_.now().nanoseconds();
  std::lock_guard<std::mutex> output_lock(output_mutex_);
  if (value.status == IncomingStatus::Revoked || value.status == IncomingStatus::Expired)
    revocations_->publish(wire);
  if (continuous_output_) candidates_->publish(wire);
}

void V2IncomingRuntime::flush_statuses() {
  const auto statuses = owner_->take_statuses();
  for (const auto& status : statuses) {
    candidate(status);
    if (!continuous_output_) continue;
    hope_msgs::msg::FlightPredictionV2 wire;
    wire.session_id = contract_.session; wire.producer_id = producer_;
    wire.frame_id = contract_.frame; wire.calibration_id = contract_.registration;
    wire.ball_id = contract_.ball; wire.clock_domain = contract_.clock_domain;
    wire.clock_mapping_id = contract_.clock_mapping;
    wire.model_config_id = wire.config_id = status.model_config_id;
    wire.shot_id = wire.shot_generation = status.token.generation;
    wire.context_revision = status.token.context_revision;
    wire.forecast_revision = status.revision;
    wire.forecast_status = name(status.status); wire.reason = status.reason;
    wire.prediction_reference_time_ns = status.source_ns;
    wire.expires_at_ns = status.expires_ns;
    wire.plane_x = status.plane.snapshot.x_hit_m;
    wire.plane_available = status.plane.snapshot.calibrated;
    wire.plane_revision = status.plane.snapshot.generation;
    wire.generated_at_ns = wire.published_at_ns = node_.now().nanoseconds();
    std::lock_guard<std::mutex> output_lock(output_mutex_);
    compact_->publish(wire);
  }
}

bool V2IncomingRuntime::forecast(IncomingQuery& query, IncomingEvaluation& result) {
  const auto metrics = owner_->counters();
  return owner_->publish(query, result, node_.now().nanoseconds(), [&](V2StrikeCandidate& value) {
    if (!continuous_output_) return true;
    auto wire = encode_prediction(result.forecast, query.pipeline.shot());
    wire.session_id = contract_.session; wire.producer_id = producer_;
    wire.config_id = value.model_config_id;
    wire.forecast_revision = value.revision;
    wire.input_count = metrics.offered;
    wire.superseded_count = superseded_.load();
    wire.generated_at_ns = node_.now().nanoseconds();
    wire.published_at_ns = wire.generated_at_ns;
    if (value.status == IncomingStatus::Revoked || value.status == IncomingStatus::Expired) {
      wire.target_valid = false; wire.forecast_status = name(value.status); wire.reason = value.reason;
    }
    auto points = std::move(wire.waypoints);
    {
      std::lock_guard<std::mutex> output_lock(output_mutex_);
      compact_->publish(wire);
      if (full_rate_hz_ > 0 && wire.prediction_reference_time_ns >= next_full_ns_) {
        wire.waypoints = std::move(points);
        wire.published_at_ns = node_.now().nanoseconds();
        full_->publish(wire);
        next_full_ns_ = wire.prediction_reference_time_ns + std::llround(1e9 / full_rate_hz_);
      }
    }
    candidate(value, &query, &result.forecast);
    return true;
  });
}

void V2IncomingRuntime::continuous(const IncomingPlane& plane) {
  if (!pending_.exchange(false)) return;
  const auto state = owner_->state();
  const bool frozen = selected_plane_ && selected_generation_ == state.generation &&
      selected_plane_->selection.epoch == plane.selection.epoch;
  auto query = owner_->continuous(frozen ? *selected_plane_ : plane);
  auto result = V2IncomingCoordinator::evaluate(query, node_.now().nanoseconds());
  flush_statuses();
  forecast(query, result);
}

StrikeTarget V2IncomingRuntime::packet(const TrajectorySnapshot& packet,
                                     const IncomingPlane& plane, BallState& state) {
  command_query_.reset(); command_evaluation_.reset();
  std::string reason;
  command_query_ = owner_->packet(packet, plane, node_.now().nanoseconds(), reason);
  if (!command_query_) { StrikeTarget rejected; rejected.reason = reason; return rejected; }
  selected_plane_ = plane;
  selected_generation_ = command_query_->pipeline.shot().generation();
  command_evaluation_ = V2IncomingCoordinator::evaluate(*command_query_, node_.now().nanoseconds());
  const auto& belief = command_evaluation_->forecast.belief;
  state.valid = belief.initialized;
  state.position = belief.mean.head<3>(); state.velocity = belief.mean.tail<3>();
  state.source_time_s = static_cast<double>(command_evaluation_->forecast.reference_ns) * 1e-9;
  state.sample_count = belief.observation_count;
  state.sample_span_s = belief.last_measurement_time_s - belief.first_measurement_time_s;
  state.reason = command_evaluation_->candidate.reason;
  return v2_strike_target(command_evaluation_->candidate, node_.now().nanoseconds());
}

bool V2IncomingRuntime::command(const std::function<bool(V2StrikeCandidate&)>& publication) {
  if (!command_query_ || !command_evaluation_) return false;
  const auto now = node_.now().nanoseconds();
  if (static_cast<long double>(command_evaluation_->candidate.expires_ns) - now < 5000000.L)
    return false;
  const bool published = owner_->publish(*command_query_, *command_evaluation_, now, publication);
  if (published) candidate(command_evaluation_->candidate, &*command_query_, &command_evaluation_->forecast);
  flush_statuses();
  return published;
}
}  // namespace hope_planner_cpp
