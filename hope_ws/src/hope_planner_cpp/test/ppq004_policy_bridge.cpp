// Software-only MuJoCo bridge to production PpPolicy and schema receiver. No HAL.
#include "a3_pingpong/pp_policy.hpp"
#include <iostream>
struct RecordedPolicy {
 std::unique_ptr<a3_pingpong::PpPolicy> policy;
 std::shared_ptr<a3_pingpong::PpBasePoseInput> base;
 std::shared_ptr<a3_pingpong::PpRacketTargetInput> input;
 std::uint64_t tick=0;
 robot_io::RobotCommand last_command;
 robot_io::RobotState last_state;
};
extern "C" {
void* ppq_create(const char* onnx,const char* yaml) {
 try {
  auto p=std::make_unique<RecordedPolicy>();a3_pingpong::PpPolicyConfig c;
  c.deploy_cfg_path=yaml;c.shared_session_home=true;c.planner_preengagement_revocation=true;
  c.planner_mode=true;c.policy_native=true;c.single_swing=true;c.level=0;c.engage_settle_s=0;
  c.loc_mode=a3_pingpong::LocMode::kExternalBase;
  p->policy=std::make_unique<a3_pingpong::PpPolicy>(onnx,c);
  p->base=std::make_shared<a3_pingpong::PpBasePoseInput>();
  p->input=std::make_shared<a3_pingpong::PpRacketTargetInput>(4,true);
  p->policy->SetBasePoseInput(p->base);p->policy->SetRacketInput(p->input);return p.release();
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return nullptr;}
}
void ppq_destroy(void* p){delete static_cast<RecordedPolicy*>(p);}
void ppq_delivered(void* v){auto& p=*static_cast<RecordedPolicy*>(v);
 p.policy->RecordCommandDelivery(p.last_command,true,false,&p.last_state);}
void ppq_stand(void* v,double* out){auto& p=*static_cast<RecordedPolicy*>(v);
 Eigen::Map<Eigen::VectorXd>(out,31)=p.policy->official_stand_q();
 Eigen::Map<Eigen::VectorXd>(out+31,31)=p.policy->official_stand_kp();
 Eigen::Map<Eigen::VectorXd>(out+62,31)=p.policy->official_stand_kd();}
unsigned long long ppq_home(void* v){return static_cast<RecordedPolicy*>(v)->policy->session_home_unsafe().epoch;}
const char* ppq_status(void* v){
 static thread_local std::string status;
 auto& p=*static_cast<RecordedPolicy*>(v);
 status=p.policy->planner_trace_snapshot(p.tick).status;return status.c_str();
}
int ppq_wire(void* v,const double* wire,int size){
 try {auto& p=*static_cast<RecordedPolicy*>(v);p.input->SetFromFlat(std::vector<double>(wire,wire+size));return p.input->Latest().has_valid?1:0;}
 catch(...){return -1;}}
int ppq_step(void* v,const double* state,double* output){
 try {auto& p=*static_cast<RecordedPolicy*>(v);robot_io::RobotState s;
 s.q=Eigen::Map<const Eigen::VectorXd>(state,31);s.dq=Eigen::Map<const Eigen::VectorXd>(state+31,31);
 s.imu_quat_wxyz=Eigen::Map<const Eigen::Vector4d>(state+62);s.imu_gyro=Eigen::Map<const Eigen::Vector3d>(state+66);
 s.has_secondary_imu=true;s.sec_imu_quat_wxyz=Eigen::Map<const Eigen::Vector4d>(state+72);
 const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
 p.base->SetFromFlat({2,1,double(p.tick+1),double(ns/1000000000),double(ns%1000000000),
   state[69],state[70],state[71],state[62],state[63],state[64],state[65],1,47,7,8});
 robot_io::RobotCommand c;if(!p.policy->ComputeCommand(p.tick++,s,c))return -1;
 p.last_command=c;p.last_state=s;
 Eigen::Map<Eigen::VectorXd>(output,31)=c.q_des;Eigen::Map<Eigen::VectorXd>(output+31,31)=c.dq_des;
 Eigen::Map<Eigen::VectorXd>(output+62,31)=c.tau_ff;Eigen::Map<Eigen::VectorXd>(output+93,31)=c.kp;
 Eigen::Map<Eigen::VectorXd>(output+124,31)=c.kd;return p.policy->level();
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return -1;}}
}
