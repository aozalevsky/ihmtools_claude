import ihmcheck_stages as st
from conftest import picked, replace_once

ATOMS_IN_SPHERES = ('atomistic . flexible by-atom', 'sphere . flexible by-residue')


def systems_of(path):
    result, systems = st.stage_read(path)
    assert result.status == 'ok'
    return systems


def test_representation_valid(write_entry, valid_cif):
    result = st.stage_representation(systems_of(write_entry(valid_cif)))
    assert result.status == 'ok'
    assert result.detail == '3 atoms/spheres checked'


def test_representation_atoms_in_sphere_segment(write_entry, valid_cif):
    bad = replace_once(valid_cif, *ATOMS_IN_SPHERES)
    result = st.stage_representation(systems_of(write_entry(bad)))
    [f] = picked(result.findings, 'ERROR', 'atom_site', 'label_asym_id')
    assert f.row == 'models 1; asyms A'
    assert f.observed == ('3 atom(s) do not match the primitive of the covering '
                          'representation segment; first at model 1 asym A seq_id 1 '
                          'atom CA')
    assert 'object at 0x' not in f.evidence


def test_representation_missing_checker_not_checked(monkeypatch, write_entry, valid_cif):
    monkeypatch.delattr(st.ihm.dumper, '_RangeChecker')
    result = st.stage_representation(systems_of(write_entry(valid_cif)))
    assert result.status == 'not_checked'


def test_roundtrip_valid_has_no_notes(write_entry, valid_cif):
    path = write_entry(valid_cif)
    _, inv = st.stage_parse(path)
    result = st.stage_roundtrip(path, systems_of(path), inv)
    assert result.status == 'ok'


def test_roundtrip_unmodeled_category_is_note(write_entry, valid_cif):
    path = write_entry(valid_cif + "#\n_struct_keywords.entry_id TEST\n"
                                   "_struct_keywords.text 'X'\n")
    _, inv = st.stage_parse(path)
    result = st.stage_roundtrip(path, systems_of(path), inv)
    [f] = picked(result.findings, 'NOTE', 'struct_keywords')
    assert f.observed == 'the whole category would be dropped by a python-ihm rewrite'


def test_roundtrip_ignores_dropped_items_without_values(write_entry, valid_cif):
    path = write_entry(replace_once(
        valid_cif, "_struct.title 'Minimal test entry'\n",
        "_struct.title 'Minimal test entry'\n_struct.pdbx_descriptor .\n"))
    _, inv = st.stage_parse(path)
    assert 'pdbx_descriptor' in inv['struct']
    result = st.stage_roundtrip(path, systems_of(path), inv)
    assert result.status == 'ok'
