import json
import re

import pytest

import check_entry
import ihmcheck_stages as st
from conftest import picked, replace_once, to_bcif


def check(capsys, path, *flags):
    code = check_entry.main([path, '--json', *flags])
    return code, json.loads(capsys.readouterr().out)


def stage(report, name):
    return next(s for s in report['stages'] if s['name'] == name)


def test_missing_file_exits_2(capsys, tmp_path):
    assert check_entry.main([str(tmp_path / 'nope.cif')]) == 2
    assert 'cannot read' in capsys.readouterr().err


def test_bad_arguments_exit_2(capsys):
    with pytest.raises(SystemExit) as e:
        check_entry.main(['--no-such-flag'])
    assert e.value.code == 2


def test_offline_valid_entry_is_incomplete_not_pass(capsys, write_entry, valid_cif,
                                                    empty_cache):
    code, report = check(capsys, write_entry(valid_cif), '--offline',
                         '--cache-dir', empty_cache)
    assert code == 0
    assert report['verdict'] == 'INCOMPLETE'
    assert [s['name'] for s in report['stages']] == [
        'parse', 'dictionary', 'read', 'linkage', 'representation', 'roundtrip',
        'atom_names']
    assert stage(report, 'dictionary')['status'] == 'not_checked'
    assert 'core references' in stage(report, 'linkage')['detail']
    assert stage(report, 'atom_names')['detail'] == 'not requested (use --check-atom-names)'
    assert report['findings'] == []


def test_json_finding_fields(capsys, write_entry, valid_cif, empty_cache):
    bad = replace_once(valid_cif, 'atomistic . flexible by-atom',
                       'sphere . flexible by-residue')
    code, report = check(capsys, write_entry(bad), '--offline', '--cache-dir', empty_cache)
    assert code == 1 and report['verdict'] == 'FAIL'
    assert set(report['findings'][0]) == {'severity', 'category', 'keyword', 'row',
                                          'observed', 'expected', 'evidence', 'fix'}


def test_text_output(capsys, write_entry, valid_cif, empty_cache):
    text = replace_once(valid_cif, "1 'Crosslinking-MS data' YES .",
                        "1 'Crosslinking-MS data' YES .\n2 'SAS data' NO .")
    code = check_entry.main([write_entry(text), '--offline', '--cache-dir', empty_cache])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith('INCOMPLETE: ')
    assert '(0 BLOCKER, 0 ERROR, 1 WARNING, 0 NOTE)' in out
    assert 'Local pre-check, not PDB-IHM validation.' in out
    assert '\n[WARNING] _ihm_dataset_list.id (id 2)\n  Observed: dataset 2' in out
    assert re.search(r'^Verified:\n  parse: ', out, re.M)
    assert re.search(r'^Not checked:\n  dictionary: dictionaries unavailable', out, re.M)


def test_syntax_error_stops_every_later_stage(capsys, write_entry, valid_cif,
                                              empty_cache):
    bad = replace_once(valid_cif, "'Minimal test entry'", "'Minimal test entry")
    code, report = check(capsys, write_entry(bad), '--offline', '--cache-dir', empty_cache)
    assert code == 1
    assert [f['severity'] for f in report['findings']] == ['BLOCKER']
    assert all(s['status'] == 'not_checked' for s in report['stages'][1:])


def test_unreadable_by_python_ihm_skips_model_stages(capsys, write_entry, valid_cif,
                                                     empty_cache):
    bad = replace_once(valid_cif, "'Monte Carlo' 0 1", "'Monte Carlo' x 1")
    code, report = check(capsys, write_entry(bad), '--offline', '--cache-dir', empty_cache)
    assert code == 1
    assert stage(report, 'linkage')['status'] == 'ok'
    assert stage(report, 'representation')['detail'] == 'python-ihm could not read the file'


def test_stage_crash_is_isolated(capsys, monkeypatch, write_entry, valid_cif,
                                 empty_cache):
    def boom(*args):
        raise RuntimeError('bug')
    monkeypatch.setattr(check_entry.st, 'stage_linkage', boom)
    code, report = check(capsys, write_entry(valid_cif), '--offline',
                         '--cache-dir', empty_cache)
    assert stage(report, 'linkage') == {
        'name': 'linkage', 'status': 'error',
        'detail': 'checker error: RuntimeError: bug'}
    assert stage(report, 'representation')['status'] == 'ok'
    assert report['verdict'] == 'INCOMPLETE'


def test_path_with_spaces_and_unicode(capsys, tmp_path, valid_cif):
    folder = tmp_path / 'my models (v2)'
    folder.mkdir()
    path = folder / 'entr\u00e9e 1.cif'
    path.write_text(valid_cif, encoding='utf-8')
    code, report = check(capsys, str(path), '--offline', '--cache-dir',
                         str(tmp_path / 'cache'))
    assert code == 0 and report['verdict'] == 'INCOMPLETE'
    assert report['file'] == str(path)


@pytest.mark.network
def test_valid_entry_passes(capsys, write_entry, valid_cif, online_cache):
    code, report = check(capsys, write_entry(valid_cif), '--cache-dir', online_cache,
                         '--check-atom-names')
    assert code == 0
    assert report['verdict'] == 'PASS'
    assert all(s['status'] == 'ok' for s in report['stages'])


@pytest.mark.network
def test_bcif_entry_passes(capsys, tmp_path, write_entry, valid_cif, online_cache):
    bcif = to_bcif(write_entry(valid_cif), tmp_path / 'entry.bcif')
    code, report = check(capsys, bcif, '--cache-dir', online_cache, '--check-atom-names')
    assert code == 0 and report['verdict'] == 'PASS'


@pytest.mark.network
def test_dangling_reference_reported_once(capsys, write_entry, valid_cif, online_cache):
    bad = re.sub(r'(1 DSS) 1 \.', r'\1 99 .', valid_cif)
    code, report = check(capsys, write_entry(bad), '--cache-dir', online_cache)
    assert code == 1
    [f] = picked(report['findings'], 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')
    assert f['evidence'].startswith('ihm.dictionary')


def test_requested_atom_name_check_that_did_not_run_is_incomplete():
    core_ok = [st.StageResult(name, 'ok') for name in check_entry.CORE_STAGES]
    not_requested = st.StageResult('atom_names', 'not_checked', check_entry.NOT_REQUESTED)
    requested_but_unavailable = st.StageResult('atom_names', 'not_checked',
                                               'CCD unavailable for ALA, ARG')
    assert check_entry.verdict(core_ok + [not_requested]) == 'PASS'
    assert check_entry.verdict(core_ok + [requested_but_unavailable]) == 'INCOMPLETE'
