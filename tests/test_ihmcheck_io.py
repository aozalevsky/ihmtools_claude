import gzip
import http.client
import io
import os
import stat

import pytest

import ihmcheck_io as cio
from conftest import to_bcif


def test_file_format():
    assert cio.file_format('x.bcif') == 'BCIF'
    assert cio.file_format('x.BCIF') == 'BCIF'
    assert cio.file_format('x.cif') == 'mmCIF'
    assert cio.file_format('x.cif.gz') == 'mmCIF'


def test_inventory_sees_pair_and_loop_categories(write_entry, valid_cif):
    inv = cio.inventory(write_entry(valid_cif))
    assert 'title' in inv['struct']                 # single-row (pair) category
    assert {'label_atom_id', 'cartn_x'} <= inv['atom_site']    # loop category
    assert all(not c.startswith('_') for c in inv)


def test_inventory_gzip_and_bcif_match_cif(tmp_path, write_entry, valid_cif):
    cif = write_entry(valid_cif)
    gz = tmp_path / 'entry.cif.gz'
    with gzip.open(gz, 'wt', encoding='utf-8') as fh:
        fh.write(valid_cif)
    assert cio.inventory(str(gz)) == cio.inventory(cif)
    bcif = to_bcif(cif, tmp_path / 'entry.bcif')
    assert set(cio.inventory(cif)) <= set(cio.inventory(bcif))


def test_read_tables_rows_missing_and_special_values(write_entry, valid_cif):
    t = cio.read_tables(write_entry(valid_cif), {
        'ihm_dataset_list': ['id', 'data_type', 'no_such_keyword'],
        'ihm_sas_restraint': ['dataset_list_id'],
        'ihm_dataset_list_x': ['id'],
        'ihm_dataset_group': ['name']})
    assert t['ihm_dataset_list'] == [
        {'id': '1', 'data_type': 'Crosslinking-MS data', 'no_such_keyword': None}]
    assert t['ihm_sas_restraint'] == []
    assert t['ihm_dataset_list_x'] == []
    assert t['ihm_dataset_group'] == [{'name': None}]       # '.' in the file


def test_cache_root(monkeypatch, tmp_path):
    assert cio.cache_root(str(tmp_path)) == tmp_path
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    assert cio.cache_root() == tmp_path / 'ihmtools'


def test_offline_without_cache_raises(tmp_path):
    with pytest.raises(cio.Unavailable, match='--offline'):
        cio.fetch_cached('https://example.invalid/x', tmp_path / 'x', offline=True)


def test_offline_uses_cache_of_any_age(tmp_path):
    dest = tmp_path / 'x'
    dest.write_text('cached')
    os.utime(dest, (0, 0))
    assert cio.fetch_cached('https://example.invalid/x', dest, offline=True) == dest


def test_stale_cache_used_when_download_fails(tmp_path, monkeypatch):
    dest = tmp_path / 'dictionaries' / 'x.dic'
    dest.parent.mkdir()
    dest.write_text('cached')
    os.utime(dest, (0, 0))  # far older than MAX_AGE

    def fail(*args, **kwargs):
        raise cio.urllib.error.URLError('no network')
    monkeypatch.setattr(cio.urllib.request, 'urlopen', fail)
    assert cio.fetch_cached('https://example.invalid/x.dic', dest, offline=False) == dest


