import re

import ihmcheck_stages as st
from conftest import picked, replace_once

DANGLING = (r'(1 DSS) 1 \.', r'\1 99 .')     # crosslink list -> dataset 99


def test_read_valid(write_entry, valid_cif):
    result, systems = st.stage_read(write_entry(valid_cif))
    assert result.status == 'ok'
    assert result.detail == '1 data block(s), 1 model(s)'
    assert len(systems) == 1


def test_read_exception_is_blocker(write_entry, valid_cif):
    # num_models_begin must be an integer: the file parses, python-ihm cannot read it
    bad = replace_once(valid_cif, "'Monte Carlo' 0 1", "'Monte Carlo' x 1")
    result, systems = st.stage_read(write_entry(bad))
    assert systems is None
    [f] = result.findings
    assert f.severity == 'BLOCKER'
    assert f.evidence.startswith("ValueError: Cannot parse 'x' as integer")


def test_read_two_data_blocks(write_entry, valid_cif):
    text = valid_cif + valid_cif.replace('data_TEST', 'data_TEST2')
    result, systems = st.stage_read(write_entry(text))
    assert result.detail == '2 data block(s), 2 model(s)'


def test_linkage_valid_has_no_findings(write_entry, valid_cif):
    assert st.stage_linkage(write_entry(valid_cif), dangling=True).status == 'ok'


def test_linkage_reports_dangling_only_when_asked(write_entry, valid_cif):
    path = write_entry(re.sub(*DANGLING, valid_cif))
    with_check = st.stage_linkage(path, dangling=True)
    [f] = picked(with_check.findings, 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')
    assert '99' in f.observed and f.evidence == '_ihm_dataset_list.id has: 1'
    without = st.stage_linkage(path, dangling=False)
    assert not picked(without.findings, 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')


def test_linkage_unused_dataset_warns(write_entry, valid_cif):
    text = replace_once(valid_cif, "1 'Crosslinking-MS data' YES .",
                        "1 'Crosslinking-MS data' YES .\n2 'SAS data' NO .")
    result = st.stage_linkage(write_entry(text), dangling=False)
    [f] = picked(result.findings, 'WARNING', 'ihm_dataset_list', 'id')
    assert f.row == 'id 2' and '(SAS data)' in f.observed


def test_linkage_primary_of_used_dataset_is_used(write_entry, valid_cif):
    text = replace_once(valid_cif, "1 'Crosslinking-MS data' YES .",
                        "1 'Crosslinking-MS data' YES .\n2 'Mass Spectrometry data' NO .\n"
                        "3 'Mass Spectrometry data' NO .")
    text += ('#\nloop_\n_ihm_related_datasets.dataset_list_id_derived\n'
             '_ihm_related_datasets.dataset_list_id_primary\n'
             '_ihm_related_datasets.transformation_id\n1 2 .\n2 3 .\n#\n')
    result = st.stage_linkage(write_entry(text), dangling=True)
    assert result.status == 'ok', result.findings   # 3 is used via 1 -> 2 -> 3


def test_linkage_reads_uppercase_tags(write_entry, valid_cif):
    text = valid_cif.replace('_ihm_dataset_list.', '_IHM_DATASET_LIST.')
    assert st.stage_linkage(write_entry(text), dangling=True).status == 'ok'
