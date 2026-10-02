"""File and cache access for check_entry.py.

Every read goes through python-ihm's low-level readers, so .cif, .cif.gz and
.bcif files share one code path.
"""
import gzip
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import ihm.dictionary
import ihm.format
import ihm.format_bcif

DICT_URL = 'https://mmcif.wwpdb.org/dictionaries/ascii/'
DICT_FILES = ('mmcif_pdbx_v50.dic', 'mmcif_ihm_ext.dic')
CCD_URL = 'https://files.rcsb.org/ligands/download/{}.cif'
MAX_AGE = 30 * 24 * 3600
_COMP_ID = re.compile(r'[A-Za-z0-9]{1,5}')


class Unavailable(Exception):
    """A remote resource could not be obtained and is not cached."""


def file_format(path):
    """Return 'BCIF' for BinaryCIF input, else 'mmCIF'."""
    return 'BCIF' if str(path).lower().endswith('.bcif') else 'mmCIF'


def open_entry(path):
    """Open an entry file in the mode its format needs."""
    p = str(path)
    if file_format(p) == 'BCIF':
        return open(p, 'rb')
    if p.lower().endswith('.gz'):
        return gzip.open(p, 'rt', encoding='utf-8')
    return open(p, encoding='utf-8')


class _Collect:
    """Generic handler: records each row as a dict of the requested keys."""
    not_in_file = None
    omitted = None
    unknown = None

    def __init__(self, keys):
        self._keys = [k.lower() for k in keys]
        self.rows = []

    def __call__(self, *args):
        self.rows.append(dict(zip(self._keys, args)))


def _read(path, handlers, **callbacks):
    reader_cls = (ihm.format_bcif.BinaryCifReader
                  if file_format(path) == 'BCIF' else ihm.format.CifReader)
    with open_entry(path) as fh:
        reader = reader_cls(fh, handlers, **callbacks)
        while reader.read_file():
            pass


def read_tables(path, wanted):
    """Return {category: [row dicts]} for the requested keywords.

    `wanted` maps category names (no leading underscore) to keyword lists.
    Absent categories give empty lists; absent keywords and '.'/'?' values
    give None.
    """
    handlers = {'_' + c.lower(): _Collect(k) for c, k in wanted.items()}
    _read(path, handlers)
    return {c: handlers['_' + c.lower()].rows for c in wanted}


def inventory(path):
    """Return {category: set(keywords)} for everything in the file.

    Uses the readers' unknown-category/keyword callbacks, which fire for
    both loop and single-row (pair) categories.
    """
    cats = set()
    _read(path, {},
          unknown_category_handler=lambda cat, line: cats.add(cat.lower()))
    keys = {c: set() for c in cats}
    _read(path, {c: _Collect([]) for c in cats},
          unknown_keyword_handler=lambda cat, key, line:
              keys[cat.lower()].add(key.lower()))
    return {c.lstrip('_'): k for c, k in keys.items()}


def cache_root(override=None):
    """Cache directory: --cache-dir, else $XDG_CACHE_HOME/ihmtools."""
    if override:
        return Path(override)
    base = os.environ.get('XDG_CACHE_HOME') or os.path.join(
        os.path.expanduser('~'), '.cache')
    return Path(base) / 'ihmtools'


def fetch_cached(url, dest, offline, max_age=MAX_AGE):
    """Return a local path for `url`, downloading into `dest` when needed.

    A cached copy younger than `max_age` seconds is used as is. An older
    copy is refreshed when possible and used as a fallback when not.
    Raises Unavailable when there is no copy and none can be downloaded.
    """
    dest = Path(dest)
    if dest.exists() and (offline or time.time() - dest.stat().st_mtime < max_age):
        return dest
    if offline:
        raise Unavailable(f'{dest.name} is not cached and --offline was given')
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + '.part')
        with urllib.request.urlopen(url, timeout=60) as resp, open(part, 'wb') as fh:
            fh.write(resp.read())
        os.replace(part, dest)
        return dest
    except (urllib.error.URLError, OSError) as e:
        if dest.exists():
            return dest
        raise Unavailable(f'{url}: {e}') from e


def load_dictionary(cache_dir, offline):
    """Return the merged PDBx + IHM dictionary, or raise Unavailable."""
    merged = None
    for name in DICT_FILES:
        path = fetch_cached(DICT_URL + name, Path(cache_dir) / 'dictionaries' / name,
                            offline)
        with open(path, encoding='utf-8') as fh:
            d = ihm.dictionary.read(fh)
        merged = d if merged is None else merged + d
    return merged


def ccd_atoms(comp_id, cache_dir, offline):
    """Return {atom_id: alt_atom_id} for a CCD component, or raise Unavailable."""
    if not _COMP_ID.fullmatch(comp_id or ''):
        raise Unavailable(f'{comp_id!r} is not a valid CCD component id')
    comp_id = comp_id.upper()
    path = fetch_cached(CCD_URL.format(comp_id),
                        Path(cache_dir) / 'ccd' / f'{comp_id}.cif', offline)
    rows = read_tables(path, {'chem_comp_atom': ['atom_id', 'alt_atom_id']})
    return {r['atom_id']: r['alt_atom_id'] for r in rows['chem_comp_atom']}
