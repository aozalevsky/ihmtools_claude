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


# ---- stage 3 -------------------------------------------------------------

def stage_read(path):
    """Read with python-ihm. Returns (result, systems or None)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with cio.open_entry(path) as fh:
                systems = ihm.reader.read(fh, format=cio.file_format(path))
    except Exception as e:
        return StageResult('read', 'findings', 'python-ihm could not read the file', [
            Finding('BLOCKER',
                    observed='python-ihm raised an exception while reading',
                    expected='a file python-ihm can read',
                    evidence=f'{type(e).__name__}: {_clean(str(e))}',
                    fix='find the item named in the exception; the curator '
                        'agent can bisect this')]), None
    nmodels = sum(1 for s in systems for _ in s._all_models())
    return (StageResult('read', 'ok', f'{len(systems)} data block(s), {nmodels} model(s)'),
            systems)


# ---- stage 4 -------------------------------------------------------------

# Categories whose dataset_list_id means "this dataset was used for modeling".
DATASET_USERS = (
    'ihm_2dem_class_average_restraint', 'ihm_3dem_restraint',
    'ihm_cross_link_list', 'ihm_derived_angle_restraint',
    'ihm_derived_dihedral_restraint', 'ihm_derived_distance_restraint',
    'ihm_epr_restraint', 'ihm_geometric_object_distance_restraint',
    'ihm_hdx_restraint', 'ihm_hydroxyl_radical_fp_restraint',
    'ihm_interface_residue_feature', 'ihm_ligand_probe',
    'ihm_poly_probe_conjugate', 'ihm_predicted_contact_restraint',
    'ihm_sas_restraint', 'ihm_starting_model_details',
)

# (child category, child keyword, parent category, parent keyword); used for
# dangling-reference checks only when dictionary validation could not run.
CORE_LINKS = (
    ('ihm_model_group_link', 'model_id', 'ihm_model_list', 'model_id'),
    ('ihm_model_group_link', 'group_id', 'ihm_model_group', 'id'),
    ('ihm_model_list', 'assembly_id', 'ihm_struct_assembly', 'id'),
    ('ihm_model_list', 'protocol_id', 'ihm_modeling_protocol', 'id'),
    ('ihm_model_list', 'representation_id', 'ihm_model_representation', 'id'),
    ('ihm_model_representation_details', 'representation_id',
     'ihm_model_representation', 'id'),
    ('ihm_struct_assembly_details', 'assembly_id', 'ihm_struct_assembly', 'id'),
    ('ihm_modeling_protocol_details', 'protocol_id', 'ihm_modeling_protocol', 'id'),
    ('ihm_modeling_protocol_details', 'dataset_group_id', 'ihm_dataset_group', 'id'),
    ('ihm_dataset_group_link', 'group_id', 'ihm_dataset_group', 'id'),
    ('ihm_dataset_group_link', 'dataset_list_id', 'ihm_dataset_list', 'id'),
    ('ihm_dataset_related_db_reference', 'dataset_list_id', 'ihm_dataset_list', 'id'),
    ('ihm_dataset_external_reference', 'dataset_list_id', 'ihm_dataset_list', 'id'),
    ('ihm_dataset_external_reference', 'file_id', 'ihm_external_files', 'id'),
    ('ihm_external_files', 'reference_id', 'ihm_external_reference_info',
     'reference_id'),
    ('ihm_related_datasets', 'dataset_list_id_derived', 'ihm_dataset_list', 'id'),
    ('ihm_related_datasets', 'dataset_list_id_primary', 'ihm_dataset_list', 'id'),
    ('ihm_starting_comparative_models', 'template_dataset_list_id',
     'ihm_dataset_list', 'id'),
) + tuple((c, 'dataset_list_id', 'ihm_dataset_list', 'id') for c in DATASET_USERS)


def _want(wanted, cat, key):
    keys = wanted.setdefault(cat, [])
    if key not in keys:
        keys.append(key)


def stage_linkage(path, dangling):
    """Find unused datasets; with `dangling`, also undefined references."""
    wanted = {}
    for c in DATASET_USERS:
        _want(wanted, c, 'dataset_list_id')
    _want(wanted, 'ihm_starting_comparative_models', 'template_dataset_list_id')
    _want(wanted, 'ihm_related_datasets', 'dataset_list_id_derived')
    _want(wanted, 'ihm_related_datasets', 'dataset_list_id_primary')
    _want(wanted, 'ihm_dataset_list', 'id')
    _want(wanted, 'ihm_dataset_list', 'data_type')
    if dangling:
        for child, ckey, parent, pkey in CORE_LINKS:
            _want(wanted, child, ckey)
            _want(wanted, parent, pkey)
    t = cio.read_tables(path, wanted)

    used = {r['dataset_list_id'] for c in DATASET_USERS for r in t[c]}
    used |= {r['template_dataset_list_id'] for r in t['ihm_starting_comparative_models']}
    used.discard(None)
    primaries = {}
    for r in t['ihm_related_datasets']:
        primaries.setdefault(r['dataset_list_id_derived'], set()).add(
            r['dataset_list_id_primary'])
    stack = list(used)
    while stack:
        for p in primaries.get(stack.pop(), ()):
            if p is not None and p not in used:
                used.add(p)
                stack.append(p)

    findings = []
    for r in t['ihm_dataset_list']:
        if r['id'] is not None and r['id'] not in used:
            findings.append(Finding(
                'WARNING', 'ihm_dataset_list', 'id', f"id {r['id']}",
                observed=f"dataset {r['id']} ({r['data_type']}) is not used by any "
                         "restraint, feature, or starting model",
                expected='every deposited dataset to be used by the modeling',
                evidence='no dataset_list_id reference to it, directly or as the '
                         'primary of a used dataset in _ihm_related_datasets',
                fix='reference it from the restraint or starting model that used '
                    'it; if it was not used, remove it or link it as the primary '
                    'of a used dataset in _ihm_related_datasets'))
    if not dangling:
        return _result('linkage', findings,
                       'dataset usage (references were checked by the dictionary stage)')
    for child, ckey, parent, pkey in CORE_LINKS:
        defined = {r[pkey] for r in t[parent]}
        missing = sorted({r[ckey] for r in t[child]} - defined - {None})
        if missing:
            findings.append(Finding(
                'ERROR', child, ckey,
                observed='reference to undefined id: ' + ', '.join(missing),
                expected=f'ids defined in _{parent}.{pkey}',
                evidence=f'_{parent}.{pkey} has: '
                         + (', '.join(sorted(defined - {None})) or 'no rows'),
                fix=_FIX['reference to undefined id']))
    return _result('linkage', findings,
                   'dataset usage and core references (dictionary not available)')


# ---- stage 5 -------------------------------------------------------------

_RANGE_PROBLEMS = (
    ('type of any representation segment',
     'do not match the primitive of the covering representation segment',
     'atoms only in atomic (by-atom) segments, spheres only in coarse-grained '
     'segments',
     'make _ihm_model_representation_details match the coordinates: declare '
     'these residues atomic, or deposit them as spheres'),
    ('representation',
     'are not covered by any representation segment of the model',
     "every atom or sphere covered by the model's representation",
     'extend _ihm_model_representation_details to cover these residues, or '
     'remove the coordinates'),
    ('assembly',
     "are outside the model's assembly",
     "every atom or sphere inside the model's assembly",
     'add these residues to the assembly (_ihm_struct_assembly_details) or '
     'remove the coordinates'),
    ('Multiple atoms with same',
     'are duplicates (same asym, seq_id, atom_id, alt_id)',
     'unique atoms',
     'remove or rename the duplicates; use alt_id for alternate conformations'),
)


def _classify_range_error(msg):
    for needle, observed, expected, fix in _RANGE_PROBLEMS:
        if needle in msg:
            return observed, expected, fix
    return 'were rejected by python-ihm', 'coordinates python-ihm can write', \
        'see the evidence'


def stage_representation(systems):
    """Report atoms/spheres python-ihm would refuse to write."""
    checker_cls = getattr(ihm.dumper, '_RangeChecker', None)
    if checker_cls is None:
        return StageResult('representation', 'not_checked',
                           'this python-ihm version has no _RangeChecker')
    groups = {}
    findings = []
    count = 0
    for system in systems:
        for _, model in system._all_models():
            try:
                checker = checker_cls(model, True)
            except Exception as e:
                findings.append(Finding(
                    'ERROR', 'ihm_model_list', '', f'model {model._id}',
                    observed="the model's representation or assembly cannot be "
                             'resolved',
                    expected='a model with a valid assembly and representation',
                    evidence=f'{type(e).__name__}: {_clean(str(e))}',
                    fix='check assembly_id and representation_id for this model'))
                continue
            for kind, objs in (('atom', model.get_atoms()),
                               ('sphere', model.get_spheres())):
                for obj in objs:
                    count += 1
                    try:
                        checker(obj)
                    except ValueError as e:
                        # One finding per problem, however many models/asyms
                        # share it: a single bad assembly can touch them all.
                        key = (kind, _classify_range_error(str(e)))
                        g = groups.setdefault(key, {
                            'n': 0, 'models': {}, 'asyms': {}, 'obj': obj,
                            'model': model._id, 'msg': str(e)})
                        g['n'] += 1
                        g['models'][model._id] = None
                        g['asyms'][obj.asym_unit._id] = None
    for (kind, (observed, expected, fix)), g in groups.items():
        obj = g['obj']
        if kind == 'atom':
            where = f"model {g['model']} asym {obj.asym_unit._id} seq_id {obj.seq_id} " \
                    f"atom {obj.atom_id}"
            cat, key = 'atom_site', 'label_asym_id'
        else:
            where = f"model {g['model']} asym {obj.asym_unit._id} " \
                    'seq_id {}-{}'.format(*obj.seq_id_range)
            cat, key = 'ihm_sphere_obj_site', 'asym_id'
        findings.append(Finding(
            'ERROR', cat, key,
            f"models {_some(g['models'])}; asyms {_some(g['asyms'])}",
            observed=f"{g['n']} {kind}(s) {observed}; first at {where}",
            expected=expected, evidence='python-ihm: ' + _clean(g['msg']), fix=fix))
    return _result('representation', findings, f'{count} atoms/spheres checked')


# ---- stage 6 -------------------------------------------------------------

def stage_roundtrip(path, systems, original):
    """Report valued items a python-ihm rewrite would drop.

    `original` is the stage-1 inventory. Items whose every value is '.' or
    '?' are not reported: dropping them loses nothing.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'roundtrip.cif')
            with open(out, 'w', encoding='utf-8') as fh:
                ihm.dumper.write(fh, systems, check=False)
            rewritten = cio.inventory(out)
    except Exception as e:
        return StageResult('roundtrip', 'findings', 'python-ihm could not write the file', [
            Finding('WARNING', observed='python-ihm cannot write this entry back out',
                    expected='a python-ihm read/write round-trip to succeed',
                    evidence=f'{type(e).__name__}: {_clean(str(e))}',
                    fix='the curator agent can locate the object that fails')])
    dropped = {cat: sorted(keys - rewritten.get(cat, set()))
               for cat, keys in original.items()}
    dropped = {cat: keys for cat, keys in dropped.items() if keys}
    values = cio.read_tables(path, dropped)
    findings = []
    for cat in sorted(dropped):
        lost = [k for k in dropped[cat]
                if any(row[k] is not None for row in values[cat])]
        if not lost:
            continue
        what = ('the whole category' if cat not in rewritten
                else 'items ' + ', '.join(lost))
        findings.append(Finding(
            'NOTE', cat,
            observed=f'{what} would be dropped by a python-ihm rewrite',
            expected='nothing; python-ihm does not model these items',
            evidence='present in the input, absent after ihm.dumper.write',
            fix='none needed; do not repair this file by rewriting it with '
                'python-ihm, or these items are lost'))
    return _result('roundtrip', findings, 'python-ihm read/write round-trip')


