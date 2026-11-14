#include "hope_planner_cpp/v2_incoming_coordinator.hpp"
#include <gtest/gtest.h>

using namespace hope_planner_cpp;
namespace {
constexpr std::int64_t origin = 1800000000000000000LL;
IncomingSourceContract contract() {
  return {"session", "table", "fixture", "simulation", "clock", "ball"};
}
IncomingPlane plane() {
  PlaneSelection selected;
  selected.valid = true; selected.epoch = 7; selected.flight = 1;
  selected.reference_x = -.43; selected.plane_x = .15;
  return incoming_plane(selected, "table", "fixture", false);
}
struct Source {
  V2IncomingCoordinator owner{{}, {}, contract()};
  ModelState physical;
  std::vector<BallSample> samples;
  Source() { physical.position = Vec3(2.5, -.7, .32); physical.velocity = Vec3(-10, 0, -.5); }
  void next() {
    BallSample sample;
    sample.source_time_ns = origin + std::llround(samples.size() / 300. * 1e9);
    sample.sequence = samples.size() + 1; sample.position = physical.position;
    sample.frame_id = "table"; sample.calibration_id = "fixture";
    sample.clock_domain = "simulation"; sample.clock_mapping_id = "clock"; sample.ball_id = "ball";
    owner.observe(sample, sample.source_time_ns);
    samples.push_back(sample);
    EventGeometry geometry;
    advance_ball(physical, 1./300, {}, geometry);
  }
  void to(int count) { while (samples.size() < static_cast<std::size_t>(count)) next(); }
  std::int64_t now() const { return samples.back().source_time_ns; }
  TrajectorySnapshot packet(int count) {
    TrajectorySnapshot packet;
    packet.sample_count = count;
    std::copy(samples.begin(), samples.begin()+count, packet.samples.begin());
    packet.packet.present = true; packet.packet.session_id = "session";
    packet.packet.producer_instance_id = "packetizer"; packet.packet.payload_hash = "verified-by-ROS-callback";
    packet.packet.frame_id = "table"; packet.packet.flight_sequence = 1;
    packet.packet.trajectory_epoch = 91;  // Deliberately unrelated to V2 generation.
    packet.one_shot.commit_due = true;
    return packet;
  }
};
TEST(V2IncomingCoordinator, PacketAndContinuousShareActualCutoffWithoutFutureMeasurements) {
  Source source; source.to(31);
  auto continuous = source.owner.continuous(plane());
  auto expected = V2IncomingCoordinator::evaluate(continuous, source.now());
  ASSERT_TRUE(expected.candidate.command_eligible) << expected.candidate.reason;
  const auto packet = source.packet(31);
  source.to(34);
  std::string reason;
  auto command = source.owner.packet(packet, plane(), source.now(), reason);
  ASSERT_TRUE(command) << reason;
  auto actual = V2IncomingCoordinator::evaluate(*command, source.now());
  EXPECT_EQ(actual.forecast.reference_ns, expected.forecast.reference_ns);
  EXPECT_EQ(actual.forecast.belief.mean, expected.forecast.belief.mean);
  EXPECT_EQ(actual.forecast.belief.covariance, expected.forecast.belief.covariance);
  EXPECT_EQ(actual.candidate.token.generation, expected.candidate.token.generation);
  EXPECT_NE(actual.candidate.token.generation, packet.packet.trajectory_epoch);
  EXPECT_EQ(actual.candidate.contact->arrival_ns, expected.candidate.contact->arrival_ns);
}
TEST(V2IncomingCoordinator, PacketMismatchAndDuplicateCannotCreateCommandOpportunity) {
  Source source; source.to(31);
  auto packet = source.packet(31); packet.samples[15].position.z() += .001;
  std::string reason;
  EXPECT_FALSE(source.owner.packet(packet, plane(), source.now(), reason));
  EXPECT_EQ(reason, "PACKET_OBSERVATION_PREFIX_MISMATCH");
  packet = source.packet(31);
  ASSERT_TRUE(source.owner.packet(packet, plane(), source.now(), reason));
  EXPECT_FALSE(source.owner.packet(packet, plane(), source.now(), reason));
  packet.packet.flight_sequence = 2;
  EXPECT_FALSE(source.owner.packet(packet, plane(), source.now(), reason));
  EXPECT_EQ(reason, "PHYSICAL_FLIGHT_ALREADY_CLAIMED");
  packet.packet.producer_instance_id = "another-producer";
  EXPECT_FALSE(source.owner.packet(packet, plane(), source.now(), reason));
}
TEST(V2IncomingCoordinator, LegacyQuaternionPlaceholderCannotQualifyUnknownSpin) {
  Source source; source.to(31);
  auto packet = source.packet(31);
  for (std::size_t i=0; i<packet.sample_count; ++i) {
    packet.samples[i].orientation_valid = true;
    packet.samples[i].orientation = Eigen::Quaterniond::Identity();
  }
  std::string reason;
  auto query = source.owner.packet(packet, plane(), source.now(), reason);
  ASSERT_TRUE(query) << reason;
  EXPECT_FALSE(query->pipeline.shot().spin().usable());
  auto result = V2IncomingCoordinator::evaluate(*query, source.now());
  EXPECT_FALSE(result.forecast.belief.effective_spin.usable());
}
TEST(V2IncomingCoordinator, HealthyNewObservationDoesNotAutomaticallyRetirePendingWork) {
  Source source; source.to(31);
  std::string reason;
  auto query = source.owner.packet(source.packet(31), plane(), source.now(), reason);
  ASSERT_TRUE(query) << reason;
  auto result = V2IncomingCoordinator::evaluate(*query, source.now());
  source.next();
  int published = 0;
  EXPECT_TRUE(source.owner.publish(*query, result, source.now(), [&](auto&) { ++published; return true; }));
  EXPECT_EQ(published, 1);
  EXPECT_FALSE(source.owner.publish(*query, result, source.now(), [&](auto&) { ++published; return true; }));
  EXPECT_EQ(published, 1);
  auto continuous = source.owner.continuous(plane());
  auto after = V2IncomingCoordinator::evaluate(continuous, source.now());
  EXPECT_TRUE(source.owner.publish(continuous, after, source.now(), [&](auto& candidate) {
    EXPECT_TRUE(candidate.strike_contact_supported);
    EXPECT_FALSE(candidate.command_eligible);
    return true;
  }));
  EXPECT_EQ(source.owner.counters().commands, 1u);
  EXPECT_GT(after.forecast.reference_ns, result.forecast.reference_ns);
  source.to(44);
  source.owner.expire(source.now());
  EXPECT_TRUE(source.owner.take_statuses().empty());
  EXPECT_EQ(result.candidate.source_ns, origin + 100000000);
}
TEST(V2IncomingCoordinator, RevocationRetiresWorkerAndPublishesCorrectPriorIdentity) {
  Source source; source.to(31);
  auto first = source.owner.continuous(plane());
  auto result = V2IncomingCoordinator::evaluate(first, source.now());
  ASSERT_TRUE(source.owner.publish(first, result, source.now(), [](auto&) { return true; }));
  auto delayed = source.owner.continuous(plane());
  auto delayed_result = V2IncomingCoordinator::evaluate(delayed, source.now());
  source.owner.revoke("HOME_CHANGED");
  bool called = false;
  EXPECT_FALSE(source.owner.publish(delayed, delayed_result, source.now(), [&](auto&) { called=true; return true; }));
  EXPECT_FALSE(called);
  auto statuses = source.owner.take_statuses();
  ASSERT_EQ(statuses.size(), 1u);
  EXPECT_EQ(statuses[0].status, IncomingStatus::Revoked);
  EXPECT_EQ(statuses[0].token.generation, result.candidate.token.generation);
  EXPECT_EQ(statuses[0].plane.selection.epoch, 7u);
  EXPECT_GT(statuses[0].revision, delayed.revision);
  EXPECT_FALSE(statuses[0].command_eligible);
}
TEST(V2IncomingCoordinator, ExpiryAndSourceFaultBlockDelayedPublication) {
  Source source; source.to(31);
  auto query = source.owner.continuous(plane());
  auto result = V2IncomingCoordinator::evaluate(query, source.now());
  EXPECT_FALSE(source.owner.publish(query, result, source.now()+30000001, [](auto&) { return true; }));
  auto bad = source.samples.back(); bad.source_time_ns++; bad.clock_mapping_valid = false;
  source.owner.observe(bad, bad.source_time_ns);
  EXPECT_FALSE(source.owner.publish(query, result, bad.source_time_ns, [](auto&) { return true; }));
}
TEST(V2IncomingCoordinator, HomeUpdateRejectsStalePlaneEvenWhenQueryStartsAfterUpdate) {
  Source source; source.to(31);
  EXPECT_TRUE(source.owner.update_reference([] { return std::make_pair(7u, true); }));
  auto query = source.owner.continuous(plane());
  auto result = V2IncomingCoordinator::evaluate(query, source.now());
  EXPECT_FALSE(source.owner.update_reference([] { return std::make_pair(7u, true); }));
  ASSERT_TRUE(source.owner.publish(query, result, source.now(), [](auto&) { return true; }));
  source.owner.update_reference([] { return std::make_pair(8u, true); });
  auto stale_plane = source.owner.continuous(plane());
  auto stale_result = V2IncomingCoordinator::evaluate(stale_plane, source.now());
  EXPECT_FALSE(source.owner.publish(stale_plane, stale_result, source.now(), [](auto&) { return true; }));
  const auto statuses = source.owner.take_statuses();
  ASSERT_EQ(statuses.size(), 1u);
  EXPECT_EQ(statuses[0].revokes_revision, result.candidate.revision);
  EXPECT_EQ(statuses[0].plane.selection.epoch, 7u);
}
TEST(V2IncomingCoordinator, HistoryAndCheckpointsStayBounded) {
  Source source; source.to(700);
  EXPECT_LE(source.owner.counters().history, contract().history_capacity);
  EXPECT_LE(source.owner.counters().checkpoints, contract().checkpoint_capacity);
}
TEST(V2IncomingCoordinator, ExpiryIsExplicitWithoutAnEarlierSupportedCandidate) {
  Source source; source.to(8);
  source.owner.continuous(plane());
  source.owner.expire(source.now()+30000001);
  const auto statuses = source.owner.take_statuses();
  ASSERT_FALSE(statuses.empty());
  EXPECT_EQ(statuses.back().status, IncomingStatus::Expired);
  EXPECT_EQ(statuses.back().source_ns, source.now());
  EXPECT_FALSE(statuses.back().command_eligible);
  source.owner.expire(source.now()+40000000);
  EXPECT_TRUE(source.owner.take_statuses().empty());
}
TEST(V2IncomingCoordinator, MissingReferencePreservesPhysicalEvidenceWithoutCommandAuthority) {
  Source source; source.to(31);
  source.owner.update_reference([] { return std::make_pair(7u, false); });
  auto query = source.owner.continuous(plane());
  auto result = V2IncomingCoordinator::evaluate(query, source.now());
  ASSERT_TRUE(result.candidate.strike_contact_supported);
  EXPECT_TRUE(source.owner.publish(query, result, source.now(), [](const auto& candidate) {
    EXPECT_TRUE(candidate.physical_state_available);
    EXPECT_TRUE(candidate.strike_contact_supported);
    EXPECT_FALSE(candidate.command_eligible);
    EXPECT_EQ(candidate.reason, "REFERENCE_UNAVAILABLE");
    return true;
  }));
}
TEST(V2IncomingCoordinator, ConfirmedSecondBounceRetiresPreviouslySupportedWorker) {
  Source source;
  while (source.samples.size() < 100 && source.owner.state().events.empty()) source.next();
  while (source.samples.size() < 100) {
    const auto state = source.owner.state();
    const auto contacts = std::count_if(state.events.begin(), state.events.end(), [](const auto& event) {
      return event.kind == PhysicalEventKind::TABLE && event.status == EventStatus::CONFIRMED;
    });
    if (contacts == 1) break;
    source.next();
  }
  auto selected = plane(); selected.selection.plane_x = -.2;
  selected = incoming_plane(selected.selection, "table", "fixture", false);
  std::string reason;
  auto command = source.owner.packet(source.packet(source.samples.size()), selected, source.now(), reason);
  ASSERT_TRUE(command) << reason;
  auto delayed = std::move(*command);
  auto result = V2IncomingCoordinator::evaluate(delayed, source.now());
  ASSERT_TRUE(result.candidate.strike_contact_supported) << result.candidate.reason;
  const auto generation = source.owner.state().generation;
  // A new observed downward/upward surface bracket contradicts the old
  // forecast's single-bounce future. It is consumed by the production detector.
  for (double height : {.06, .04, .02, .04, .06, .08}) {
    source.physical.position.z() = height;
    source.next();
  }
  const auto state = source.owner.state();
  ASSERT_EQ(state.generation, generation);
  ASSERT_EQ(std::count_if(state.events.begin(), state.events.end(), [](const auto& event) {
    return event.kind == PhysicalEventKind::TABLE && event.status == EventStatus::CONFIRMED;
  }), 2);
  ASSERT_LT(source.now(), result.candidate.expires_ns);
  ASSERT_LT(source.now(), result.candidate.contact->arrival_ns);
  bool called = false;
  EXPECT_FALSE(source.owner.publish(delayed, result, source.now(), [&](auto&) { called=true; return true; }));
  EXPECT_FALSE(called);
}
}  // namespace

