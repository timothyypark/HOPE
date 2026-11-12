#include "hope_planner_cpp/flight_state_v2.hpp"
#include <gtest/gtest.h>
using namespace hope_planner_cpp;
namespace {
BallSample sample(std::int64_t ns, int direction=1) {
  BallSample s; s.source_time_ns=ns; s.source_time_s=ns*1e-9;
  const double t=ns*1e-9;
  s.position=Vec3(1+direction*3*t,-.7,.5+t-4.905*t*t);
  s.frame_id="table";s.clock_domain="simulation";s.ball_id="ball";return s;
}
ModelState contact(double x, int direction) {
  ModelState s;s.position=Vec3(x,-.7,.02);s.velocity=Vec3(direction*3,0,-2);return s;
}
class PPQ004Contract : public ::testing::TestWithParam<bool> {
 protected:
  ShotSettings settings() const { ShotSettings s;s.automatic_rearm=GetParam();
    s.game_legality_advisory=GetParam();return s; }
};
TEST_P(PPQ004Contract, S01_StartupAndHeldBallNeverAuthorize) {
  ShotContext s({},settings());EXPECT_EQ(s.state(),PlayState::INVALID);
  for(int i=0;i<100;++i) {auto p=sample(i*3333333LL);p.position=Vec3(1,-.7,.5);
    p.orientation_valid=true;p.orientation=Eigen::Quaterniond::Identity();s.observe(p);}
  EXPECT_FALSE(s.qualify_candidate());EXPECT_EQ(s.state(),PlayState::INVALID);
}
TEST_P(PPQ004Contract, S02_BothDirectionsRemainProvisionalWithMissingHistory) {
  for(int direction:{-1,1}) { ShotContext s({},settings());
    s.start(0,direction,BoundaryEvidence::ACQUISITION,HistoryContinuity::kUnknown);
    s.observe(sample(0,direction));
    EXPECT_EQ(s.state(),direction<0?PlayState::OPPONENT_RALLY:PlayState::RALLY);
    EXPECT_EQ(s.classification(),ClassificationStatus::PROVISIONAL);
  }
}
TEST_P(PPQ004Contract, S03_ObservedServePreservesIdentityAndSamples) {
  for(int direction:{-1,1}) { ShotContext s({},settings());
    s.start(0,direction,BoundaryEvidence::RACKET_CONTACT,HistoryContinuity::kComplete);
    s.observe(sample(0,direction));const auto generation=s.generation(),count=s.samples().size();
    s.confirm(PhysicalEventKind::TABLE,100000000,110000000,
      contact(direction<0?2.3:.4,direction),"independent_fixture");
    EXPECT_EQ(s.state(),direction<0?PlayState::OPPONENT_SERVE:PlayState::SERVE);
    EXPECT_EQ(s.generation(),generation);EXPECT_EQ(s.samples().size(),count);
    EXPECT_EQ(s.events().back().confirmed_at_ns,110000000);
    auto net=contact(1.37,direction);net.position.z()=.3;
    s.confirm(PhysicalEventKind::NET_CROSSING,200000000,200000000,net,"independent_fixture");
    s.confirm(PhysicalEventKind::TABLE,300000000,310000000,
      contact(direction<0?.4:2.3,direction),"independent_fixture");
    EXPECT_TRUE(s.active());EXPECT_EQ(s.observed_contacts(),2);
    EXPECT_EQ(s.generation(),generation);
  }
}
TEST_P(PPQ004Contract, S04_ContextAndPredictionsCannotConfirmPublicServe) {
  for(int direction:{-1,1}) {ShotContext s({},settings());
    s.start(0,direction,BoundaryEvidence::ACQUISITION,HistoryContinuity::kUnknown);
    s.observe(sample(0,direction));
    ASSERT_TRUE(s.context(MatchContext::SERVE,0,"context_fixture",s.generation()));
    PhysicalEvent e;e.kind=PhysicalEventKind::TABLE;e.dt_s=.1;
    e.pre=e.post=contact(direction<0?2.3:.4,direction);s.predict_events({e},0);
    EXPECT_EQ(s.state(),direction<0?PlayState::OPPONENT_RALLY:PlayState::RALLY);
    EXPECT_EQ(s.observed_contacts(),0);
  }
}
TEST_P(PPQ004Contract, S05_StrictAndAdvisoryIllegalOrderDifferExplicitly) {
  ShotContext s({},settings());s.start(0,1,BoundaryEvidence::RACKET_CONTACT,HistoryContinuity::kComplete);
  s.observe(sample(0));ASSERT_TRUE(s.context(MatchContext::NORMAL_RALLY,0,"fixture",s.generation()));
  s.confirm(PhysicalEventKind::TABLE,100000000,110000000,contact(.4,1),"fixture");
  EXPECT_EQ(s.active(),GetParam());
}
TEST_P(PPQ004Contract, S06_ResetFencesOldGenerationAndContext) {
  ShotContext s({},settings());s.start(0,-1,BoundaryEvidence::RACKET_CONTACT,HistoryContinuity::kComplete);
  s.observe(sample(0,-1));const auto token=s.snapshot();s.invalidate("explicit_reset");
  EXPECT_EQ(s.state(),PlayState::INVALID);EXPECT_FALSE(s.publishable(token,1000000));
  EXPECT_FALSE(s.context(MatchContext::SERVE,1000000,"stale",token.generation));
  s.start(2000000,1,BoundaryEvidence::RACKET_CONTACT,HistoryContinuity::kComplete);
  EXPECT_GT(s.generation(),token.generation);EXPECT_TRUE(s.samples().empty());
}
INSTANTIATE_TEST_SUITE_P(Profiles,PPQ004Contract,::testing::Bool(),
  [](const auto& info){return info.param?"Managed":"Strict";});
}
