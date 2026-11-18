"""Best-effort, bounded output discovery; never authorship or acceptance evidence."""
import hashlib
import os
from pathlib import Path
import re
import stat
import time

# These are discovery limits, not limits on the task or on explicit checkpoints.
MAX_FILES = 4000
MAX_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024
SECONDS = 3
SKIP_DIRS = {'.git', '.pi-ping-pong', 'node_modules', '.venv', 'venv', '__pycache__', '.cache'}


def service_path(path):
    parts = Path(path).parts
    return '.pi-ping-pong' in parts or any(pair in {('.pi', 'ping-pong'), ('.pi', 'reviewed-runs')} for pair in zip(parts, parts[1:]))


def private_path(path):
    return any(part.startswith('.') or re.search(
        r'(?:credential|secret|password|token|^auth(?:\.|$)|^id_rsa|^id_ed25519|\.(?:pem|key|p12|pfx|keystore)$|(?:^|[._-])(?:config|settings)(?:[._-]|$)|local.*config)',
        part, re.I) for part in Path(path).parts)


def worker_directory(c):
    target = c.get('execution_contract', {}).get('target')
    if not isinstance(target, str) or not Path(target).is_absolute():
        return Path(c['root']) / 'work'
    path = Path(target).resolve()
    while not path.is_dir() and path != path.parent:
        path = path.parent
    return path


def roots(c):
    paths = [str((Path(c['root']) / 'work').resolve())]
    target = c.get('execution_contract', {}).get('target')
    if isinstance(target, str) and Path(target).is_absolute():
        paths.append(str(Path(target).absolute() if Path(target).is_symlink() else Path(target).resolve()))
    return list(dict.fromkeys(paths))


def snapshot(c):
    started, used, seen = time.monotonic(), 0, 0
    files, limitations = {}, set()
    scopes = roots(c)
    for scope in scopes:
        pending = [Path(scope)]
        while pending:
            if seen >= MAX_FILES or used >= MAX_BYTES or time.monotonic() - started >= SECONDS:
                limitations.add('Discovery limit reached (4000 entries, 32 MiB, 1 MiB/file, 3 seconds); visibility is partial.')
                break
            path = pending.pop()
            seen += 1
            relative = path.relative_to(scope)
            if scope == scopes[0] and path.name in {'cycle-context.json', 'checkpoint.json'}:
                continue
            if (scope != scopes[0] and service_path(path)) or private_path(relative) or private_path(Path(path.name)) or path.name in SKIP_DIRS or path.is_symlink():
                limitations.add('Hidden/private paths, symlinks and dependency/cache directories are excluded from discovery.')
                continue
            try:
                info = path.lstat()
                if path.resolve() != path.absolute():
                    limitations.add('Symlinked paths omitted from discovery.')
                    continue
                if stat.S_ISDIR(info.st_mode):
                    with os.scandir(path) as entries:
                        for entry in entries:
                            if seen + len(pending) >= MAX_FILES or time.monotonic() - started >= SECONDS:
                                limitations.add('Directory enumeration limit reached; visibility is partial.')
                                break
                            pending.append(Path(entry.path))
                    continue
                if not stat.S_ISREG(info.st_mode):
                    continue
                if info.st_size > MAX_FILE_BYTES or used + info.st_size > MAX_BYTES:
                    limitations.add('Large files omitted; discovery is limited to 1 MiB/file and 32 MiB total.')
                    continue
                # O_NOFOLLOW prevents a final-component symlink swap.
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode):
                        continue
                    data = stream.read(MAX_FILE_BYTES + 1)
                    after = os.fstat(stream.fileno())
                used += len(data)
                if len(data) > MAX_FILE_BYTES or (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    limitations.add('Files changing during discovery omitted; concurrent edits remain possible.')
                    continue
                files[str(path.absolute())] = hashlib.sha256(data).hexdigest()
            except FileNotFoundError:
                if path != Path(scope):
                    limitations.add('Files disappeared during discovery; visibility is partial.')
            except OSError:
                limitations.add('Some scoped paths could not be read; visibility is partial.')
    return dict(run_id=c['run_id'], roots=scopes, files=files, limitations=sorted(limitations))


def changes(c, baseline):
    current = snapshot(c)
    valid = isinstance(baseline, dict) and baseline.get('run_id') == c['run_id'] and baseline.get('roots') == roots(c) and isinstance(baseline.get('files'), dict)
    previous = baseline['files'] if valid else {}
    candidates = {name: value for name, value in current['files'].items() if previous.get(name) != value}
    limitations = current['limitations'] + (baseline.get('limitations', []) if valid else ['Baseline missing or mismatched; existing files are candidates of unknown origin, not established new changes.'])
    limitations.append('Discovery compares only the bounded authorized target and work subset with launch hashes, not a per-cycle snapshot. Candidates can include user/concurrent edits; no authorship, test execution or acceptance is inferred. Private/hidden, symlinked, dependency/cache and oversized files may remain undiscovered.')
    return candidates, list(dict.fromkeys(limitations))
