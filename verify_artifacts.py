"""Verify published archive parts, reconstructed bytes and every manifested member."""
import argparse, hashlib, io, json, re, tarfile
from pathlib import Path

SECRET = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[A-Z0-9]{16})')

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

class Parts(io.RawIOBase):
    def __init__(self, paths):
        self.paths = iter(paths)
        self.current = None
    def readable(self): return True
    def readinto(self, target):
        while True:
            if self.current is None:
                path = next(self.paths, None)
                if path is None: return 0
                self.current = path.open('rb')
            count = self.current.readinto(target)
            if count: return count
            self.current.close()
            self.current = None
    def close(self):
        if self.current: self.current.close()
        super().close()

def main():
    p = argparse.ArgumentParser(); p.add_argument('root', type=Path); p.add_argument('--output', type=Path, required=True); args = p.parse_args()
    groups = json.loads((args.root / 'archives.json').read_text())
    reports = []
    for group in groups:
        paths = [args.root / x['file'] for x in group['parts']] if 'parts' in group else [args.root / group['archive']]
        if 'parts' in group:
            for part, path in zip(group['parts'], paths):
                assert path.stat().st_size == part['bytes'] and sha(path) == part['sha256'], path
        h = hashlib.sha256(); count = 0
        for path in paths:
            with path.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    count += len(block); h.update(block)
        assert count == group['bytes'] and h.hexdigest() == group['sha256'], group['archive']
        mp = args.root / (group['archive'].removesuffix('.tar.gz') + '.manifest.json')
        expected = {x['path']: x for x in json.loads(mp.read_text())['files']} if mp.exists() else None
        seen = set(); scanned = 0
        with io.BufferedReader(Parts(paths)) as raw, tarfile.open(fileobj=raw, mode='r|gz') as archive:
            for member in archive:
                if not member.isfile(): continue
                assert member.name not in seen, member.name
                seen.add(member.name)
                if expected is not None: assert member.name in expected, member.name
                stream = archive.extractfile(member); digest = hashlib.sha256(); size = 0; previous = b''
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    assert not SECRET.search(previous + block), ('credential-like value: manual review required', member.name)
                    digest.update(block); size += len(block); previous = block[-256:]
                scanned += size
                if expected is not None:
                    entry = expected[member.name]
                    assert size == entry['bytes'] and digest.hexdigest() == entry['sha256'], member.name
        if expected is not None: assert set(expected) == seen
        reports.append(dict(archive=group['archive'],sha256=group['sha256'],members=len(seen),uncompressed_bytes=scanned,status='PASS',all_members_manifested=expected is not None))
        print(group['archive'], len(seen), 'PASS', flush=True)
    for line in (args.root / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert sha(args.root / name) == digest, name
    args.output.write_text(json.dumps(dict(status='PASS',archives=reports,credential_pattern_scan='No matches in archived file contents',limitations='Pattern scan is not an exhaustive secret audit'),indent=2)+'\n')

if __name__ == '__main__': main()
