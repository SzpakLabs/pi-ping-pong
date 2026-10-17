#!/usr/bin/env python3
"""Install only this skill and its Pi receiver, preserving differing old files."""
import argparse
from pathlib import Path
import shutil
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', type=Path, default=Path.home() / '.agents/skills')
    parser.add_argument('--extensions-dir', type=Path, default=Path.home() / '.pi/agent/extensions')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    target = args.skills_dir.expanduser().resolve() / 'pi-ping-pong'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')

    def copy_file(src, dst):
        if dst.exists() and src.read_bytes() == dst.read_bytes():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            backup = dst.with_name(dst.name + '.backup-' + stamp)
            shutil.copy2(dst, backup)
        shutil.copy2(src, dst)

    if source != target:
        for src in source.rglob('*'):
            relative = src.relative_to(source)
            if any(part in {'.git', '__pycache__', 'node_modules', 'runs', 'data', '.pi-ping-pong'} for part in relative.parts):
                continue
            if src.is_file() and (src.suffix in {'.md', '.py', '.mjs', '.ts', '.yaml'} or src.name in {'.gitignore', 'LICENSE'}):
                copy_file(src, target / relative)
    receiver = args.extensions_dir.expanduser().resolve() / 'pi-reviewed.ts'
    copy_file(source / 'extensions/pi-reviewed.ts', receiver)
    print(f'Skill: {target}\nPi receiver: {receiver}\nReload Pi before new launches.')


if __name__ == '__main__':
    main()