TEST(V2IncomingDecisionObserver, InstrumentationPreservesForecastAndKeepsRepeatedTimestampTransitions) {
  IncomingSourceContract ids{"session", "table", "fixture", "simulation", "clock", "ball"};
  V2IncomingCoordinator plain({}, {}, ids), traced({}, {}, ids);
  std::vector<IncomingDecision> rows;
  traced.set_decision_observer([&](const auto& row){rows.push_back(row);});
  for(int i=0;i<40;++i) {
    BallSample s;s.source_time_ns=1800000000000000000LL+i*3333333LL;s.sequence=i+1;
    const double t=i/300.;s.position=Vec3(2.5-5*t,-.7,.5-.5*t-4.905*t*t);
    s.frame_id="table";s.calibration_id="fixture";s.clock_domain="simulation";s.clock_mapping_id="clock";s.ball_id="ball";
    EXPECT_EQ(plain.observe(s,s.source_time_ns),traced.observe(s,s.source_time_ns));
    plain.expire(s.source_time_ns);traced.expire(s.source_time_ns);
  }
  ASSERT_EQ(rows.size(),160u);
  for(std::size_t i=0;i<rows.size();++i)EXPECT_EQ(rows[i].sequence,i+1);
  EXPECT_EQ(rows[0].source_ns,rows[3].source_ns);
  EXPECT_STREQ(rows[0].phase.data(),"before_observe");
  EXPECT_STREQ(rows[3].phase.data(),"after_expire");
  EXPECT_EQ(plain.state().generation,traced.state().generation);
  EXPECT_EQ(plain.state().state,traced.state().state);
  PlaneSelection selection;selection.valid=true;selection.epoch=1;selection.flight=1;selection.plane_x=.15;selection.reference_x=-.43;
  auto p=incoming_plane(selection,"table","fixture",false);
  auto a=plain.continuous(p),b=traced.continuous(p);
  auto fa=V2IncomingCoordinator::evaluate(a,1800000000130000000LL);
  auto fb=V2IncomingCoordinator::evaluate(b,1800000000130000000LL);
  EXPECT_EQ(fa.forecast.belief.mean,fb.forecast.belief.mean);
  EXPECT_EQ(fa.forecast.belief.covariance,fb.forecast.belief.covariance);
  traced.set_decision_observer({});
}