# ---- stage 7 -------------------------------------------------------------

# Accepted in atom_site even though the CCD component does not list them.
TERMINAL_ATOMS = frozenset({'H1', 'H2', 'H3', 'OXT', 'HXT', 'OP3'})


def stage_atom_names(path, cache_dir, offline):
    """Compare atom_site atom names with the CCD."""
    rows = cio.read_tables(path, {'atom_site': ['label_comp_id', 'label_atom_id']})
    by_comp = {}
    for r in rows['atom_site']:
        if r['label_comp_id'] and r['label_atom_id']:
            by_comp.setdefault(r['label_comp_id'], set()).add(r['label_atom_id'])
    if not by_comp:
        return StageResult('atom_names', 'ok', 'no atom_site rows')
    findings, unchecked = [], []
    for comp in sorted(by_comp):
        try:
            ccd = cio.ccd_atoms(comp, cache_dir, offline)
        except cio.Unavailable:
            unchecked.append(comp)
            continue
        current = {alt: atom for atom, alt in ccd.items() if alt and alt != atom}
        bad = sorted(by_comp[comp] - set(ccd) - TERMINAL_ATOMS)
        if not bad:
            continue
        renames = [f'{b} -> {current[b]}' for b in bad if b in current]
        findings.append(Finding(
            'ERROR', 'atom_site', 'label_atom_id', f'comp_id {comp}',
            observed='atom names not in the CCD: ' + ', '.join(bad),
            expected=f'atom names from the CCD definition of {comp}',
            evidence=cio.CCD_URL.format(comp.upper()),
            fix=('rename ' + ', '.join(renames)) if renames
                else 'check these atoms against the CCD definition'))
    if len(unchecked) == len(by_comp):
        return StageResult('atom_names', 'not_checked',
                           'CCD unavailable for ' + ', '.join(unchecked))
    detail = f'{len(by_comp) - len(unchecked)} component(s) against the CCD'
    if unchecked:
        detail += '; CCD unavailable for ' + ', '.join(unchecked)
    return _result('atom_names', findings, detail)
