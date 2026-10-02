import re

import pytest

import ihmcheck_stages as st
from conftest import picked, replace_once

DANGLING = (r'(1 DSS) 1 \.', r'\1 99 .')     # crosslink list -> dataset 99


def test_parse_valid(write_entry, valid_cif):
    result, inv = st.stage_parse(write_entry(valid_cif))
    assert result.status == 'ok'
    assert 'ihm_dataset_list' in inv
    assert result.detail.endswith('items')


def test_parse_syntax_error_is_blocker(write_entry, valid_cif):
    bad = replace_once(valid_cif, "'Minimal test entry'", "'Minimal test entry")
    result, inv = st.stage_parse(write_entry(bad))
    assert inv is None
    [f] = result.findings
    assert f.severity == 'BLOCKER'
    assert 'CifParserError' in f.evidence and 'line' in f.evidence


def test_parse_non_utf8_is_blocker(tmp_path, valid_cif):
    path = tmp_path / 'latin1.cif'
    path.write_bytes(replace_once(valid_cif, "'Minimal test entry'",
                                  "'Minimal t\xe9st entry'").encode('latin-1'))
    result, inv = st.stage_parse(str(path))
    assert inv is None
    assert 'UnicodeDecodeError' in result.findings[0].evidence


def test_parse_empty_file_is_blocker(write_entry):
    result, inv = st.stage_parse(write_entry(''))
    assert inv is None
    assert result.detail == 'no data'
    assert result.findings[0].severity == 'BLOCKER'


def test_parse_without_ihm_categories_is_error(write_entry):
    result, inv = st.stage_parse(write_entry('data_x\n_entry.id x\n'))
    assert inv == {'entry': {'id'}}
    [f] = result.findings
    assert f.severity == 'ERROR' and 'no ihm_' in f.observed


def test_some_truncates():
    assert st._some('abc') == 'a, b, c'
    assert st._some(range(10), limit=3) == '0, 1, 2 (+7 more)'


def test_clean_strips_object_reprs():
    msg = '<ihm.model.Atom object at 0x7f00ab12> vs <ihm.representation.ResidueSegment object at 0x1>'
    assert st._clean(msg) == 'Atom vs ResidueSegment'
    assert st._clean('x' * 400).endswith('...')


def test_parse_validator_messages():
    def parse(msg):
        return list(st._parse_validator_message(msg))
    assert parse("Mandatory keyword struct.title cannot have value '?'") == [
        ('struct', 'title', "mandatory item is '?'", None, 'a value (mandatory item)')]
    assert parse('The following IDs referenced by _ihm_cross_link_list.dataset_list_id '
                 'were not defined in the parent category (_ihm_dataset_list.id): 7, 9'
                 ) == [('ihm_cross_link_list', 'dataset_list_id',
                        'reference to undefined id', v,
                        'ids defined in _ihm_dataset_list.id') for v in ('7', '9')]
    assert parse('The following keywords are not defined in the dictionary: '
                 '_struct.foo, _entry.bar') == [
        ('struct', 'foo', 'item not in dictionary', None,
         'items defined in PDBx or IHMCIF'),
        ('entry', 'bar', 'item not in dictionary', None,
         'items defined in PDBx or IHMCIF')]
    assert parse('something new') == [('', '', 'other', 'something new', '')]


def test_group_validator_errors_merges_rows():
    msg = ('Keyword atom_site.group_pdb value ATOMX is not a valid enumerated value '
           '(options are ATOM, HETATM)')
    [f] = st._group_validator_errors([msg, msg, msg])
    assert (f.severity, f.category, f.keyword) == ('ERROR', 'atom_site', 'group_pdb')
    assert f.observed == 'value not in enumeration (3 rows): ATOMX'
    assert f.expected == 'one of: ATOM, HETATM'


def test_dictionary_offline_without_cache_not_checked(write_entry, valid_cif,
                                                      empty_cache):
    result = st.stage_dictionary(write_entry(valid_cif), empty_cache, offline=True)
    assert result.status == 'not_checked'
    assert result.detail.startswith('dictionaries unavailable')


@pytest.mark.network
def test_dictionary_valid(write_entry, valid_cif, online_cache):
    result = st.stage_dictionary(write_entry(valid_cif), online_cache, offline=False)
    assert result.status == 'ok'


@pytest.mark.network
def test_dictionary_dangling_reference(write_entry, valid_cif, online_cache):
    bad = re.sub(*DANGLING, valid_cif)
    result = st.stage_dictionary(write_entry(bad), online_cache, offline=False)
    [f] = picked(result.findings, 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')
    assert f.observed == 'reference to undefined id: 99'


@pytest.mark.network
def test_dictionary_repeated_violation_grouped(write_entry, valid_cif, online_cache):
    bad = re.sub(r'^ATOM ', 'ATOMX ', valid_cif, flags=re.M)
    result = st.stage_dictionary(write_entry(bad), online_cache, offline=False)
    # the validator reports keywords lowercased
    [f] = picked(result.findings, 'ERROR', 'atom_site', 'group_pdb')
    assert f.observed.startswith('value not in enumeration (3 rows): ATOMX')
