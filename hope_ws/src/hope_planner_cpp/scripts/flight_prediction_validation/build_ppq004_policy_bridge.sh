#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../../../../.." && pwd)
output=${1:?Usage: build_ppq004_policy_bridge.sh NEW_OUTPUT_DIRECTORY}
ort=${ORT_ROOT:?Set ORT_ROOT to the pinned ONNX Runtime C++ distribution}
[[ ! -e "$output" ]] || { echo 'Output already exists' >&2; exit 2; }
mkdir -p "$output"
runner="$repo/a3_deploy/a3_deploy_example/src/a3/a3_deploy_onnx_ref"
g++ -std=c++20 -O1 -shared -fPIC -pthread -I/usr/include/eigen3 -I"$ort/include" -I"$runner/include" \
 "$repo/hope_ws/src/hope_planner_cpp/test/ppq004_policy_bridge.cpp" \
 "$runner/src/a3_deploy/pp_gripper_worker.cpp" "$ort/lib/libonnxruntime.so" \
 -Wl,-rpath,"$ort/lib" -lyaml-cpp -o "$output/libppq004_policy.so" > "$output/build.log" 2>&1
sha256sum "$output/libppq004_policy.so" "$ort/lib/libonnxruntime.so" \
 "$repo/hope_training/whole_body_tracking/checkpoints/policy.onnx" \
 "$repo/hope_training/whole_body_tracking/checkpoints/deploy.yaml" > "$output/sha256.txt"
