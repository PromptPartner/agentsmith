#!/usr/bin/env python3
"""Freeze a containment manifest, record immutable observations, and check coverage.

An incomplete ledger is a valid recording. `check` exits nonzero unless all
required evidence passes; fixtures can never produce native qualification.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import qualification as q


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    # Exclusive creation preserves every predecessor; no in-place ledger editing.
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    manifest = subs.add_parser('manifest', help='freeze full required variant inventory')
    manifest.add_argument('--inventory', required=True)
    manifest.add_argument('--output', required=True)
    ledger = subs.add_parser('init', help='retain all native variants as not-run')
    ledger.add_argument('--manifest', required=True)
    ledger.add_argument('--output', required=True)
    rec = subs.add_parser('record', help='append actual observation to a new snapshot')
    rec.add_argument('--manifest', required=True)
    rec.add_argument('--ledger', required=True)
    rec.add_argument('--entry', required=True)
    rec.add_argument('--output', required=True)
    check = subs.add_parser('check', help='strict completeness; never substitutes fixtures')
    check.add_argument('--manifest', required=True)
    check.add_argument('--ledger', required=True)
    check.add_argument('--fixture', action='store_true', help='fixture completeness only, never native qualification')
    check.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'manifest':
            value = q.build_manifest(read(args.inventory))
        elif args.command == 'init':
            value = q.new_ledger(read(args.manifest))
        elif args.command == 'record':
            value = q.record(read(args.manifest), read(args.ledger), read(args.entry))
        else:
            value = q.check(read(args.manifest), read(args.ledger), require_native=not args.fixture)
        write(args.output, value)
        print(json.dumps({'command': args.command, 'output': args.output,
                          **({'complete': value['complete'], 'qualified': value['qualified'],
                              'blockers': len(value['blockers'])} if args.command == 'check' else {})}, sort_keys=True))
        return 1 if args.command == 'check' and not value['complete'] else 0
    except (q.EvidenceError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f'qualification evidence rejected: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
