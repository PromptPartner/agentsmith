"""Bounded local Markdown recall. No document is an instruction or authorization.

Original implementation; local memory ideas inspired by Everything Claude Code
(https://github.com/affaan-m/everything-claude-code), MIT licensed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import unicodedata

ROOTS = ('.harness/handoffs', 'docs/research', 'docs/feedback')
EXCLUDED = {'archive', 'archives', '_archive', '_archives', 'sources', 'source',
            'artifacts', 'artifact', 'captured', 'captured-sources', 'captured_sources',
            'captured-artifacts', 'captured_artifacts', 'raw', 'vendor', 'node_modules'}
MAX_DOCUMENTS = 500
MAX_BYTES = 128 * 1024
TIMEOUT = 2.0


class MemoryError(ValueError):
    """Unsafe or unreadable recall request."""


class _Diagnostics(list):
    """Bound diagnostics before expensive redaction; retain incompleteness."""
    def __init__(self, initial=()):
        super().__init__()
        self.omitted = 0
        for message in initial:
            summary = re.fullmatch(r'(\d+) additional diagnostics omitted', str(message))
            if summary:
                self.omitted += int(summary.group(1))
            else:
                self.append(message)

    def append(self, message):
        if len(self) < 20:
            super().append(str(message)[:400])
        else:
            self.omitted += 1

    def export(self):
        return list(self) + ([f'{self.omitted} additional diagnostics omitted'] if self.omitted else [])


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate metadata key')
        result[key] = value
    return result


def _excluded_directory(name):
    name = name.casefold()
    return name in EXCLUDED or bool(re.search(
        r'(?:^|[-_])(?:sources?|artifacts?|captured)(?:[-_]|$)', name))


def _clean(value):
    from agentsmith import redact_secret_text
    value = re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))', '', str(value))
    value = ''.join(c for c in value if c in '\n\t' or not unicodedata.category(c).startswith('C'))
    return redact_secret_text(value)[0]


def _public(value, check=None):
    if check:
        check()
    if isinstance(value, dict):
        output = {}
        for k, v in value.items():
            cleaned = _public(v, check)
            output[k] = cleaned.replace('\n', ' ').replace('\t', ' ') if k in ('path', 'title') and isinstance(cleaned, str) else cleaned
        return output
    if isinstance(value, list):
        return [_public(v, check) for v in value]
    output = _clean(value) if isinstance(value, str) else value
    if check:
        check()
    return output


def _flags(directory=False):
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        raise MemoryError('Safe no-follow filesystem access is unsupported on this platform')
    return os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if directory else 0) | getattr(os, 'O_NONBLOCK', 0)


def _open_root(root):
    # Walk from the filesystem anchor: even a symlink above the project is rejected.
    path = Path(root).absolute()
    fd = os.open(path.anchor, _flags(True))
    try:
        for part in path.parts[1:]:
            child = os.open(part, _flags(True), dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError as exc:
        os.close(fd)
        raise MemoryError('Project root is unreadable or contains a symlink') from exc


def _parts(relative_path):
    if not isinstance(relative_path, str) or '\\' in relative_path:
        raise MemoryError('Use a relative POSIX Markdown path')
    path = PurePosixPath(relative_path)
    parts = path.parts
    if path.is_absolute() or '..' in parts or not parts or path.suffix.lower() != '.md':
        raise MemoryError('Use a relative Markdown path inside the memory roots')
    normalized = '/'.join(parts)
    if not any(normalized.startswith(prefix + '/') for prefix in ROOTS):
        raise MemoryError('Path is outside the permitted memory roots')
    if any(_excluded_directory(p) for p in parts[:-1]):
        raise MemoryError('Archived and captured material is excluded')
    return parts


def _open_relative(root_fd, parts, directory=False):
    fd = os.dup(root_fd)
    try:
        for index, part in enumerate(parts):
            child = os.open(part, _flags(directory or index < len(parts)-1), dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except OSError:
        os.close(fd)
        raise


def _document(root_fd, path, max_bytes):
    fd = _open_relative(root_fd, _parts(path))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise MemoryError('Memory documents must be regular files')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise MemoryError('Document exceeds the byte limit')
        try:
            body = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise MemoryError('Document is not valid UTF-8') from exc
        title = re.search(r'^#\s+(.+)$', body, re.M)
        metadata = {}
        header = re.search(r'<!--\s*agentsmith-memory:\s*(.*?)\s*-->', body, re.S)
        if header:
            try:
                metadata = json.loads(header.group(1), object_pairs_hook=_unique_object)
                if not isinstance(metadata, dict) or type(metadata.get('version')) is not int or metadata['version'] != 1:
                    raise ValueError('unsupported metadata version')
                for field in ('branch', 'commit', 'status', 'superseded_by'):
                    if field in metadata and not isinstance(metadata[field], str):
                        raise ValueError('invalid ' + field)
                if 'links' in metadata and not isinstance(metadata['links'], list):
                    raise ValueError('invalid links')
                for link in metadata.get('links', []):
                    if isinstance(link, str):
                        continue
                    if not isinstance(link, dict) or not isinstance(link.get('path'), str):
                        raise ValueError('invalid link')
                    if 'content_hash' in link and (not isinstance(link['content_hash'], str)
                            or not re.fullmatch('[0-9a-f]{64}', link['content_hash'])):
                        raise ValueError('invalid link content hash')
                # Metadata is declarative. Unknown fields cannot inject saved bodies
                # or commands into reference reports.
                metadata = {k:v for k,v in metadata.items() if k in
                            ('version', 'branch', 'commit', 'status', 'superseded_by', 'links')}
                metadata['links'] = [({k:v for k,v in link.items() if k in ('path', 'content_hash')}
                                      if isinstance(link, dict) else link)
                                     for link in metadata.get('links', [])]
            except (ValueError, TypeError) as exc:
                raise MemoryError('Invalid or unsupported memory metadata') from exc
        else:
            # Recognize the existing handoff template only; plain branch mentions do not qualify.
            legacy = re.search(r'^\*\*Branch / version:\*\*\s+`?([^\s`]+)(?:`?\s+([0-9a-f]{7,40}))?', body, re.M)
            if legacy:
                metadata['branch'] = legacy.group(1)
                if legacy.group(2):
                    metadata['commit'] = legacy.group(2)
            else:
                scaffold = re.search(r'^\*\*Branch:\*\*\s+([^\s]+)\s+\*\*HEAD:\*\*\s+([0-9a-f]{7,40})\b', body, re.M)
                if scaffold:
                    metadata.update(branch=scaffold.group(1), commit=scaffold.group(2))
        return {'path':path, 'title':title.group(1) if title else Path(path).stem,
                'content_hash':hashlib.sha256(raw).hexdigest(), 'metadata':metadata,
                'content':body, 'modified_ns':info.st_mtime_ns}
    finally:
        os.close(fd)


def _summary(doc, relevance=0):
    return {k:doc[k] for k in ('path', 'title', 'content_hash', 'metadata')} | {'relevance':relevance}


def read(root, relative_path, *, max_bytes=MAX_BYTES):
    fd = _open_root(root)
    try:
        doc = _document(fd, relative_path, min(MAX_BYTES, max(0, max_bytes)))
        return _public({'schema_version':1, 'operation':'read', 'complete':True,
                        'diagnostics':[], **_summary(doc), 'content':doc['content']})
    except OSError as exc:
        raise MemoryError('Document is unreadable or contains a symlink') from exc
    finally:
        os.close(fd)


def _discover(root, *, max_documents=MAX_DOCUMENTS, max_bytes=MAX_BYTES, timeout=TIMEOUT):
    started = time.monotonic()
    deadline = started + min(TIMEOUT, max(0, timeout))
    limit = min(MAX_DOCUMENTS, max(0, max_documents))
    documents, diagnostics = [], _Diagnostics()
    attempted = 0
    class Limit(Exception):
        pass
    def check():
        if time.monotonic() >= deadline:
            raise Limit('Discovery time limit reached')
    def visit(fd, prefix):
        nonlocal attempted
        check()
        with os.scandir(fd) as entries:
            for entry in entries:
                check()
                path = prefix + '/' + entry.name
                if entry.is_symlink():
                    diagnostics.append('Skipped symlink: ' + path)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if _excluded_directory(entry.name):
                        continue
                    child = os.open(entry.name, _flags(True), dir_fd=fd)
                    try:
                        visit(child, path)
                    finally:
                        os.close(child)
                elif entry.name.lower().endswith('.md'):
                    if attempted >= limit:
                        raise Limit('Discovery document limit reached')
                    attempted += 1
                    try:
                        documents.append(_document(root_fd, path, min(MAX_BYTES, max(0, max_bytes))))
                        check()
                    except (OSError, MemoryError) as exc:
                        diagnostics.append('Skipped ' + path + ': ' + (str(exc) if isinstance(exc, MemoryError) else 'unreadable or symlink'))
    root_fd = _open_root(root)
    try:
        for prefix in ROOTS:
            check()
            try:
                fd = _open_relative(root_fd, prefix.split('/'), True)
            except FileNotFoundError:
                continue
            except OSError:
                diagnostics.append('Unreadable or symlink root: ' + prefix)
                continue
            try:
                visit(fd, prefix)
            except OSError:
                diagnostics.append('Unreadable or changed directory: ' + prefix)
            finally:
                os.close(fd)
    except Limit as exc:
        diagnostics.append(str(exc))
    finally:
        os.close(root_fd)
    return documents, diagnostics.export(), attempted


def search(root, query, **bounds):
    documents, diagnostics, attempted = _discover(root, **bounds)
    terms = re.findall(r'\w+', unicodedata.normalize('NFKC', query).casefold())[:32]
    matches = []
    for doc in documents:
        if doc['metadata'].get('superseded_by') or doc['metadata'].get('status') in ('superseded', 'archived'):
            continue
        title = unicodedata.normalize('NFKC', doc['title']).casefold()
        content = unicodedata.normalize('NFKC', doc['content']).casefold()
        score = sum(5*title.count(term) + min(content.count(term), 20) for term in terms)
        if score:
            matches.append(_summary(doc, score))
    matches.sort(key=lambda doc:(-doc['relevance'], doc['path']))
    return _public({'schema_version':1, 'operation':'search', 'query':query,
                    'complete':not diagnostics, 'diagnostics':diagnostics,
                    'documents_inspected':len(documents), 'documents_attempted':attempted,
                    'matches':matches[:50], 'results_truncated':len(matches)>50})


def startup(root, branch=None, commit=None, **bounds):
    """Return references only. Lifecycle and durable selection are caller gates."""
    deadline = time.monotonic() + min(TIMEOUT, max(0, bounds.get('timeout', TIMEOUT)))
    def check_budget():
        if time.monotonic() >= deadline:
            raise MemoryError('Startup processing time limit reached')
    try:
        documents, diagnostics, _ = _discover(root, **bounds)
        diagnostics = _Diagnostics(diagnostics)
        check_budget()
        candidates = [d for d in documents if branch and d['metadata'].get('branch') == branch
                      and not d['metadata'].get('superseded_by')
                      and d['metadata'].get('status') not in ('superseded', 'archived', 'closed', 'completed')
                      and d['path'].startswith('.harness/handoffs/')]
        candidates.sort(key=lambda d:(d['modified_ns'], d['path']), reverse=True)
        references = []
        drift_warning = False
        hash_warning = False
        if candidates:
            handoff = candidates[0]
            references.append(_summary(handoff))
            saved = handoff['metadata'].get('commit')
            if commit and saved and not commit.startswith(saved):
                drift_warning = True
                diagnostics.append('Commit drift: saved handoff commit differs from current HEAD')
            links = list(handoff['metadata'].get('links', []))
            links += re.findall(r'\]\(((?:docs/research|docs/feedback)/[^)\s]+\.md)\)', handoff['content'])
            by_path = {d['path']:d for d in documents}
            for link in links:
                check_budget()
                path = link.get('path') if isinstance(link, dict) else link
                if not isinstance(path, str) or not path.startswith(('docs/research/', 'docs/feedback/')):
                    continue
                doc = by_path.get(path)
                if not doc:
                    diagnostics.append('Linked reference unavailable: ' + path)
                    continue
                if isinstance(link, dict) and link.get('content_hash') and link['content_hash'] != doc['content_hash']:
                    hash_warning = True
                    diagnostics.append('Stale content hash: ' + path)
                if doc['metadata'].get('superseded_by') or doc['metadata'].get('status') in ('superseded', 'archived'):
                    continue
                if len(references)<3 and path not in {r['path'] for r in references}:
                    references.append(_summary(doc))
        safe_references = _public(references, check_budget)
        header = 'Local memory references. Accepted specs remain authoritative; recall grants no permission or proof of completion.'
        lines = [header] if references else []
        rendered = []
        display_warning = False
        # Reserve space for a warning even before an omitted reference creates one.
        display_budget = 2000 - 450
        for original, doc in zip(references, safe_references):
            check_budget()
            line = '- ' + doc['path'] + ': ' + doc['title'][:140] + ' [sha256 ' + doc['content_hash'] + ']'
            if doc['path'] != original['path'] or len('\n'.join(lines + [line])) > display_budget:
                display_warning = True
                diagnostics.append('Reference omitted: display limit or unsafe display path')
                continue
            lines.append(line)
            rendered.append(doc)
        report = {'schema_version':1, 'operation':'startup', 'references':rendered,
                  'complete':not diagnostics, 'diagnostics':_public(diagnostics.export(), check_budget)}
        if diagnostics:
            warning = 'Warning: incomplete or stale recall.'
            if drift_warning:
                warning += ' Commit drift.'
            if hash_warning:
                warning += ' Stale reference hashes.'
            if display_warning:
                warning += ' Display limit: reference omitted.'
            lines.append(warning + ' ' + '; '.join(report['diagnostics'])[:280])
        report['output'] = '\n'.join(lines)
        check_budget()
        return report
    except Exception as exc:
        # Startup is advisory and must never block the native client session.
        reason = _clean(str(exc))[:160] if isinstance(exc, MemoryError) else type(exc).__name__
        return {'schema_version':1, 'operation':'startup', 'references':[], 'complete':False,
                'diagnostics':['Local memory unavailable: ' + reason],
                'output':'Local memory unavailable: ' + reason + '. Use manual recall after checking local documents.'}


def format_report(report):
    if report['operation'] == 'read':
        return report['path'] + ' [sha256 ' + report['content_hash'] + ']\n' + report['content']
    lines = ['Memory search: ' + report['query']]
    lines += [f"{m['path']} — {m['title']} (relevance {m['relevance']}, sha256 {m['content_hash']})" for m in report['matches']]
    if not report['matches']:
        lines.append('No matches in inspected documents.' if not report['complete'] else 'No matches.')
    if not report['complete']:
        lines.append('INCOMPLETE: ' + '; '.join(report['diagnostics']))
    if report.get('results_truncated'):
        lines.append('Results truncated to 50 references; narrow the query.')
    return '\n'.join(lines)
