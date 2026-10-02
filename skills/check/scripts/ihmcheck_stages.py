"""The seven stages run by check_entry.py.

Each stage returns a StageResult; stages that later stages depend on also
return the data those stages need (the inventory, the python-ihm systems).
"""
import os
import re
import tempfile
import warnings
from dataclasses import dataclass, field

import ihm.dictionary
import ihm.dumper
import ihm.reader

import ihmcheck_io as cio

SEVERITIES = ('BLOCKER', 'ERROR', 'WARNING', 'NOTE')

@dataclass
class Finding:
    severity: str
    category: str = ''
    keyword: str = ''
    row: str = ''
    observed: str = ''
    expected: str = ''
    evidence: str = ''
    fix: str = ''


@dataclass
class StageResult:
    name: str
    status: str  # ok | findings | not_checked | error
    detail: str = ''
    findings: list = field(default_factory=list)


def _some(values, limit=8):
    """'a, b, c' or 'a, b, ... (+n more)' for display."""
    values = list(values)
    shown = ', '.join(str(v) for v in values[:limit])
    return shown + (f' (+{len(values) - limit} more)' if len(values) > limit else '')


def _result(name, findings, detail):
    return StageResult(name, 'findings' if findings else 'ok', detail, findings)


def _clean(msg, limit=300):
    """Strip python-ihm object reprs and cap length for display."""
    msg = re.sub(r'<ihm\.[\w.]+\.(\w+) object at 0x[0-9a-f]+>', r'\1', msg)
    return msg if len(msg) <= limit else msg[:limit] + '...'


# ---- stage 1 -------------------------------------------------------------

def stage_parse(path):
    """Parse the file and inventory it. Returns (result, inventory or None)."""
    try:
        inv = cio.inventory(path)
    except Exception as e:  # any failure here means nothing else can run
        return StageResult('parse', 'findings', 'file could not be parsed', [Finding(
            'BLOCKER',
            observed=f'the file cannot be parsed as {cio.file_format(path)}',
            expected='a syntactically valid mmCIF or BinaryCIF file',
            evidence=f'{type(e).__name__}: {_clean(str(e))}',
            fix='repair the syntax at the reported location; '
                'no other check can run until the file parses')]), None
    if not inv:
        return StageResult('parse', 'findings', 'no data', [Finding(
            'BLOCKER', observed='the file contains no categories',
            expected='a data block describing the entry',
            fix='check that this is the right file')]), None
    findings = []
    if not any(c.startswith('ihm_') for c in inv):
        findings.append(Finding(
            'ERROR',
            observed='the file has no ihm_* categories',
            expected='an integrative (IHMCIF) entry; PDB-IHM requires the IHM '
                     'extension',
            evidence=f'{len(inv)} categories, none starting with ihm_',
            fix='check this is the integrative model file you meant to use; '
                'other findings may be consequences of this one'))
    nkeys = sum(len(k) for k in inv.values())
    return _result('parse', findings, f'{len(inv)} categories, {nkeys} items'), inv


# ---- stage 2 -------------------------------------------------------------

_FIX = {
    "mandatory item is '?'": "supply the value; if it is a fact about the "
                             "study, depositor input is required",
    'mandatory item is missing': 'add the item',
    'mandatory category is missing': 'add the category',
    'value not in enumeration': 'use one of the allowed values',
    'value does not match item type': 'correct the value format',
    'reference to undefined id': 'define the id in the parent category, '
                                 'or correct the reference',
    'category not in dictionary': 'remove it or correct the name '
                                  '(check the spelling against the dictionary)',
    'item not in dictionary': 'remove it or correct the name '
                              '(check the spelling against the dictionary)',
}


def _parse_validator_message(msg):
    """Yield (category, keyword, problem, value, expected) for one message."""
    m = re.match(r"Mandatory keyword (\w+)\.(\S+) cannot have value '\?'$", msg)
    if m:
        yield m[1], m[2], "mandatory item is '?'", None, 'a value (mandatory item)'
        return
    m = re.match(r'Mandatory keyword (\w+)\.(\S+) cannot be missing from the file$', msg)
    if m:
        yield m[1], m[2], 'mandatory item is missing', None, 'the item (mandatory)'
        return
    m = re.match(r'Keyword (\w+)\.(\S+) value (.*) is not a valid enumerated '
                 r'value \(options are (.*)\)$', msg, re.S)
    if m:
        yield m[1], m[2], 'value not in enumeration', m[3], 'one of: ' + m[4]
        return
    m = re.match(r'Keyword (\w+)\.(\S+) value (.*) does not match item type '
                 r'\((.*?)\) regular expression', msg, re.S)
    if m:
        yield m[1], m[2], 'value does not match item type', m[3], f'type {m[4]}'
        return
    m = re.match(r'The following IDs referenced by _(\w+)\.(\S+) were not defined '
                 r'in the parent category \(_(\w+)\.(\S+)\): (.*)$', msg, re.S)
    if m:
        for value in m[5].split(', '):
            yield (m[1], m[2], 'reference to undefined id', value,
                   f'ids defined in _{m[3]}.{m[4]}')
        return
    m = re.match(r'The following mandatory categories are missing in the file: (.*)$',
                 msg, re.S)
    if m:
        for cat in m[1].split(', '):
            yield cat, '', 'mandatory category is missing', None, 'the category'
        return
    m = re.match(r'The following categories are not defined in the dictionary: (.*)$',
                 msg, re.S)
    if m:
        for cat in m[1].split(', '):
            yield (cat.lstrip('_'), '', 'category not in dictionary', None,
                   'categories defined in PDBx or IHMCIF')
        return
    m = re.match(r'The following keywords are not defined in the dictionary: (.*)$',
                 msg, re.S)
    if m:
        for item in m[1].split(', '):
            cat, _, key = item.lstrip('_').partition('.')
            yield (cat, key, 'item not in dictionary', None,
                   'items defined in PDBx or IHMCIF')
        return
    yield '', '', 'other', msg, ''


def _group_validator_errors(messages):
    groups = {}
    for msg in messages:
        for cat, key, problem, value, expected in _parse_validator_message(msg):
            g = groups.setdefault((cat, key, problem),
                                  {'n': 0, 'values': [], 'expected': expected,
                                   'msg': msg})
            g['n'] += 1
            if value is not None and value not in g['values']:
                g['values'].append(value)
    findings = []
    for (cat, key, problem), g in groups.items():
        observed = problem if problem != 'other' else 'dictionary violation'
        if g['n'] > 1:
            observed += f" ({g['n']} rows)"
        if g['values'] and problem != 'other':
            observed += ': ' + _some(g['values'], limit=5)
        findings.append(Finding(
            'ERROR', cat, key, observed=observed, expected=g['expected'],
            evidence='ihm.dictionary: ' + _clean(g['msg']),
            fix=_FIX.get(problem, 'see the evidence')))
    return findings


def stage_dictionary(path, cache_dir, offline):
    """Validate against the merged PDBx + IHM dictionaries."""
    try:
        dictionary = cio.load_dictionary(cache_dir, offline)
    except cio.Unavailable as e:
        return StageResult('dictionary', 'not_checked', f'dictionaries unavailable: {e}')
    try:
        with cio.open_entry(path) as fh:
            dictionary.validate(fh, format=cio.file_format(path))
    except ihm.dictionary.ValidatorError as e:
        findings = _group_validator_errors(str(e).split('\n\n'))
        return _result('dictionary', findings, 'PDBx + IHM dictionaries')
    return StageResult('dictionary', 'ok', 'PDBx + IHM dictionaries: no violations')
