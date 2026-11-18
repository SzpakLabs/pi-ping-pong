"""Read-only launch Git record and start→current line diff: Reviewer facts, never a verdict or authorship."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import action_protocol as p
import output_snapshot as outputs

MAX_FILES = 200
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024
MAX_DIFF_BYTES = 256 * 1024
SECONDS = 5
RECORD = 'launch-git.json'
REF = 'launch-diff'
NOTE = ('Core fact, not a verdict: launch state = recorded HEAD + the user\'s uncommitted launch edits (git diff HEAD) and untracked text. '
        'Authorship of later changes is not established; the user may have edited concurrently. '
        'Files clean at launch are not listed. Omitted, truncated or unreconstructable files are unknown, not unchanged.')


def git(cwd, args, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Git launch record deadline reached')
    # Read-only forms only: no index refresh/lock, fsmonitor hooks, external diff or textconv.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', LC_ALL='C')
    return subprocess.run(['git', '-c', 'core.fsmonitor=false', *args], cwd=cwd, env=env, capture_output=True, timeout=remaining)


def checked(cwd, args, deadline):
    result = git(cwd, args, deadline)
    if result.returncode:
        raise RuntimeError('git ' + args[0] + ' failed: ' + result.stderr.decode(errors='replace').strip()[:300])
    return result.stdout


def safe_text(data):
    """Same conservative filters as partial-result retention; None means omit."""
    if b'\0' in data or re.search(rb'(?:password|passwd|private[_-]?key)\s*[:=]\s*\S+', data, re.I):
        return None
    try:
        value = data.decode('utf-8')
        for line in value.splitlines():
            if line.strip():
                p.text(line)
    except (UnicodeError, ValueError):
        return None
    return value


def private(relative):
    path = Path(relative)
    return outputs.private_path(path) or any(part in outputs.SKIP_DIRS for part in path.parts)


def read_regular(path):
    info = path.lstat()
    p.require(not path.is_symlink() and path.is_file(), 'not a regular file')
    p.require(info.st_size <= MAX_FILE_BYTES, 'oversized')
    return path.read_bytes()


def record(c):
    """Return the launch record, or None for a non-filesystem target. Raises on git error/timeout."""
    target = c.get('execution_contract', {}).get('target')
    if not isinstance(target, str) or not Path(target).is_absolute():
        return None
    target = Path(target).resolve()
    cwd = target if target.is_dir() else target.parent
    base = dict(run_id=c['run_id'], target=str(target), status='not_git', files={}, omitted={}, truncated=False, limitations=[])
    if not cwd.is_dir():
        return {**base, 'limitations': ['Target directory unavailable at launch.']}
    deadline = time.monotonic() + SECONDS
    top = git(cwd, ['rev-parse', '--show-toplevel'], deadline)
    if top.returncode:
        return {**base, 'limitations': ['Target is not inside a Git repository; no launch content record.']}
    top = Path(top.stdout.decode().strip()).resolve()
    head = git(top, ['rev-parse', '--verify', '-q', 'HEAD^{commit}'], deadline)
    if head.returncode:
        return {**base, 'status': 'no_head', 'limitations': ['Git repository has no HEAD commit; no launch content record.']}
    relative = target.relative_to(top).as_posix() if target != top else '.'
    spec = ':(literal)' + relative
    value = {**base, 'status': 'recorded', 'top': str(top), 'head': head.stdout.decode().strip(), 'scope': relative}
    tracked = []
    for entry in checked(top, ['diff', 'HEAD', '--numstat', '-z', '--no-renames', '--no-ext-diff', '--no-textconv', '--', spec], deadline).split(b'\0'):
        if entry:
            added, _, name = entry.decode('utf-8', 'surrogateescape').split('\t', 2)
            tracked.append((name, added == '-'))
    untracked = [name.decode('utf-8', 'surrogateescape') for name in checked(top, ['ls-files', '-o', '--exclude-standard', '-z', '--', spec], deadline).split(b'\0') if name]
    used = 0
    for name, binary in [(n, b) for n, b in tracked] + [(n, None) for n in untracked]:
        if outputs.service_path(top / name):
            continue
        scoped = Path(name).relative_to(relative) if relative != '.' else Path(name)
        if private(scoped) or private(Path(name).name):
            value['omitted'][name] = 'private/hidden/configuration path not recorded'
            continue
        if len(value['files']) >= MAX_FILES or len(value['omitted']) >= MAX_FILES or used >= MAX_TOTAL_BYTES:
            value['truncated'] = True
            value['limitations'].append('Launch record limit reached; remaining launch-dirty/untracked files are unlisted and their start state is unknown.')
            break
        try:
            path = top / name
            current = read_regular(path) if path.exists() or path.is_symlink() else None
            if binary:
                raise ValueError('binary')
            if binary is None:
                text = safe_text(current or b'')
                p.require(text is not None, 'binary or potentially private content')
                item = dict(kind='untracked', sha256=hashlib.sha256(current).hexdigest(), content=text)
                used += len(current)
            else:
                patch = checked(top, ['diff', 'HEAD', '--no-color', '--no-ext-diff', '--no-textconv', '--no-renames', '--', ':(literal)' + name], deadline)
                p.require(len(patch) <= MAX_FILE_BYTES, 'oversized patch')
                text = safe_text(patch)
                p.require(text is not None, 'binary or potentially private patch')
                item = dict(kind='tracked', sha256=None if current is None else hashlib.sha256(current).hexdigest(), patch=text)
                used += len(patch)
            value['files'][name] = item
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            value['omitted'][name] = 'not recorded: ' + str(error)[:300]
    if value['omitted']:
        value['limitations'].append('Some launch-dirty/untracked files were not recorded (private, binary, oversized or limit); their start state is unknown.')
    return value


def split(text):
    return re.findall(r'[^\n]*\n|[^\n]+\Z', text)


def apply(old, patch):
    """Apply one exact git hunk set (no fuzz) to old text."""
    lines = split(patch)
    if any(line.startswith(('new file mode', '--- /dev/null')) for line in lines):
        old = ''
    old, out, i, previous = split(old), [], 0, None
    hunks = False
    for line in lines:
        if line.startswith('@@'):
            match = re.match(r'@@ -(\d+)(?:,(\d+))? ', line)
            p.require(match is not None, 'malformed hunk')
            start = int(match[1]) - (0 if match[2] == '0' else 1)
            p.require(start >= i, 'overlapping hunk')
            out += old[i:start]
            i, hunks = start, True
        elif not hunks:
            continue
        elif line.startswith('\\'):
            if previous in (' ', '+') and out:
                out[-1] = out[-1].rstrip('\n')
        elif line[:1] in (' ', '-'):
            p.require(i < len(old) and old[i].rstrip('\n') == line[1:].rstrip('\n'), 'patch does not match launch HEAD blob')
            if line[0] == ' ':
                out.append(old[i])
            i += 1
        elif line[:1] == '+':
            out.append(line[1:])
        previous = line[:1]
    return ''.join(out + old[i:])


def build(c, root, directory):
    """Write directory/launch-diff.txt and return request metadata; never raises for unavailable facts."""
    meta = dict(coverage='unknown', files={}, truncated=False, limitations=[])
    try:
        value = json.loads((Path(root) / RECORD).read_text())
    except (OSError, ValueError):
        meta['limitations'].append('No launch Git record (non-filesystem target, resumed older run or unavailable at launch); start→current preservation is unknown.')
        return meta
    target = c.get('execution_contract', {}).get('target')
    if not isinstance(value, dict) or value.get('run_id') != c['run_id'] or not isinstance(target, str) or value.get('target') != str(Path(target).resolve()):
        meta['limitations'].append('Launch Git record mismatched; start→current preservation is unknown.')
        return meta
    meta['limitations'].extend(value.get('limitations', []))
    if value.get('status') != 'recorded':
        return meta
    meta['truncated'] = bool(value.get('truncated'))
    top, deadline = Path(value['top']), time.monotonic() + SECONDS
    body, used = [], 0
    for name, reason in sorted(value['omitted'].items()):
        meta['files'][name] = dict(status='unknown', reason=reason)
    for name, item in sorted(value['files'].items()):
        try:
            path = top / name
            current = read_regular(path) if path.exists() or path.is_symlink() else None
            if (None if current is None else hashlib.sha256(current).hexdigest()) == item['sha256']:
                meta['files'][name] = dict(status='unchanged')
                continue
            if item['kind'] == 'untracked':
                before = item['content']
            else:
                blob = git(top, ['cat-file', 'blob', value['head'] + ':' + name], deadline)
                old = blob.stdout.decode('utf-8') if blob.returncode == 0 else ''
                # A file deleted at launch has no start content.
                before = '' if item['sha256'] is None else apply(old, item['patch'])
                p.require(item['sha256'] is None or hashlib.sha256(before.encode()).hexdigest() == item['sha256'], 'reconstruction does not match launch content hash')
            after = safe_text(current or b'')
            p.require(after is not None, 'current content binary or potentially private')
            delta = list(difflib.unified_diff(split(before), split(after), 'launch/' + name, ('current/' if current is not None else 'deleted/') + name))
            removed = sum(1 for line in delta[2:] if line.startswith('-'))
            text = ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in delta)
            if used + len(text.encode()) > MAX_DIFF_BYTES:
                meta['truncated'] = True
                meta['files'][name] = dict(status='unknown', reason='diff size limit reached', removed_lines=removed)
                continue
            used += len(text.encode())
            body.append(text)
            meta['files'][name] = dict(status='changed' if current is not None else 'deleted', removed_lines=removed)
        except (OSError, ValueError, UnicodeError, TimeoutError, subprocess.SubprocessError) as error:
            meta['files'][name] = dict(status='unknown', reason=str(error)[:300])
    meta['coverage'] = 'partial' if meta['truncated'] or any(v['status'] == 'unknown' for v in meta['files'].values()) else 'complete'
    header = [NOTE, f'HEAD at launch: {value["head"]}; scope: {value["scope"]}; coverage: {meta["coverage"]}; truncated: {str(meta["truncated"]).lower()}.']
    header += [f'{name}: {v["status"]}' + (f', removed_lines={v["removed_lines"]}' if 'removed_lines' in v else '') + (f' ({v["reason"]})' if 'reason' in v else '') for name, v in sorted(meta['files'].items())]
    header += meta['limitations'] or []
    path = Path(directory) / 'launch-diff.txt'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('\n'.join('# ' + line for line in header) + '\n' + ''.join(body))
        stream.flush()
        os.fsync(stream.fileno())
    meta.update(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return meta
