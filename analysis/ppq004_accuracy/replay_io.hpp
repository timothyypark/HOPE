#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
struct Frame {
  std::size_t index;
  std::int64_t ns;
  int present, oriented;
  double x,y,z,qx,qy,qz,qw;
};
inline bool read_frame(Frame& f) {
  std::string line;
  if(!std::getline(std::cin,line)) return false;
  std::replace(line.begin(),line.end(),',',' ');
  std::istringstream in(line);
  if(!(in>>f.index>>f.ns>>f.present>>f.x>>f.y>>f.z>>f.oriented>>f.qx>>f.qy>>f.qz>>f.qw))
    throw std::runtime_error("Malformed frame");
  std::string extra;if(in>>extra)throw std::runtime_error("Extra input field");
  return true;
}
inline void number(double x) { if(std::isfinite(x))std::cout<<x;else std::cout<<"null"; }
template<class V> void vector_json(const V& v) {
  std::cout<<'[';for(int i=0;i<v.size();++i){if(i)std::cout<<',';number(v[i]);}std::cout<<']';
}
inline void prefix(const char* method,const Frame& f) {
  std::cout<<"{\"method\":"<<std::quoted(method)<<",\"source_index\":"<<f.index<<",\"source_ns\":"<<f.ns;
}
inline const std::vector<double> planes{.15,.08,.7,1.37};
