"""Executes the API calls taught in skills/build/references/python-ihm-patterns.md.

If python-ihm changes an API the reference relies on, this fails first.
"""
import io

import ihm
import ihm.analysis
import ihm.cross_linkers
import ihm.dataset
import ihm.dumper
import ihm.location
import ihm.model
import ihm.protocol
import ihm.reader
import ihm.representation
import ihm.restraint


def build_from_patterns():
    system = ihm.System(title='Patterns')
    system.authors.extend(['Last, F.'])
    comps = ihm.LPeptideAlphabet()._comps
    protein = ihm.Entity([comps['M'], comps['K'], comps['V']],
                         alphabet=ihm.LPeptideAlphabet, description='Protein')
    zinc = ihm.Entity([ihm.NonPolymerChemComp('ZN', name='ZINC ION')],
                      description='ZINC ION')
    a = ihm.AsymUnit(protein, details='Protein', id='A')
    z = ihm.AsymUnit(zinc, details='ZINC ION', id='B')
    system.entities.extend([protein, zinc])
    system.asym_units.extend([a, z])
    assembly = ihm.Assembly([a, z], name='Modeled assembly')
    representation = ihm.representation.Representation([
        ihm.representation.AtomicSegment(a(1, 3), rigid=False),
        ihm.representation.AtomicSegment(z, rigid=False)])

    xl = ihm.dataset.CXMSDataset(ihm.location.PRIDELocation('PXD000001'))
    em = ihm.dataset.EMDensityDataset(ihm.location.EMDBLocation('EMD-1234'))
    sas = ihm.dataset.SASDataset(ihm.location.SASBDBLocation('SASDA12'))
    repo = ihm.location.Repository(doi='10.5281/zenodo.1', url='https://zenodo.org/record/1')
    ihm.location.InputFileLocation('data/x.csv', repo=repo)
    system.orphan_datasets.extend([xl, em, sas])

    xlr = ihm.restraint.CrossLinkRestraint(dataset=xl, linker=ihm.cross_linkers.dsso)
    link = ihm.restraint.ExperimentalCrossLink(protein.residue(1), protein.residue(3))
    xlr.experimental_cross_links.append([link])
    xlr.cross_links.append(ihm.restraint.ResidueCrossLink(
        experimental_cross_link=link, asym1=a, asym2=a,
        distance=ihm.restraint.UpperBoundDistanceRestraint(30.0)))
    emr = ihm.restraint.EM3DRestraint(dataset=em, assembly=assembly,
                                      fitting_method='Gaussian mixture models')
    sasr = ihm.restraint.SASRestraint(dataset=sas, assembly=assembly,
                                      fitting_method='FoXS', multi_state=False,
                                      radius_of_gyration=None)
    system.restraints.extend([xlr, emr, sasr])

    protocol = ihm.protocol.Protocol(name='Modeling')
    protocol.steps.append(ihm.protocol.Step(
        assembly=assembly, dataset_group=None, name='Sampling',
        method='Replica exchange monte carlo', num_models_begin=0, num_models_end=10))
    analysis = ihm.analysis.Analysis()
    analysis.steps.append(ihm.analysis.ClusterStep(
        feature='RMSD', num_models_begin=10, num_models_end=5))
    protocol.analyses.append(analysis)
    system.orphan_protocols.append(protocol)

    class Model(ihm.model.Model):
        def get_atoms(self):
            rows = [(a, 1, 'CA', 'C'), (a, 2, 'CA', 'C'), (a, 3, 'CA', 'C'),
                    (z, None, 'ZN', 'ZN')]
            for i, (asym, seq_id, name, element) in enumerate(rows):
                yield ihm.model.Atom(asym_unit=asym, seq_id=seq_id or 1, atom_id=name,
                                     type_symbol=element, x=float(i), y=0., z=0.,
                                     het=asym is z, biso=None, occupancy=None)

    model = Model(assembly=assembly, protocol=protocol,
                  representation=representation, name='Best scoring model')
    emr.fits[model] = ihm.restraint.EM3DRestraintFit()
    sasr.fits[model] = ihm.restraint.SASRestraintFit(chi_value=None)
    group = ihm.model.ModelGroup([model], name='Cluster 0')
    system.state_groups.append(ihm.model.StateGroup([ihm.model.State([group])]))
    system.ensembles.append(ihm.model.Ensemble(
        model_group=group, num_models=5, name='Cluster 0',
        clustering_method='Density based threshold-clustering',
        clustering_feature='RMSD'))
    return system


def test_patterns_write_and_read_back():
    fh = io.StringIO()
    ihm.dumper.write(fh, [build_from_patterns()])
    fh.seek(0)
    check, = ihm.reader.read(fh)
    assert len(check.entities) == 2
    assert len(check.restraints) == 3          # crosslink, 3DEM, SAS
    assert len(check.ensembles) == 1


def test_restraint_without_fit_is_silently_dropped():
    system = build_from_patterns()
    sas_restraint = system.restraints[2]
    sas_restraint.fits.clear()
    fh = io.StringIO()
    ihm.dumper.write(fh, [system])
    fh.seek(0)
    check, = ihm.reader.read(fh)
    assert len(check.restraints) == 2          # what the reference warns about
