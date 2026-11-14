"""Freeze inputs and run both native prediction adapters; never supplies labels."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def run(args):
    contract = json.loads(Path(__file__).with_name('contract.json').read_text())
    for root, pin in ((args.main, contract['main_sha']), (args.v2, contract['v2_sha'])):
        if git(root, 'rev-parse', 'HEAD') != pin or git(root, 'status', '--porcelain'):
            raise ValueError('Pinned implementation must be clean: ' + str(root))
    harness = Path(__file__).resolve().parents[2]
    if git(harness, 'status', '--porcelain'):
        raise ValueError('Commit harness before running recordings')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.prepared / 'manifest.json').read_text())
    observation_path = args.prepared / 'observations.jsonl'
    if digest(observation_path) != manifest['files']['observations.jsonl']:
        raise ValueError('Prepared recording hash mismatch')
    config = args.main / 'hope_ws/src/hope_planner_cpp/config'
    hardware = config / 'model21800_hardware.yaml'
    packetizer = config / 'model21800_flight_packetizer.yaml'
    receipt = dict(contract=contract, harness_sha=git(harness, 'rev-parse', 'HEAD'),
                   contract_sha256=digest(Path(__file__).with_name('contract.json')),
                   prepared_sha256=digest(args.prepared / 'manifest.json'),
                   observations_sha256=digest(observation_path),
                   profiles={str(p): digest(p) for p in (hardware, packetizer)},
                   binaries={name: digest(args.build / name) for name in ('main_replay', 'v2_replay')},
                   platform=platform.platform(), started_ns=time.time_ns(), runs=[],
                   scope='Offline virtual-clock prediction queries; no ROS, packet transmission or robot execution')
    (args.output / 'freeze.json').write_text(json.dumps(receipt, indent=2) + '\n')
    inputs = {}
    try:
        with observation_path.open() as stream:
            for line in stream:
                row = json.loads(line)
                name = row['recording_id']
                if name not in inputs:
                    inputs[name] = (args.output / (name + '.csv')).open('w')
                ball = row['streams']['ball']
                q = ball['quaternion_xyzw'] if ball['orientation_available'] else [0, 0, 0, 0]
                values = [row['source_index'], row['source_time_ns'], int(ball['available']),
                          *(ball['position_m'] or [0, 0, 0]), int(ball['orientation_available']), *q]
                inputs[name].write(','.join(map(str, values)) + '\n')
    finally:
        for stream in inputs.values():
            stream.close()
    # Development first, held-out take last; no tuning between runs.
    for name in sorted(inputs):
        source = args.output / (name + '.csv')
        for binary in ('main_replay', 'v2_replay'):
            command = [str(args.build / binary)]
            if binary == 'main_replay':
                command += [str(hardware), str(packetizer)]
            target = args.output / (name + '.' + binary + '.jsonl')
            stderr = target.with_suffix('.stderr')
            print('START', name, binary, flush=True)
            start = time.monotonic()
            with source.open() as stdin, target.open('w') as stdout, stderr.open('w') as err:
                p = subprocess.run(command, stdin=stdin, stdout=stdout, stderr=err)
            result = dict(recording=name, binary=binary, command=command, exit_code=p.returncode,
                          duration_s=time.monotonic() - start, input_sha256=digest(source),
                          output_sha256=digest(target), stderr_sha256=digest(stderr))
            receipt['runs'].append(result)
            (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            print('RESULT', name, binary, p.returncode, result['duration_s'], flush=True)
            if p.returncode:
                raise RuntimeError('Replay failed; original outputs retained')
    receipt['completed_ns'] = time.time_ns()
    receipt['source_unchanged'] = all(git(root, 'rev-parse', 'HEAD') == pin and not git(root, 'status', '--porcelain')
        for root, pin in ((args.main, contract['main_sha']), (args.v2, contract['v2_sha'])))
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('main', 'v2', 'build', 'prepared', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    run(parser.parse_args())
