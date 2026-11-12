// Observation-only full-take replay: no annotation, START, CONTEXT or CONTACT input.
#include "hope_planner_cpp/v2_incoming_coordinator.hpp"
#include "hope_planner_cpp/flight_replay_input.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
using namespace hope_planner_cpp;
const char* forecast_status(ForecastStatus status) {
  switch (status) {
    case ForecastStatus::READY: return "READY";
    case ForecastStatus::WARMING_UP: return "WARMING_UP";
    case ForecastStatus::HORIZON_EXHAUSTED: return "HORIZON_EXHAUSTED";
    case ForecastStatus::UNCERTAIN: return "UNCERTAIN";
    case ForecastStatus::REVOKED: return "REVOKED";
  }
  throw std::logic_error("unknown forecast status");
}
int main(int argc,char** argv) {
 try {
  ProbabilisticConfig config;ShotSettings settings;std::string profile="managed",forecast_path;
  double plane_x=.15;std::size_t stride=6;
  for(int i=1;i<argc;++i) {
    const std::string key=argv[i];
    if(i+1>=argc) throw std::invalid_argument("option missing value");
    const std::string value=argv[++i];
    if(key=="--profile") profile=value;
    else if(key=="--plane-x") plane_x=std::stod(value);
    else if(key=="--forecasts") forecast_path=value;
    else if(key=="--forecast-stride") stride=std::stoul(value);
    else if(key=="--set") {auto split=value.find('=');if(split==std::string::npos) throw std::invalid_argument("key=value required");
      set_flight_parameter(config,settings,value.substr(0,split),std::stod(value.substr(split+1)));}
    else throw std::invalid_argument("unknown option");
  }
  if((profile!="strict"&&profile!="managed")||!stride||!std::isfinite(plane_x)) throw std::invalid_argument("bad profile/stride/plane");
  IncomingSourceContract contract{"recorded", "ppq004_table_corner", "ppq004_20261020_recorded_table_corner", "recorded_virtual", "integer_epoch", "Ball"};
  V2IncomingCoordinator owner(config,settings,contract);FlightPipeline strict(config,settings);
  // Explicit fixed reference fixture: recorded base centroids have no control-point extrinsic.
  PlaneSelection selected;selected.valid=true;selected.epoch=1;selected.flight=1;
  selected.reference_x=plane_x-.58;selected.plane_x=plane_x;
  auto plane=incoming_plane(selected,contract.frame,contract.registration,false);
  owner.update_reference([]{return std::make_pair(1ULL,true);});
  std::ofstream forecasts;if(!forecast_path.empty()) {forecasts.open(forecast_path);if(!forecasts)throw std::runtime_error("forecast output failed");forecasts<<std::setprecision(17);}
  std::cout<<std::setprecision(17);
  std::uint64_t trace=0,frames=0;std::int64_t previous=0;bool first=true;
  auto emit=[&](const char* phase,std::size_t index,std::int64_t now,bool available,bool accepted) {
    // Copies carry causal state; no second live tracker participates in managed replay.
    auto query=owner.continuous(plane);const auto& shot=profile=="managed"?query.pipeline.shot():strict.shot();
    std::cout<<"{\"trace_sequence\":"<<++trace<<",\"source_index\":"<<index<<",\"source_ns\":"<<now
      <<",\"receipt_ns\":"<<now<<",\"clock\":\"virtual\",\"phase\":\""<<phase<<"\",\"profile\":\""<<profile
      <<"\",\"present\":"<<available<<",\"accepted\":"<<accepted<<",\"generation\":"<<shot.generation()
      <<",\"semantic_revision\":"<<shot.revision()<<",\"semantic_epoch\":"<<query.semantic_epoch
      <<",\"play_state\":\""<<name(shot.state())<<"\",\"classification_status\":\""
      <<(shot.classification()==ClassificationStatus::CONFIRMED?"CONFIRMED":"PROVISIONAL")
      <<"\",\"history_continuity\":"<<static_cast<int>(shot.continuity())<<",\"forecast_route\":\""<<name(shot.route())
      <<"\",\"acquisition\":\""<<shot.acquisition_state()<<"\",\"reason\":\""<<shot.reason()
      <<"\",\"spin_available\":"<<shot.spin().usable()<<",\"observation_count\":"<<shot.samples().size()
      <<",\"authority_evidence\":\"see_candidate_and_revocation\",\"events\":[";
    bool comma=false;for(const auto& event:shot.events()) {if(comma)std::cout<<',';comma=true;
      std::cout<<"{\"id\":"<<event.id<<",\"generation\":"<<event.generation<<",\"kind\":\""<<name(event.kind)
        <<"\",\"status\":"<<static_cast<int>(event.status)<<",\"occurrence_ns\":"<<event.event_time_ns
        <<",\"available_ns\":"<<event.confirmed_at_ns<<'}';}
    std::cout<<"]}\n";
  };
  std::string line;while(std::getline(std::cin,line)) {
    if(line.empty()||line[0]=='#')continue;
    std::replace(line.begin(),line.end(),',',' ');std::istringstream in(line);
    std::size_t index;std::int64_t now;int present;double x,y,z;int oriented;double qx,qy,qz,qw;
    if(!(in>>index>>now>>present>>x>>y>>z>>oriented>>qx>>qy>>qz>>qw)) throw std::invalid_argument("expected index,ns,present,xyz,orientation_available,xyzw");
    std::string trailing;if(in>>trailing)throw std::invalid_argument("trailing frame input");
    if(!first&&index!=frames)throw std::invalid_argument("missing source frame index");
    first=false;
    emit("before",index,now,present,false);
    // A missing measurement still advances expiry; it is never a zero XYZ observation.
    owner.expire(now);
    emit("after_expire",index,now,present,false);
    bool accepted=false;
    if(present) {
      BallSample sample;sample.source_time_ns=now;sample.source_time_s=now*1e-9;sample.sequence=index+1;
      sample.position=Vec3(x,y,z);sample.orientation=Eigen::Quaterniond(qw,qx,qy,qz);
      sample.orientation_valid=oriented;sample.orientation_authoritative=oriented;
      sample.frame_id=contract.frame;sample.calibration_id=contract.registration;
      sample.clock_domain=contract.clock_domain;sample.clock_mapping_id=contract.clock_mapping;sample.ball_id=contract.ball;
      accepted=profile=="managed"?owner.observe(sample,now):strict.observe(sample);
    }
    emit("after",index,now,present,accepted);
    if(forecasts.is_open()&&frames%stride==0) {
      auto query=owner.continuous(plane);
      IncomingEvaluation evaluation;
      if(profile=="managed") evaluation=V2IncomingCoordinator::evaluate(query,now);
      else evaluation.forecast=strict.forecast(plane.snapshot,now);
      auto& f=evaluation.forecast;
      forecasts<<"{\"source_index\":"<<index<<",\"source_ns\":"<<now<<",\"prediction_reference_ns\":"<<f.reference_ns
        <<",\"generation\":"<<f.token.generation<<",\"physical_available\":"<<f.physical_available
        <<",\"forecast_status\":\""<<forecast_status(f.status)<<"\",\"reason\":\""<<f.reason
        <<"\",\"command_eligible\":"<<(profile=="managed"&&evaluation.candidate.command_eligible)
        <<",\"candidate_reason\":\""<<evaluation.candidate.reason<<"\",\"model_config_id\":\""<<f.model_config_id<<"\",\"waypoints\":[";
      bool comma=false;for(const auto& w:f.nominal.waypoints) {if(comma)forecasts<<',';comma=true;
        forecasts<<'['<<w.dt_s;for(int a=0;a<6;++a)forecasts<<','<<w.state[a];forecasts<<']';}
      forecasts<<"]}\n";
    }
    for(const auto& status:owner.take_statuses()) {
      std::cout<<"{\"trace_sequence\":"<<++trace<<",\"phase\":\"revocation\",\"source_index\":"<<index
        <<",\"source_ns\":"<<now<<",\"generation\":"<<status.token.generation<<",\"reason\":\""<<status.reason<<"\"}\n";
    }
    previous=now;++frames;
  }
  owner.expire(previous+31000000);emit("end_expiry",frames,previous+31000000,false,false);
  std::cout<<"{\"trace_sequence\":"<<++trace<<",\"phase\":\"footer\",\"frames\":"<<frames<<",\"complete\":true}\n";
  return std::cout.good()&&(!forecasts.is_open()||forecasts.good())?0:3;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
}
