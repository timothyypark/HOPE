cmake_minimum_required(VERSION 3.16)
project(ppq004_accuracy LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Eigen3 REQUIRED NO_MODULE)
find_package(yaml-cpp REQUIRED)
find_package(GTest REQUIRED)
enable_testing()
if(NOT MAIN_ROOT OR NOT V2_ROOT)
  message(FATAL_ERROR "Supply pinned MAIN_ROOT and V2_ROOT")
endif()
set(MAIN_P ${MAIN_ROOT}/hope_ws/src/hope_planner_cpp)
set(V2_P ${V2_ROOT}/hope_ws/src/hope_planner_cpp)
add_library(main_core ${MAIN_P}/src/batch_physics_estimator.cpp
  ${MAIN_P}/src/spin_estimator.cpp ${MAIN_P}/src/trajectory_predictor.cpp
  ${MAIN_P}/src/laptop_play_state.cpp)
target_include_directories(main_core PUBLIC ${MAIN_P}/include)
target_link_libraries(main_core PUBLIC Eigen3::Eigen)
add_executable(main_replay main_replay.cpp)
target_link_libraries(main_replay PRIVATE main_core yaml-cpp)
add_library(v2_core
  ${V2_P}/src/common_ball_physics.cpp ${V2_P}/src/flight_spin_estimator.cpp
  ${V2_P}/src/flight_state_v2.cpp ${V2_P}/src/spin_estimator.cpp
  ${V2_P}/src/probabilistic_physics.cpp ${V2_P}/src/probabilistic_ball_tracker.cpp
  ${V2_P}/src/nominal_event_forecast.cpp ${V2_P}/src/fixed_lag_types.cpp
  ${V2_P}/src/hit_plane_manager.cpp ${V2_P}/src/v2_incoming_coordinator.cpp
  ${V2_P}/src/v2_strike_adapter.cpp ${V2_P}/src/return_eligibility.cpp ${V2_P}/src/return_region.cpp)
target_include_directories(v2_core PUBLIC ${V2_P}/include)
target_link_libraries(v2_core PUBLIC Eigen3::Eigen)
add_executable(v2_replay v2_replay.cpp)
target_link_libraries(v2_replay PRIVATE v2_core)
foreach(target main_replay v2_replay)
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
endforeach()
foreach(test batch_physics_estimator spin_estimator future_contact_predictor laptop_play_state)
  add_executable(main_test_${test} ${MAIN_P}/test/test_${test}.cpp)
  target_link_libraries(main_test_${test} PRIVATE main_core GTest::gtest_main)
  add_test(NAME main_${test} COMMAND main_test_${test})
endforeach()
add_executable(v2_test_coordinator ${V2_P}/test/test_v2_incoming_coordinator.cpp)
target_link_libraries(v2_test_coordinator PRIVATE v2_core GTest::gtest_main)
add_test(NAME v2_coordinator COMMAND v2_test_coordinator)