TEST(V2IncomingDecisionObserver, ReferenceTransitionsRetainReceiptClock) {
  IncomingSourceContract ids{"session", "table", "fixture", "simulation", "clock", "ball"};
  V2IncomingCoordinator owner({}, {}, ids);
  std::vector<IncomingDecision> rows;
  owner.set_decision_observer([&](const auto& row){rows.push_back(row);});
  constexpr std::int64_t receipt = 1800000000123456789LL;
  EXPECT_TRUE(owner.update_reference([]{return std::make_pair(7ULL,true);}, receipt));
  ASSERT_EQ(rows.size(), 2u);
  EXPECT_STREQ(rows[0].phase.data(), "before_reference");
  EXPECT_STREQ(rows[1].phase.data(), "after_reference");
  EXPECT_EQ(rows[0].receipt_ns, receipt);
  EXPECT_EQ(rows[1].receipt_ns, receipt);
  EXPECT_EQ(rows[0].sequence + 1, rows[1].sequence);
}

TEST(V2IncomingCoordinator, DescriptiveTrackContinuesAfterRejectionWithoutRearmingCommand) {
  ShotSettings settings;
  settings.automatic_rearm = settings.game_legality_advisory = settings.descriptive_forecasts = true;
  FlightPipeline pipeline({}, settings);
  pipeline.start(origin, -1, BoundaryEvidence::RESTART, HistoryContinuity::kUnknown);
  ModelState physical;
  physical.position = Vec3(2.5, -.7, .8); physical.velocity = Vec3(-4, 0, 1);
  BallSample sample;
  sample.frame_id = "table"; sample.calibration_id = "fixture";
  sample.clock_domain = "simulation"; sample.clock_mapping_id = "clock"; sample.ball_id = "ball";
  std::uint64_t rejected_generation = 0;
  int descriptive_count = 0;
  for (int i = 0; i < 85; ++i) {
    sample.source_time_ns = origin + std::llround(i * 1e9 / 300);
    sample.position = physical.position;
    pipeline.observe(sample);
    if (i == 30) {
      pipeline.invalidate("qualified_non_ballistic_motion");
      rejected_generation = pipeline.shot().generation();
    }
    if (i > 40) {
      auto forecast = pipeline.forecast(plane().snapshot, sample.source_time_ns);
      ASSERT_TRUE(forecast.descriptive_only);
      ASSERT_TRUE(forecast.physical_available) << forecast.reason;
      EXPECT_FALSE(forecast.target.valid);
      EXPECT_EQ(forecast.reference_ns, sample.source_time_ns);
      EXPECT_EQ(pipeline.shot().generation(), rejected_generation);
      EXPECT_FALSE(pipeline.shot().active());
      EXPECT_LT((forecast.belief.mean.head<3>() - sample.position).norm(), .02);
      EXPECT_NE(forecast.nominal.uncertainty_provenance.find("not_command_authority"), std::string::npos);
      auto candidate = evaluate_v2_strike(forecast, pipeline.shot().export_snapshot(), {}, plane(), sample.source_time_ns);
      EXPECT_TRUE(candidate.physical_state_available);
      EXPECT_FALSE(candidate.command_eligible);
      EXPECT_FALSE(candidate.strike_contact_supported);
      EXPECT_FALSE(v2_strike_target(candidate, sample.source_time_ns).valid);
      EXPECT_EQ(select_physical_return(forecast, pipeline.shot().export_snapshot(), {}, sample.source_time_ns).reason,
                "DESCRIPTIVE_ONLY");
      ++descriptive_count;
    }
    EventGeometry geometry;
    advance_ball(physical, 1./300, {}, geometry);
  }
  EXPECT_GT(descriptive_count, 30);
  auto stale = pipeline.forecast(plane().snapshot, sample.source_time_ns + 31000000);
  EXPECT_FALSE(stale.physical_available);
  EXPECT_FALSE(stale.belief.initialized);
  EXPECT_EQ(stale.reason, "DESCRIPTIVE_SOURCE_EXPIRED");
  // An outlier must not be reported as a fresh posterior at its source time.
  sample.source_time_ns += 3333333; sample.position += Vec3(3, 2, 1);
  pipeline.observe(sample);
  auto rejected = pipeline.forecast(plane().snapshot, sample.source_time_ns);
  EXPECT_FALSE(rejected.physical_available);
  EXPECT_EQ(rejected.reason, "DESCRIPTIVE_MEASUREMENT_REJECTED");
}

