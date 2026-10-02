import pytest

import ihmcheck_stages as st
from conftest import build_cif, picked


def test_atom_names_offline_without_cache_not_checked(write_entry, valid_cif,
                                                      empty_cache):
    result = st.stage_atom_names(write_entry(valid_cif), empty_cache, offline=True)
    assert result.status == 'not_checked'
    assert result.detail == 'CCD unavailable for LYS, MET, VAL'


def test_atom_names_without_atoms(write_entry):
    result = st.stage_atom_names(write_entry('data_x\n_entry.id x\n'), '/nonexistent',
                                 offline=True)
    assert (result.status, result.detail) == ('ok', 'no atom_site rows')


@pytest.mark.network
def test_atom_names_valid(write_entry, valid_cif, online_cache):
    result = st.stage_atom_names(write_entry(valid_cif), online_cache, offline=False)
    assert result.status == 'ok'
    assert result.detail == '3 component(s) against the CCD'


@pytest.mark.network
def test_obsolete_hydrogen_name_gets_rename(write_entry, online_cache):
    path = write_entry(build_cif(atom_names=('1HB', 'CA', 'OXT')))
    result = st.stage_atom_names(path, online_cache, offline=False)
    [f] = picked(result.findings, 'ERROR', 'atom_site', 'label_atom_id')
    assert f.row == 'comp_id MET'
    assert f.observed == 'atom names not in the CCD: 1HB'
    assert f.fix == 'rename 1HB -> HB2'
