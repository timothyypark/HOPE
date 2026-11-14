// Diagnostic queries into unchanged pinned upstream classes; no future labels.
#include "replay_io.hpp"
#include "hope_planner_cpp/batch_physics_estimator.hpp"
#include "hope_planner_cpp/spin_estimator.hpp"
#include "hope_planner_cpp/future_contact_predictor.hpp"
#include "hope_planner_cpp/laptop_play_state.hpp"
#include <yaml-cpp/yaml.h>
using namespace hope_planner_cpp;
int main(int argc,char** argv) { try {
  if(argc!=3)throw std::runtime_error("main_replay hardware.yaml packetizer.yaml");
  const auto p=YAML::LoadFile(argv[1])["hope_planner"]["ros__parameters"];
  const auto g=YAML::LoadFile(argv[2])["hope_ball_flight_packetizer"]["ros__parameters"];
  BallPhysics physics;EstimatorConfig ec;SpinEstimatorConfig sc;FutureContactConfig fc;PlannerConfig pc;TableParams table;PlayStateConfig gc;
#define SET(node,obj,field,key,type) if(node[key])obj.field=node[key].as<type>()
  SET(p,physics,drag_k,"drag_k",double); SET(p,physics,magnus_k,"magnus_k",double);
  SET(p,physics,restitution_h,"restitution_h",double); SET(p,physics,restitution_v,"restitution_v",double);
  SET(p,physics,table_tangential_gain,"table_tangential_gain",double); SET(p,physics,table_friction_cap_mu,"table_friction_cap_mu",double);
  SET(p,physics,nakashima_friction_mu,"nakashima_friction_mu",double);
  SET(p,ec,spin_enabled,"future_contact_magnus_enabled",bool); SET(p,ec,spin_min_coherence,"future_contact_spin_min_coherence",double);
  SET(p,ec,window_s,"batch_estimator_window_s",double); SET(p,ec,min_span_s,"batch_estimator_min_span_s",double);
  SET(p,ec,min_samples,"batch_estimator_min_samples",std::size_t); SET(p,ec,huber_delta_m,"batch_estimator_huber_delta_m",double);
  SET(p,ec,recency_half_life_s,"batch_estimator_recency_half_life_s",double); SET(p,ec,robust_iterations,"batch_estimator_iterations",int);
  SET(p,ec,integration_dt_s,"dt_integrate",double); SET(p,ec,single_flight_only,"batch_single_flight_only",bool);
  SET(p,ec,post_bounce_min_span_s,"batch_post_bounce_min_span_s",double); SET(p,ec,post_bounce_exclusion_s,"batch_post_bounce_exclusion_s",double);
  SET(p,ec,max_sample_gap_s,"batch_max_sample_gap_s",double);
  SET(p,ec,bounce_center_z_max_m,"bounce_center_z_max",double); SET(p,ec,bounce_min_reversal_m,"bounce_min_reversal_m",double);
  SET(p,ec,bounce_min_excursion_m,"bounce_min_excursion_m",double); SET(p,ec,bounce_confirmation_samples,"bounce_confirmation_samples",std::size_t);
  SET(p,ec,bounce_confirmation_max_span_s,"bounce_confirmation_max_span_s",double); SET(p,ec,bounce_sparse_confirmation_min_span_s,"bounce_sparse_confirmation_min_span_s",double);
  SET(p,ec,bounce_sparse_confirmation_excursion_m,"bounce_sparse_confirmation_excursion_m",double); SET(p,ec,bounce_refractory_s,"bounce_refractory_s",double);
  SET(p,sc,window_s,"spin_window_s",double); SET(p,sc,min_span_s,"spin_min_span_s",double); SET(p,sc,max_gap_s,"spin_max_gap_s",double);
  SET(p,sc,max_rev_s,"spin_max_rev_s",double); SET(p,sc,huber_delta_rev_s,"spin_huber_delta_rev_s",double);
  SET(p,sc,min_increments,"spin_min_increments",std::size_t); SET(p,sc,robust_iterations,"spin_robust_iterations",int);
  SET(p,fc,spin_enabled,"future_contact_spin_enabled",bool); SET(p,fc,magnus_enabled,"future_contact_magnus_enabled",bool);
  SET(p,fc,tangential_gain,"future_contact_spin_tangential_gain",double); SET(p,fc,omega_scale,"future_contact_spin_omega_scale",double);
  SET(p,fc,min_coherence,"future_contact_spin_min_coherence",double); SET(p,fc,require_spin_for_future_contact,"future_contact_require_spin",bool);
  SET(p,pc,integrate_dt_s,"dt_integrate",double); SET(p,pc,max_predict_time_s,"max_predict_time",double);
  SET(p,pc,adaptive_predict_horizon,"adaptive_predict_horizon",bool); SET(p,pc,max_predict_time_cap_s,"max_predict_time_cap",double);
  SET(p,table,net_x,"net_x",double); SET(p,table,y_max,"table_y_max",double);
  SET(g,gc,input_timeout_s,"play_state_input_timeout_s",double); SET(g,gc,rally_min_speed_mps,"play_state_rally_min_speed_mps",double);
  SET(g,gc,rally_slow_confirm_s,"play_state_rally_slow_confirm_s",double); SET(g,gc,direction_speed_mps,"play_state_direction_speed_mps",double);
  SET(g,gc,direction_confirm_s,"play_state_direction_confirm_s",double); SET(g,gc,launch_span_s,"play_state_launch_span_s",double);
  SET(g,gc,held_span_s,"play_state_held_span_s",double); SET(g,gc,contact_height_m,"play_state_contact_height_m",double);
  // Mirror FlightPacketizerNode's dedicated operator preview fit, including
  // its explicit constructor overrides, rather than the downstream HDU fit.
  EstimatorConfig operator_ec; SpinEstimatorConfig operator_sc;
  operator_ec.spin_enabled=fc.magnus_enabled;
  operator_ec.spin_min_coherence=fc.min_coherence;
  SET(g,operator_ec,huber_delta_m,"batch_estimator_huber_delta_m",double);
  SET(g,operator_ec,recency_half_life_s,"batch_estimator_recency_half_life_s",double);
  SET(g,operator_ec,robust_iterations,"batch_estimator_iterations",int);
  SET(g,operator_ec,post_bounce_min_span_s,"batch_post_bounce_min_span_s",double);
  SET(g,operator_ec,post_bounce_exclusion_s,"batch_post_bounce_exclusion_s",double);
  SET(g,operator_sc,window_s,"spin_window_s",double);
  operator_ec.window_s=.10;operator_ec.min_span_s=.060;
  operator_ec.min_samples=8;operator_ec.single_flight_only=true;
  for(const auto* key:{"drag_k","magnus_k","restitution_h","restitution_v",
      "table_tangential_gain","table_friction_cap_mu","post_net_future_bounce_tangential_gain",
      "post_net_future_bounce_restitution_v","future_contact_spin_tangential_gain",
      "future_contact_spin_omega_scale","future_contact_spin_min_coherence"})
    if(p[key].as<double>()!=g[key].as<double>())throw std::runtime_error("Profiles differ: "+std::string(key));
  for(const auto* key:{"future_contact_magnus_enabled","future_contact_spin_enabled","future_contact_require_spin"})
    if(p[key].as<bool>()!=g[key].as<bool>())throw std::runtime_error("Profiles differ: "+std::string(key));
#undef SET
  BallPhysics future=physics;
  future.table_tangential_gain=p["post_net_future_bounce_tangential_gain"].as<double>();
  future.restitution_v=p["post_net_future_bounce_restitution_v"].as<double>();
  BatchPhysicsEstimator plain(physics,ec,sc), admitted(physics,operator_ec,operator_sc);
  SpinEstimator plain_spin(sc),admitted_spin(operator_sc);LaptopPlayState gate(gc);gate.set_hit_plane(.15);
  FutureContactPredictor predictor(future,pc,table,fc);
  PlannerConfig operator_pc;operator_pc.adaptive_predict_horizon=true;
  FutureContactPredictor operator_predictor(future,operator_pc,TableParams{},fc);
  std::uint64_t generation=gate.generation();double bounce=-1e9;
  auto sync=[&]{if(generation==gate.generation())return false;generation=gate.generation();admitted.reset();admitted_spin.reset();bounce=-1e9;return true;};
  std::cout<<std::setprecision(17);Frame f;std::size_t count=0;std::int64_t previous=-1;
  while(read_frame(f)) {
    if(f.index!=count++||f.ns<=previous)throw std::runtime_error("Input sequence/order");previous=f.ns;
    gate.poll(f.ns);sync();
    if(!f.present){gate.input_unavailable("ball_pose_missing",f.ns);sync();}
    else {
      BallSample s;s.source_time_ns=f.ns;s.source_time_s=f.ns*1e-9;s.sequence=f.index+1;
      s.receipt_steady_ns=f.ns;s.receipt_wall_ns=f.ns;s.position=Vec3(f.x,f.y,f.z);
      s.orientation=Eigen::Quaterniond(f.qw,f.qx,f.qy,f.qz);s.orientation_valid=f.oriented;
      plain.push(s);plain_spin.push(s);
      const bool accepted=gate.observe(s);const bool fresh=sync();
      if(accepted&&gate.state()!=PlayState::INVALID&&!gate.waiting_for_launch()&&gate.sample_usable()) {
        if(fresh){for(const auto& seed:gate.samples()){admitted.push(seed);admitted_spin.push(seed);}}
        else {if(gate.last_bounce_time()!=bounce){admitted.reset();admitted_spin.reset();bounce=gate.last_bounce_time();}
          admitted.push(s);admitted_spin.push(s);}
      }
    }
    if(f.index%6)continue;
    auto emit=[&](const char* method,BatchPhysicsEstimator& estimator,SpinEstimator& spin,bool allowed,const FutureContactPredictor& predictor) {
      const auto state=estimator.estimate();const auto omega=state.spin_model_enabled?state.physics_spin:spin.estimate();
      const bool fresh=std::abs(state.source_time_s-f.ns*1e-9)<1e-8;
      const bool available=f.present&&allowed&&state.valid&&fresh;
      prefix(method,f);std::cout<<",\"available\":"<<available<<",\"reason\":"<<std::quoted(allowed?state.reason:gate.reason())
        <<",\"state\":"<<std::quoted(play_state_name(gate.state()))<<",\"generation\":"<<generation<<",\"position\":";
      vector_json(state.position);std::cout<<",\"velocity\":";vector_json(state.velocity);
      Vec3 effective=Vec3::Zero();
      if(predictor.uses_spin(omega))effective=fc.omega_scale*omega.omega_rad_s;
      else if(state.spin_model_enabled)effective=omega.omega_rad_s;
      std::cout<<",\"spin_available\":"<<predictor.uses_spin(omega)<<",\"omega\":";
      vector_json(effective);
      std::cout<<",\"targets\":[";
      for(std::size_t i=0;i<planes.size();++i){if(i)std::cout<<',';const auto target=predictor.predict(state,planes[i],omega);
        std::cout<<"{\"plane\":"<<planes[i]<<",\"valid\":"<<(available&&target.valid)<<",\"reason\":"<<std::quoted(target.reason)<<",\"position\":";
        vector_json(target.ball_position);std::cout<<",\"arrival_ns\":";number(target.strike_source_time_s*1e9);std::cout<<'}';}
      std::cout<<"]}\n";
    };
    emit("main_batch",plain,plain_spin,true,predictor);emit("main_operator",admitted,admitted_spin,gate.incoming_flight(),operator_predictor);
  }
  std::cerr<<"frames="<<count<<" complete=true\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