TEST(V2IncomingCoordinator, DescriptiveOutputCannotClaimPacketOrSurviveSourceFault) {
  Source source;
  // Deliberately non-ballistic motion: a diagnostic track may describe this,
  // but the production shot qualifier must not authorize it.
  for (int i = 0; i < 40; ++i) {
    source.physical.position.z() = .8;
    source.physical.velocity.z() = 0;
    source.next();
  }
  auto query = source.owner.continuous(plane());
  auto evaluation = V2IncomingCoordinator::evaluate(query, source.now());
  ASSERT_TRUE(evaluation.forecast.descriptive_only);
  ASSERT_TRUE(evaluation.forecast.physical_available) << evaluation.forecast.reason;
  EXPECT_FALSE(evaluation.candidate.command_eligible);
  int publications = 0;
  EXPECT_TRUE(source.owner.publish(query, evaluation, source.now(), [&](auto &candidate) {
    EXPECT_FALSE(candidate.command_eligible); ++publications; return true;
  }));
  EXPECT_EQ(publications, 1);
  std::string reason;
  EXPECT_FALSE(source.owner.packet(source.packet(40), plane(), source.now(), reason));
  EXPECT_EQ(reason, "PACKET_PHYSICAL_GENERATION_RETIRED");
  EXPECT_EQ(source.owner.counters().commands, 0u);
  auto delayed = source.owner.continuous(plane());
  auto result = V2IncomingCoordinator::evaluate(delayed, source.now());
  EXPECT_FALSE(source.owner.publish(delayed, result, source.now() + 31000000, [](auto &) { return true; }));
  auto bad = source.samples.back(); bad.source_time_ns += 3333333; bad.calibration_id = "wrong";
  EXPECT_FALSE(source.owner.observe(bad, bad.source_time_ns));
  EXPECT_FALSE(source.owner.publish(delayed, result, bad.source_time_ns, [](auto &) { return true; }));
}