def test_download_failure_without_cache_raises(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise cio.urllib.error.URLError('no network')
    monkeypatch.setattr(cio.urllib.request, 'urlopen', fail)
    with pytest.raises(cio.Unavailable):
        cio.fetch_cached('https://example.invalid/x', tmp_path / 'x', offline=False)
    assert not (tmp_path / 'x').exists()


@pytest.mark.parametrize('comp_id', ['../etc', '', 'TOOLONG', 'A B', None])
def test_ccd_rejects_unsafe_component_ids(tmp_path, comp_id):
    with pytest.raises(cio.Unavailable):
        cio.ccd_atoms(comp_id, tmp_path, offline=False)


@pytest.mark.network
def test_ccd_atoms_has_alt_names(online_cache):
    atoms = cio.ccd_atoms('MET', online_cache, offline=False)
    assert atoms['HB2'] == '1HB'
    assert atoms['CA'] == 'CA'


@pytest.mark.network
def test_load_dictionary_merges_pdbx_and_ihm(online_cache):
    d = cio.load_dictionary(online_cache, offline=False)
    assert 'atom_site' in d.categories and 'ihm_dataset_list' in d.categories


def test_inventory_crlf_line_endings(tmp_path, valid_cif):
    crlf = tmp_path / 'crlf.cif'
    crlf.write_bytes(valid_cif.replace('\n', '\r\n').encode('utf-8'))
    lf = tmp_path / 'lf.cif'
    lf.write_text(valid_cif, encoding='utf-8')
    assert cio.inventory(str(crlf)) == cio.inventory(str(lf))


def test_tags_are_case_insensitive(write_entry, valid_cif):
    path = write_entry(valid_cif.replace('_ihm_dataset_list.', '_IHM_DATASET_LIST.'))
    assert 'ihm_dataset_list' in cio.inventory(path)
    assert cio.read_tables(path, {'ihm_dataset_list': ['id']}) == {
        'ihm_dataset_list': [{'id': '1'}]}


@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
def test_unwritable_cache_dir_is_unavailable_not_a_crash(tmp_path):
    readonly = tmp_path / 'readonly'
    readonly.mkdir()
    readonly.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(cio.Unavailable):
            cio.fetch_cached('https://example.invalid/x', readonly / 'sub' / 'x',
                             offline=False)
    finally:
        readonly.chmod(stat.S_IRWXU)


# ---- review fix: downloads and cached files must be the real thing ----------

PORTAL = b'<html><body>Please sign in to the network</body></html>'


def serve(monkeypatch, payload=None, error=None):
    """Make urlopen return `payload` bytes, or raise `error`."""
    def fake(*args, **kwargs):
        if error is not None:
            raise error
        return io.BytesIO(payload)
    monkeypatch.setattr(cio.urllib.request, 'urlopen', fake)


def test_download_failing_validation_is_discarded(tmp_path, monkeypatch):
    serve(monkeypatch, PORTAL)
    dest = tmp_path / 'x.dic'
    with pytest.raises(cio.Unavailable, match='not a valid'):
        cio.fetch_cached('https://example.invalid/x.dic', dest, offline=False,
                         sentinel=b'save_atom_site')
    assert list(tmp_path.iterdir()) == []          # no dest, no leftover .part


def test_invalid_download_falls_back_to_valid_stale_cache(tmp_path, monkeypatch):
    dest = tmp_path / 'x.dic'
    dest.write_bytes(b'data_x\nsave_atom_site\n')
    os.utime(dest, (0, 0))
    serve(monkeypatch, PORTAL)
    assert cio.fetch_cached('https://example.invalid/x.dic', dest, offline=False,
                            sentinel=b'save_atom_site') == dest
    assert dest.read_bytes() == b'data_x\nsave_atom_site\n'


def test_invalid_cached_file_is_never_used(tmp_path):
    dest = tmp_path / 'x.dic'
    dest.write_bytes(PORTAL)                        # fresh, but garbage
    with pytest.raises(cio.Unavailable):
        cio.fetch_cached('https://example.invalid/x.dic', dest, offline=True,
                         sentinel=b'save_atom_site')


def test_dropped_connection_is_unavailable(tmp_path, monkeypatch):
    serve(monkeypatch, error=http.client.IncompleteRead(b'partial'))
    with pytest.raises(cio.Unavailable):
        cio.fetch_cached('https://example.invalid/x', tmp_path / 'x', offline=False)


def test_corrupt_cached_dictionaries_are_unavailable(tmp_path):
    folder = tmp_path / 'dictionaries'
    folder.mkdir()
    for name in cio.DICT_FILES:
        (folder / name).write_bytes(PORTAL)
    with pytest.raises(cio.Unavailable):
        cio.load_dictionary(tmp_path, offline=True)


def test_corrupt_cached_ccd_file_is_unavailable(tmp_path):
    (tmp_path / 'ccd').mkdir()
    (tmp_path / 'ccd' / 'MET.cif').write_bytes(PORTAL)
    with pytest.raises(cio.Unavailable):
        cio.ccd_atoms('MET', tmp_path, offline=True)
