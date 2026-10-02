#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["ihm>=2.11", "msgpack"]
# ///
"""Local pre-check of an integrative-structure (IHMCIF) file.

This is not PDB-IHM validation; it catches problems before a file is sent
to validate.pdb-ihm.org or deposited.

Usage: check_entry.py FILE [--json] [--check-atom-names] [--cache-dir DIR] [--offline]
Exit codes: 0 no BLOCKER/ERROR, 1 at least one BLOCKER/ERROR, 2 could not run.
"""
import argparse
import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ihmcheck_io as cio  # noqa: E402
import ihmcheck_stages as st  # noqa: E402

CORE_STAGES = ('parse', 'dictionary', 'read', 'linkage', 'representation', 'roundtrip')
NOT_REQUESTED = 'not requested (use --check-atom-names)'
_RANK = {s: i for i, s in enumerate(st.SEVERITIES)}


def _guard(name, fn, *args):
    """Run a stage so that a bug in it cannot stop the other stages."""
    try:
        return fn(*args)
    except Exception as e:
        return st.StageResult(name, 'error', f'checker error: {type(e).__name__}: {e}')


def run_checks(path, cache_dir=None, offline=False, atom_names=False):
    """Run every stage on `path` and return the list of StageResults."""
    cache = cio.cache_root(cache_dir)
    parse, inventory = st.stage_parse(path)
    results = [parse]
    if inventory is None:
        reason = 'the file could not be parsed'
        results += [st.StageResult(n, 'not_checked', reason)
                    for n in CORE_STAGES[1:] + ('atom_names',)]
        return results
    dictionary = _guard('dictionary', st.stage_dictionary, path, cache, offline)
    results.append(dictionary)
    read, systems = st.stage_read(path)
    results.append(read)
    dictionary_ran = dictionary.status in ('ok', 'findings')
    results.append(_guard('linkage', st.stage_linkage, path, not dictionary_ran))
    if systems is None:
        reason = 'python-ihm could not read the file'
        results += [st.StageResult('representation', 'not_checked', reason),
                    st.StageResult('roundtrip', 'not_checked', reason)]
    else:
        results.append(_guard('representation', st.stage_representation, systems))
        results.append(_guard('roundtrip', st.stage_roundtrip, path, systems, inventory))
    if atom_names:
        results.append(_guard('atom_names', st.stage_atom_names, path, cache, offline))
    else:
        results.append(st.StageResult('atom_names', 'not_checked',
                                      NOT_REQUESTED))
    return results


def findings_of(results):
    return sorted((f for r in results for f in r.findings),
                  key=lambda f: _RANK[f.severity])


def verdict(results):
    """FAIL on any BLOCKER/ERROR; INCOMPLETE if a core or requested stage did not run."""
    if any(f.severity in ('BLOCKER', 'ERROR') for f in findings_of(results)):
        return 'FAIL'
    if any(r.status in ('not_checked', 'error')
           and (r.name in CORE_STAGES or r.detail != NOT_REQUESTED)
           for r in results):
        return 'INCOMPLETE'
    return 'PASS'


def _anchor(f):
    if not f.category:
        return '(file)'
    anchor = f'_{f.category}.{f.keyword}' if f.keyword else f'_{f.category}'
    return f'{anchor} ({f.row})' if f.row else anchor


def render_text(path, results):
    findings = findings_of(results)
    counts = ', '.join(f'{sum(f.severity == s for f in findings)} {s}'
                       for s in st.SEVERITIES)
    lines = [f'{verdict(results)}: {path} ({counts}). '
             'Local pre-check, not PDB-IHM validation.']
    for f in findings:
        lines.append('')
        lines.append(f'[{f.severity}] {_anchor(f)}')
        for label, value in (('Observed', f.observed), ('Expected', f.expected),
                             ('Evidence', f.evidence), ('Fix', f.fix)):
            if value:
                lines.append(f'  {label + ":":<10}{value}')
    lines.append('')
    lines.append('Verified:')
    ran = [r for r in results if r.status in ('ok', 'findings')]
    lines += [f'  {r.name}: {r.detail}' for r in ran] or ['  (nothing)']
    lines.append('Not checked:')
    skipped = [r for r in results if r.status in ('not_checked', 'error')]
    lines += [f'  {r.name}: {r.detail}' for r in skipped] or ['  (nothing)']
    return '\n'.join(lines)


def render_json(path, results):
    return json.dumps({
        'file': str(path),
        'verdict': verdict(results),
        'stages': [{'name': r.name, 'status': r.status, 'detail': r.detail}
                   for r in results],
        'findings': [asdict(f) for f in findings_of(results)],
    }, indent=2)


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Local pre-check of an IHMCIF file (not PDB-IHM validation).')
    p.add_argument('file', help='.cif, .cif.gz, or .bcif')
    p.add_argument('--json', action='store_true', help='machine-readable output')
    p.add_argument('--check-atom-names', action='store_true',
                   help='compare atom names with the CCD (downloads CCD files)')
    p.add_argument('--cache-dir', help='default: $XDG_CACHE_HOME/ihmtools')
    p.add_argument('--offline', action='store_true',
                   help='use cached dictionaries/CCD only; never download')
    args = p.parse_args(argv)
    if not os.path.isfile(args.file) or not os.access(args.file, os.R_OK):
        print(f'check_entry: cannot read {args.file}', file=sys.stderr)
        return 2
    results = run_checks(args.file, args.cache_dir, args.offline, args.check_atom_names)
    print(render_json(args.file, results) if args.json else render_text(args.file, results))
    return 1 if verdict(results) == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
