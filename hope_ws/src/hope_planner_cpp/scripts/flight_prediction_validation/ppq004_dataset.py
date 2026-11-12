"""Lossless PPQ004 frame adapter. No predictions or annotation labels enter it."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np

SCHEMA = 'ppq004-observation-v1'
FRAME = 'ppq004_table_corner'
CALIBRATION = 'ppq004_20261020_recorded_table_corner'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source_ns(seconds, epoch_ns=0):
    """Round the recorded relative time BEFORE adding an integer epoch."""
    if not np.isfinite(seconds) or not isinstance(epoch_ns, int):
        raise ValueError('finite relative time and integer epoch required')
    value = int(round(float(seconds) * 1_000_000_000)) + epoch_ns
    if not -(2**63) <= value < 2**63:
        raise ValueError('source time exceeds signed int64')
    return value


def quaternion_equivalent(a, b, atol=1e-12):
    a, b = np.asarray(a), np.asarray(b)
    return bool(np.allclose(a, b, rtol=0, atol=atol) or
                np.allclose(a, -b, rtol=0, atol=atol))


def finite_list(value):
    value = np.asarray(value)
    return value.tolist() if np.isfinite(value).all() else None


def observations(data, part, parent_hash, epoch_ns=0):
    """Yield every NPZ frame, including unavailable Ball; preserve raw ordering."""
    previous = None
    rate = float(data['rate'])
    if rate != 300.0:
        raise ValueError('PPQ004 frame schedule must be 300 Hz')
    for index, time in enumerate(data['t']):
        ns = source_ns(time, epoch_ns)
        ordering = ('first' if previous is None else 'duplicate' if ns == previous
                    else 'backstep' if ns < previous else 'in_order')
        row = dict(schema=SCHEMA, evidence_type='measured_recording',
                   recording_id=f'ppq004_part{part}', session_id=f'ppq004_part{part}',
                   split='benchmark_holdout' if part == 3 else 'development',
                   source_index=index, original_frame=int(round(float(time)*rate)),
                   original_time_s=float(time), source_time_ns=ns, sequence=index+1,
                   epoch_ns=epoch_ns, clock_domain='recorded_virtual',
                   clock_mapping_id=f'ppq004_part{part}_integer_epoch_{epoch_ns}',
                   clock_uncertainty_s=0.0, clock_authority='virtual_replay_fixture',
                   frame_id=FRAME, calibration_id=CALIBRATION, ball_id='Ball',
                   parent_sha256=parent_hash, ordering=ordering, streams={})
        for name in ('ball', 'base', 'p1', 'p2'):
            if name+'_present' not in data:
                row['streams'][name] = dict(available=False, position_m=None,
                    quaternion_xyzw=None, orientation_available=False,
                    control_point_authorized=False)
                continue
            present = bool(data[name+'_present'][index])
            key = 'ball_pos' if name == 'ball' else name+'_centroid'
            position = finite_list(data[key][index]) if present else None
            q = finite_list(data[name+'_quat'][index]) if present else None
            orientation = q is not None and abs(float(np.linalg.norm(q))-1) < 1e-6
            rms = float(data[name+'_rms'][index])
            row['streams'][name] = dict(available=present and position is not None,
                position_m=position, quaternion_xyzw=q,
                orientation_available=orientation, angular_velocity_authorized=False,
                control_point_authorized=name == 'ball',
                position_convention='ball_center' if name == 'ball' else 'marker_centroid',
                marker_to_control_extrinsic=None,
                rigid_rms_m=rms if np.isfinite(rms) else None)
        # Source frame identity remains stable under downstream derivatives.
        payload = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
        row['source_frame_sha256'] = hashlib.sha256(payload.encode()).hexdigest()
        yield row
        previous = ns


def check_csv(data, csv):
    present = data['ball_present'] & np.isfinite(data['ball_pos']).all(axis=1)
    expected = np.column_stack((data['t'][present], data['ball_pos'][present],
                                data['ball_quat'][present]))
    actual = np.loadtxt(csv, delimiter=',', ndmin=2)
    if actual.shape != expected.shape or not np.array_equal(actual, expected, equal_nan=True):
        raise ValueError(f'CSV/NPZ round trip differs: {csv}')
    return len(actual)
