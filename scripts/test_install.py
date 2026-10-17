#!/usr/bin/env python3
"""Exercise installer file allowlisting in an isolated synthetic fixture."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys


REQUIRED = (
    'package.json',
    'package-lock.json',
    'pyproject.toml',
    'uv.lock',
    'tsconfig.json',
    'scripts/check.sh',
    '.githooks/pre-commit',
    'eslint.config.mjs',
)
PRIVATE = ('.pi-ping-pong', 'node_modules', '.venv', '.git', '.pytest_cache', 'dist')
UNRELATED = (
    'auth.json',
    '.env.json',
    'local.toml',
    'private.lock',
    'nested/config.json',
    'nested/settings.toml',
    'nested/private.lock',
    'nested/.env.json',
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-root', type=Path, required=True)
    args = parser.parse_args()
    fixture = args.fixture_root.resolve()
    if fixture.exists():
        shutil.rmtree(fixture)
    fixture.mkdir(parents=True)
    source = Path(__file__).resolve().parent.parent
    synthetic = fixture / 'source'
    shutil.copytree(
        source,
        synthetic,
        ignore=shutil.ignore_patterns('.git', 'node_modules', '.venv', '.pi-ping-pong', '.ruff_cache'),
    )
    for relative in UNRELATED:
        path = synthetic / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic private config\n', encoding='utf-8')
    result = subprocess.run(
        [
            sys.executable,
            str(synthetic / 'scripts/install.py'),
            '--skills-dir',
            str(fixture / 'skills'),
            '--extensions-dir',
            str(fixture / 'extensions'),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise SystemExit(f'installer failed ({result.returncode}): {result.stderr}')
    installed = fixture / 'skills/pi-ping-pong'
    missing = [path for path in REQUIRED if not (installed / path).is_file()]
    if missing:
        raise SystemExit(f'missing required tooling files: {missing}')
    bad_modes = [
        path for path in ('scripts/check.sh', '.githooks/pre-commit')
        if not (installed / path).stat().st_mode & 0o111
    ]
    if bad_modes:
        raise SystemExit(f'executable mode not preserved: {bad_modes}')
    leaked = [path for path in UNRELATED if (installed / path).exists()]
    if leaked:
        raise SystemExit(f'unrelated/private configs copied: {leaked}')
    excluded = [path for path in PRIVATE if (installed / path).exists()]
    if excluded:
        raise SystemExit(f'private/generated paths copied: {excluded}')
    print('installer allowlist, required tooling, executable modes, and privacy exclusions: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
