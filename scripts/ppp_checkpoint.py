#!/usr/bin/env python3
"""Optional Worker helper: write work/checkpoint.json with Core identity and resolved evidence, then run Core's check."""
import argparse
import filecmp
import os
from pathlib import Path
import shutil
import sys

from action_protocol import envelope
from bridge import atomic, inside, read, validate_checkpoint


def resolve(name, work, target):
    raw = Path(name).expanduser()
    if raw.is_absolute():
        candidates = [raw]
    else:
        candidates = [work / raw]
        if target:
            candidates.append(target / raw)
        candidates.append(Path.cwd() / raw)
        if raw.parts[:1] == ('work',):
            candidates.append(work.joinpath(*raw.parts[1:]))
    found = next((path.resolve() for path in candidates if path.is_file()), None)
    if found is None:
        raise ValueError(f'Evidence file not found: {name!r}; tried {", ".join(map(str, candidates))}')
    if found.is_relative_to(work.resolve()):
        return found.relative_to(work.resolve()).as_posix()
    if target and found.is_relative_to(target.resolve()):
        return str(found)
    inside(Path('/'), found)  # refuses secret-like paths (.env*, auth.json, credentials.json) before copying
    if any(part in {'.ssh', '.aws', '.gnupg', '.netrc', '.npmrc'} for part in found.parts) or found.suffix in {'.pem', '.key'}:
        raise ValueError('Secret-bearing paths must not be checkpoint evidence')
    copy = work / 'evidence' / found.name
    index = 1
    while copy.exists() and not (copy.is_file() and filecmp.cmp(copy, found, shallow=False)):
        copy = copy.with_name(f'{found.stem}-{index}{found.suffix}')
        index += 1
    copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(found, copy)
    return copy.relative_to(work).as_posix()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', required=True, choices=['progress', 'ready', 'needs_human'])
    parser.add_argument('--summary', required=True)
    parser.add_argument('--next-step', default='')
    parser.add_argument('--reason-code')
    parser.add_argument('evidence', nargs='*')
    args = parser.parse_args(argv)
    try:
        work = Path(os.environ['PPP_WORK_DIR'])
        c = {**read(work.parent / 'config.json'), 'root': str(work.parent)}
        ctx = read(work / 'cycle-context.json')
        target = c['execution_contract'].get('target')
        target = Path(target) if isinstance(target, str) and Path(target).is_absolute() else None
        limit = c.get('max_evidence_files', 20)
        if len(args.evidence) > limit:
            raise ValueError(f'{len(args.evidence)} evidence files exceed max_evidence_files={limit}; pass the most relevant ones or an index file')
        evidence = list(dict.fromkeys(resolve(name, work, target) for name in args.evidence))
        cp = dict(protocol_version=2, schema_version=1, run_id=ctx['run_id'], cycle=ctx['cycle'], action_id=ctx['action_id'],
                  status=args.status, summary=args.summary, evidence=evidence, next_step=args.next_step)
        if args.reason_code:
            cp['reason_code'] = args.reason_code
        path = work / 'checkpoint.json'
        previous = path.read_bytes() if path.is_file() else None
        atomic(path, cp)
        try:
            written, _ = validate_checkpoint(c, ctx['cycle'])
            envelope(written, c['run_id'])
        except Exception:
            # Keep the earlier checkpoint rather than leaving a rejected one in its place.
            if previous is None:
                path.unlink()
            else:
                temp = path.with_name(path.name + '.restore')
                temp.write_bytes(previous)
                temp.replace(path)
            raise
    except (KeyError, ValueError, OSError) as error:
        print(f'Checkpoint helper error: {error}', file=sys.stderr)
        return 2
    print(f'OK {work / "checkpoint.json"}: status={args.status}, evidence={evidence}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
