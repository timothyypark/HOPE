"""Prepare a fresh, hash-bound full-frame dataset without labeling predictor truth."""
import argparse
import json
from pathlib import Path
import numpy as np
from ppq004_dataset import observations, sha256, check_csv


def prepare(source, archive, output):
    source, archive, output = map(Path, (source, archive, output))
    entries = json.loads((archive/'manifest.json').read_text())
    for entry in entries:
        raw = source/entry['path'][:-3]
        if sha256(raw) != entry['sha256'] or raw.stat().st_size != entry['bytes']:
            raise ValueError(f'source archive mismatch: {raw}')
        if sha256(archive/entry['path']) != entry['compressed_sha256']:
            raise ValueError(f'compressed archive mismatch: {entry["path"]}')
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema='ppq004-prepared-v1', archive_manifest_sha256=sha256(archive/'manifest.json'),
                    recordings=[], annotation_status='UNREVIEWED', files={})
    with (output/'observations.jsonl').open('w') as stream:
        for part in (1, 2, 3):
            path = source/f'fit/part{part}/raw_extracted.npz'
            with np.load(path, allow_pickle=False) as packed:
                # NpzFile indexing decompresses an entire member on every access.
                # Materialize only the streams used here once, not once per frame.
                data = {key: packed[key] for key in packed.files
                        if key in ('t', 'rate', 'ball_pos') or
                        key.endswith(('_present', '_centroid', '_quat', '_rms'))}
                count = check_csv(data, source/f'trajectories/part{part}.csv')
                available = 0
                for row in observations(data, part, sha256(path)):
                    available += row['streams']['ball']['available']
                    stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n')
                if available != count:
                    raise ValueError('frame/CSV availability mismatch')
                manifest['recordings'].append(dict(part=part, parent_sha256=sha256(path),
                    frames=len(data['t']), tracked_ball=count, rate_hz=float(data['rate']),
                    split='benchmark_holdout' if part == 3 else 'development'))
    # Archive contacts are candidate evidence, not reviewed state labels.
    with (output/'annotation_candidates.jsonl').open('w') as stream:
        for part in (1, 2, 3):
            ledger=source/f'fit/part{part}/contact_position_ledger.json'
            for i, candidate in enumerate(json.loads(ledger.read_text())['candidates']):
                row=dict(candidate_id=f'part{part}:contact:{i}', recording_id=f'ppq004_part{part}',
                         evidence_type='measured_recording', review_status='UNREVIEWED',
                         ledger_sha256=sha256(ledger), candidate=candidate)
                stream.write(json.dumps(row, allow_nan=False)+'\n')
    (output/'episodes.jsonl').write_text('')  # No fabricated physical boundaries.
    manifest['frames']=sum(r['frames'] for r in manifest['recordings'])
    manifest['tracked_ball']=sum(r['tracked_ball'] for r in manifest['recordings'])
    if (manifest['frames'], manifest['tracked_ball']) != (146931, 102275):
        raise ValueError('verified PPQ004 counts differ')
    for name in ('observations.jsonl','episodes.jsonl','annotation_candidates.jsonl'):
        manifest['files'][name]=sha256(output/name)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.archive,args.output),indent=2))


if __name__=='__main__': main()
