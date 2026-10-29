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
TEST(V2IncomingCoordinator, HistoryAndCheckpointsStayBounded) {
  Source source; source.to(700);
  EXPECT_LE(source.owner.counters().history, contract().history_capacity);
  EXPECT_LE(source.owner.counters().checkpoints, contract().checkpoint_capacity);
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
  auto delayed = source.owner.continuous(selected);
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