TEST(V2IncomingCoordinator, DescriptiveQueriesKeepCausalCutoffAndStandaloneRemainsStrict) {
  Source source;
  for (int i = 0; i < 20; ++i) {
    source.physical.position.z() = .8; source.physical.velocity.z() = 0; source.next();
  }
  auto query = source.owner.continuous(plane());
  const auto now = source.now();
  auto before = V2IncomingCoordinator::evaluate(query, now);
  ASSERT_TRUE(before.forecast.descriptive_only);
  ASSERT_TRUE(before.forecast.physical_available);
  source.physical.velocity = Vec3(3, 2, 4); source.to(50);
  auto after = V2IncomingCoordinator::evaluate(query, now);
  EXPECT_EQ(before.forecast.belief.mean, after.forecast.belief.mean);
  EXPECT_EQ(before.forecast.belief.covariance, after.forecast.belief.covariance);
  EXPECT_EQ(before.forecast.reference_ns, after.forecast.reference_ns);
  ShotSettings strict; strict.service_armed = true;
  FlightPipeline standalone({}, strict);
  for (auto sample : source.samples) standalone.observe(sample);
  auto forecast = standalone.forecast(plane().snapshot, source.now());
  EXPECT_FALSE(forecast.physical_available);
  EXPECT_FALSE(forecast.descriptive_only);
}
