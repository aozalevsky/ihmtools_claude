# python-ihm patterns for building an entry

Condensed from the worked examples in https://github.com/salilab/ihmtools,
`examples/9A9W/assemble.py` (atomic: 51729 atoms, DSSO crosslinks, 3DEM map)
and `examples/9A8W/assemble.py` (coarse-grained: 1663 spheres, SDA
crosslinks, 3DEM map). Read those scripts when a case below is not enough.
API reference: https://python-ihm.readthedocs.io.

## Skeleton

```python
import ihm, ihm.dataset, ihm.dumper, ihm.location, ihm.model
import ihm.protocol, ihm.reader, ihm.representation, ihm.restraint

system = ihm.System(title="...")            # TODO(depositor) if unknown
system.authors.extend(["Last, F.", ...])
# entities, asym units, assembly, representation, datasets, restraints,
# protocol, models (below)
with open(OUTPUT, "w") as fh:
    ihm.dumper.write(fh, [system])
with open(OUTPUT) as fh:                     # read back: the cheapest check
    check, = ihm.reader.read(fh)
```

## Entities and asym units

One `ihm.Entity` per unique sequence, one `ihm.AsymUnit` per chain copy.

```python
alphabet = ihm.DNAAlphabet if is_dna else ihm.LPeptideAlphabet
comps = alphabet()._comps
# DNAAlphabet is keyed by "DA"; LPeptideAlphabet by the one-letter code.
# Look up by name first, then fall back to the one-letter code:
sequence = [comps.get(name) or
            comps[gemmi.find_tabulated_residue(name).one_letter_code.upper()]
            for name in residue_names]
entity = ihm.Entity(sequence, alphabet=alphabet, description=description)
asym = ihm.AsymUnit(entity, details=description, id=chain_id)

# a ligand (e.g. zinc) is its own single-component entity
zn = ihm.Entity([ihm.NonPolymerChemComp("ZN", name="ZINC ION")],
                description="ZINC ION")

assembly = ihm.Assembly(list_of_asyms, name="Modeled assembly")
```

`_entity.pdbx_description` is often the only naming a coordinate file
carries, and crosslink tables name proteins by it. gemmi's
`make_mmcif_document()` drops it, so put it back if you rewrite coordinates.

## Representation

```python
# atomic, over the residues actually present (chains may have gaps)
ihm.representation.AtomicSegment(asym(first_seq, last_seq), rigid=False)
# ligands: the whole asym unit; never give a non-polymer a residue range
ihm.representation.AtomicSegment(zinc_asym, rigid=False)

# coarse-grained
ihm.representation.ResidueSegment(asym(b, e), rigid=True, primitive="sphere")
ihm.representation.FeatureSegment(asym(b, e), rigid=False, primitive="sphere",
                                  count=1)      # one multi-residue bead
representation = ihm.representation.Representation([...segments...])
```

Ask the entity (`asym.entity.is_polymeric()`) before giving an asym a residue
range; older gemmi assigns `label_seq` to non-polymers too.

## Datasets and where the data lives

```python
xl = ihm.dataset.CXMSDataset(ihm.location.PRIDELocation("PXD......"))
em = ihm.dataset.EMDensityDataset(ihm.location.EMDBLocation("EMD-....."))
sas = ihm.dataset.SASDataset(ihm.location.SASBDBLocation("SASDA..."))
pdb = ihm.dataset.PDBDataset(ihm.location.PDBLocation("9XXX"))
afdb = ihm.dataset.DeNovoModelDataset(
    ihm.location.AlphaFoldDBLocation("AF-Q93009-F1-v4"))
ma = ihm.dataset.DeNovoModelDataset(
    ihm.location.ModelArchiveLocation("ma-....."))
# data not in a database: a file in a DOI-bearing repository (e.g. Zenodo)
repo = ihm.location.Repository(doi="10.5281/zenodo.......", url="https://...")
f = ihm.location.InputFileLocation("path/in/archive.csv", repo=repo)
system.orphan_datasets.extend([xl, em, ...])
```

Every dataset should be used by a restraint or starting model; the `check`
skill warns about any that are not. Raw data behind a processed dataset is
linked with `ihm_related_datasets`, not left as an unused dataset.

