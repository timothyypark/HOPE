// Observation-only full-take queries against unchanged pinned managed V2 core.
#include "replay_io.hpp"
#include "hope_planner_cpp/v2_incoming_coordinator.hpp"
using namespace hope_planner_cpp;
int main() {try {
  ProbabilisticConfig config;ShotSettings settings;
  IncomingSourceContract contract{"comparison","table","ppq004_table_corner","virtual","integer","Ball"};
  V2IncomingCoordinator owner(config,settings,contract);
  owner.update_reference([]{return std::make_pair(1ULL,true);});
  std::cout<<std::setprecision(17);Frame f;std::size_t count=0;std::int64_t previous=-1;
  while(read_frame(f)) {
    if(f.index!=count++||f.ns<=previous)throw std::runtime_error("Input sequence/order");previous=f.ns;
    owner.expire(f.ns);
    if(f.present) {
      BallSample s;s.source_time_ns=f.ns;s.source_time_s=f.ns*1e-9;s.sequence=f.index+1;
      s.receipt_steady_ns=f.ns;s.receipt_wall_ns=f.ns;s.position=Vec3(f.x,f.y,f.z);
      s.orientation=Eigen::Quaterniond(f.qw,f.qx,f.qy,f.qz);s.orientation_valid=f.oriented;s.orientation_authoritative=f.oriented;
      s.frame_id=contract.frame;s.calibration_id=contract.registration;s.clock_domain=contract.clock_domain;s.clock_mapping_id=contract.clock_mapping;s.ball_id=contract.ball;
      owner.observe(s,f.ns);
    }
    if(f.index%6==0) {
      prefix("v2_managed",f);
      for(std::size_t i=0;i<planes.size();++i) {
        PlaneSelection selected;selected.valid=true;selected.epoch=1;selected.flight=1;selected.reference_x=planes[i]-.58;selected.plane_x=planes[i];
        const auto plane=incoming_plane(selected,contract.frame,contract.registration,false);
        auto q=owner.continuous(plane);auto e=V2IncomingCoordinator::evaluate(q,f.ns);const auto& forecast=e.forecast;
        const bool available=f.present&&forecast.physical_available&&forecast.reference_ns==f.ns;
        if(i==0){std::cout<<",\"available\":"<<available<<",\"reason\":"<<std::quoted(forecast.reason)<<",\"state\":"<<std::quoted(name(forecast.state))
          <<",\"generation\":"<<forecast.token.generation<<",\"position\":";vector_json(forecast.belief.mean.head<3>());
          std::cout<<",\"velocity\":";vector_json(forecast.belief.mean.tail<3>());std::cout<<",\"spin_available\":"<<forecast.belief.effective_spin.usable()<<",\"omega\":";
          vector_json(forecast.belief.effective_spin.omega.value_or(Vec3::Zero()));std::cout<<",\"targets\":[";
        }else std::cout<<',';
        const auto target=v2_strike_target(e.candidate,f.ns);
        std::cout<<"{\"plane\":"<<planes[i]<<",\"valid\":"<<(available&&target.valid)<<",\"reason\":"<<std::quoted(e.candidate.reason)<<",\"position\":";
        vector_json(target.ball_position);std::cout<<",\"arrival_ns\":";number(target.strike_source_time_s*1e9);std::cout<<'}';
      }
      std::cout<<"]}\n";
    }
    owner.take_statuses();
  }
  std::cerr<<"frames="<<count<<" complete=true\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
