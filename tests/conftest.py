"""Fixtures for check_entry.py: a minimal valid IHMCIF entry and mutations."""
import io
import os
import sys
from pathlib import Path

import pytest

import ihm
import ihm.cross_linkers
import ihm.dataset
import ihm.dumper
import ihm.location
import ihm.model
import ihm.protocol
import ihm.reader
import ihm.representation
import ihm.restraint

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'check' / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def build_cif(atom_names=('CA', 'CA', 'CA')):
    """Return mmCIF text for a 3-residue, 1-model crosslink entry.

    `atom_names` gives the atom_id of the single atom on residues 1-3.
    The result validates cleanly against the PDBx + IHM dictionaries.
    """
    s = ihm.System(id='TEST')
    s.title = 'Minimal test entry'
    s.authors.append('Doe, J.')
    s.citations.append(ihm.Citation(
        pmid=None, title='Test', journal='J', volume='1', page_range=(1, 2),
        year='2026', authors=['Doe, J.'], doi='10.1/x'))
    entity = ihm.Entity('MKV', description='Test protein')
    s.entities.append(entity)
    asym = ihm.AsymUnit(entity, details='Chain A', id='A')
    s.asym_units.append(asym)
    assembly = ihm.Assembly([asym], name='Complete')
    dataset = ihm.dataset.CXMSDataset(ihm.location.PRIDELocation('PXD000001'))
    rep = ihm.representation.Representation(
        [ihm.representation.AtomicSegment(asym, rigid=False)])
    protocol = ihm.protocol.Protocol(name='Modeling')
    protocol.steps.append(ihm.protocol.Step(
        assembly=assembly, dataset_group=ihm.dataset.DatasetGroup([dataset]),
        method='Monte Carlo', num_models_begin=0, num_models_end=1))
    xl = ihm.restraint.CrossLinkRestraint(dataset, ihm.cross_linkers.dss)
    exp = ihm.restraint.ExperimentalCrossLink(entity.residue(1), entity.residue(3))
    xl.experimental_cross_links.append([exp])
    xl.cross_links.append(ihm.restraint.ResidueCrossLink(
        exp, asym, asym, ihm.restraint.UpperBoundDistanceRestraint(30.0)))
    s.restraints.append(xl)
    model = ihm.model.Model(assembly=assembly, protocol=protocol,
                            representation=rep, name='Model 1')
    for seq_id, (atom_id, x) in enumerate(zip(atom_names, (0., 3.8, 7.6)), start=1):
        model.add_atom(ihm.model.Atom(asym_unit=asym, seq_id=seq_id, atom_id=atom_id,
                                      type_symbol=atom_id.lstrip('0123456789')[0],
                                      x=x, y=0., z=0., het=False))
    group = ihm.model.ModelGroup([model], name='Group 1')
    s.state_groups.append(ihm.model.StateGroup([ihm.model.State([group])]))
    fh = io.StringIO()
    ihm.dumper.write(fh, [s])
    return fh.getvalue()


def replace_once(text, old, new):
    """str.replace that fails loudly if the fixture text has drifted."""
    assert text.count(old) == 1, f'expected exactly one {old!r} in fixture'
    return text.replace(old, new)


@pytest.fixture
def write_entry(tmp_path):
    """Write mmCIF text to tmp_path/<name> and return the path as str."""
    def _write(text, name='entry.cif'):
        path = tmp_path / name
        path.write_text(text, encoding='utf-8')
        return str(path)
    return _write


@pytest.fixture
def valid_cif():
    return build_cif()


@pytest.fixture
def empty_cache(tmp_path):
    path = tmp_path / 'empty-cache'
    path.mkdir()
    return str(path)


@pytest.fixture(scope='session')
def online_cache(tmp_path_factory):
    """A cache dir shared by network tests; dictionaries download once."""
    return str(tmp_path_factory.mktemp('ihmtools-cache'))


def to_bcif(cif_path, bcif_path):
    with open(cif_path, encoding='utf-8') as fh:
        systems = ihm.reader.read(fh)
    with open(bcif_path, 'wb') as fh:
        ihm.dumper.write(fh, systems, format='BCIF')
    return str(bcif_path)


def picked(findings, severity, category, keyword=''):
    """Findings (objects or JSON dicts) with this severity and anchor."""
    get = (lambda f, k: f[k]) if findings and isinstance(findings[0], dict) \
        else getattr
    return [f for f in findings if get(f, 'severity') == severity
            and get(f, 'category') == category and get(f, 'keyword') == keyword]