## Crosslinks: two layers

What the experiment measured (protein and residue, no chain copy), and what
the modeling restrained (a chain pair, for the subset used).

```python
import ihm.cross_linkers                     # dss, dsso, bs3, sda, edc, ...
r = ihm.restraint.CrossLinkRestraint(dataset=xl, linker=ihm.cross_linkers.dsso)
link = ihm.restraint.ExperimentalCrossLink(
    entity1.residue(int(res1)), entity2.residue(int(res2)))
r.experimental_cross_links.append([link])
r.cross_links.append(ihm.restraint.ResidueCrossLink(    # residue-level beads/atoms
    experimental_cross_link=link, asym1=a1, asym2=a2,
    distance=ihm.restraint.UpperBoundDistanceRestraint(30.0)))
# on a multi-residue bead use FeatureCrossLink with the same arguments;
# psi=, sigma1=, sigma2= record Bayesian nuisance parameters when used
system.restraints.append(r)
```

Use the predefined linker from `ihm.cross_linkers` when it exists; it carries
the chemical description. `ihm.ChemDescriptor("NAME")` is the fallback.

## Map and SAS restraints

```python
emr = ihm.restraint.EM3DRestraint(dataset=em, assembly=assembly,
                                  fitting_method="Gaussian mixture models")
emr.fits[model] = ihm.restraint.EM3DRestraintFit()
sasr = ihm.restraint.SASRestraint(dataset=sas, assembly=assembly,
                                  fitting_method="FoXS",
                                  multi_state=False, radius_of_gyration=None)
sasr.fits[model] = ihm.restraint.SASRestraintFit(chi_value=None)
system.restraints.extend([emr, sasr])
```

Map and SAS restraints are written one row per fitted model: a restraint
with no entry in `.fits` is silently left out of the file. Record the fit
statistic when known (`cross_correlation_coefficient=`, `chi_value=`).

## Protocol, analysis, ensembles

```python
protocol = ihm.protocol.Protocol(name="Modeling")
protocol.steps.append(ihm.protocol.Step(
    assembly=assembly, dataset_group=None, name="Sampling",
    method="Replica exchange monte carlo",
    num_models_begin=0, num_models_end=320000))
import ihm.analysis
analysis = ihm.analysis.Analysis()
analysis.steps.append(ihm.analysis.ClusterStep(
    feature="RMSD", num_models_begin=320000, num_models_end=8260))
protocol.analyses.append(analysis)
system.orphan_protocols.append(protocol)
```

Use `None` for model counts you do not know rather than guessing.

## Models: stream coordinates

```python
class Model(ihm.model.Model):
    def get_atoms(self):                    # atomic
        for ...:
            yield ihm.model.Atom(asym_unit=asym, seq_id=seq_id or 1,
                                 atom_id=name, type_symbol=element,
                                 x=x, y=y, z=z, het=is_het,
                                 biso=b, occupancy=occ)

    def get_spheres(self):                  # coarse-grained
        for ...:
            yield ihm.model.Sphere(asym_unit=asym, seq_id_range=(b, e),
                                   x=x, y=y, z=z, radius=r)

model = Model(assembly=assembly, protocol=protocol,
              representation=representation, name="Best scoring model")
group = ihm.model.ModelGroup([model], name="Cluster 0")
system.state_groups.append(ihm.model.StateGroup([ihm.model.State([group])]))
system.ensembles.append(ihm.model.Ensemble(
    model_group=group, num_models=5766, name="Cluster 0",
    clustering_method="Density based threshold-clustering",
    clustering_feature="RMSD"))
```

## Things that bite

- **Non-polymers have no `label_seq`.** Skip their atoms and the write fails
  with "Assemblies reference asym IDs that don't have coordinates". A
  single-component entity's `seq_id` is 1.
- **Alphabets are keyed differently** (see above).
- **Representation must match the coordinates.** `ihm.dumper.write` raises
  `ValueError` when an atom falls in a sphere segment, or outside the
  representation or assembly. Fix the representation; do not pass
  `check=False` to get a file out.
- **Coarse-grained crosslinks** onto a bead spanning several residues must be
  `FeatureCrossLink`, not `ResidueCrossLink`.
