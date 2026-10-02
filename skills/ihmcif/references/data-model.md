# IHM data model

## Archive and identifiers

- **PDBx/mmCIF** is the wwPDB format for coordinates and metadata. Chemical
  components come from the Chemical Component Dictionary (CCD):
  `https://files.rcsb.org/ligands/download/{COMP_ID}.cif`.
- **PDB-IHM** (formerly PDB-Dev) archives integrative structures, meaning
  models computed from several kinds of experimental and computational data
  rather than one diffraction or imaging experiment.
- Entry identifiers come in two forms: legacy `PDBDEV_########` (8 digits)
  and 4-character PDB IDs (e.g. `9A8R`), used since PDB-IHM entries joined
  the main PDB archive. Both can appear in one file (`_database_2`,
  `_pdbx_database_related`).
- Released files: `https://files.rcsb.org/download/{ID}.cif`. Entry
  metadata: `https://data.rcsb.org/rest/v1/core/entry/{ID}`.
- Dictionaries: `https://mmcif.wwpdb.org/dictionaries/ascii/mmcif_pdbx_v50.dic`
  (PDBx) and `https://mmcif.wwpdb.org/dictionaries/ascii/mmcif_ihm_ext.dic`
  (IHMCIF; also in `https://github.com/ihmwg/IHMCIF`, `dist/`).

## Categories you will navigate

| Concern | Categories |
|---|---|
| Composition | `entity`, `entity_poly`, `entity_poly_seq`, `struct_asym`, `ihm_entity_poly_segment` |
| What was modeled | `ihm_struct_assembly`, `ihm_struct_assembly_details`, `ihm_struct_assembly_class` |
| Representation | `ihm_model_representation`, `ihm_model_representation_details` (atomic vs. sphere vs. Gaussian, rigid vs. flexible, residues per bead) |
| Coordinates | `atom_site` (atomic), `ihm_sphere_obj_site` (coarse-grained beads), `ihm_gaussian_obj_site` |
| Models and ensembles | `ihm_model_list`, `ihm_model_group`, `ihm_model_group_link`, `ihm_ensemble_info`, `ihm_localization_density_files` |
| States and order | `ihm_multi_state_modeling`, `ihm_ordered_ensemble`, `ihm_multi_state_scheme` (IHMCIF 1.2 and later) |
| Input data | `ihm_dataset_list`, `ihm_dataset_group`, `ihm_dataset_related_db_reference`, `ihm_related_datasets`, `ihm_external_reference_info`, `ihm_external_files` |
| Starting models | `ihm_starting_model_details`, `ihm_starting_computational_models`, `ihm_starting_comparative_models` |
| Restraints | `ihm_cross_link_list`, `ihm_cross_link_restraint`, `ihm_sas_restraint`, `ihm_3dem_restraint`, `ihm_predicted_contact_restraint`, `ihm_derived_distance_restraint`, `ihm_geometric_object_*` |
| Protocol | `ihm_modeling_protocol`, `ihm_modeling_protocol_details`, `ihm_modeling_post_process` |

`_ihm_model_list` has only `model_id`, `model_name`, `assembly_id`,
`protocol_id`, `representation_id`. Which models belong to which group is
recorded in `ihm_model_group_link`.

## The two invariants entries break most

1. **Linkage.** A restraint, dataset, or model group points at an id that
   does not exist, or a dataset is used by nothing: no restraint, feature,
   or starting model references it, and it is not the primary of a used
   dataset in `ihm_related_datasets`.
2. **Representation consistency.** A segment declared coarse-grained carries
   `atom_site` rows, or an atomic segment carries spheres. Coordinates must
   also fall inside the model's assembly and representation.

## Data types and validation coverage

The IHMValidation report covers SAS, crosslinking-MS, and 3DEM data (FRET is
in development). A section for a data type the entry does not have is
legitimately empty; that is not a bug. Crosslinking-MS data quality can be
assessed only for datasets deposited in PRIDE in compliant form; SAS fits
come from SASBDB; 3DEM assessments reuse the wwPDB EM pipeline.
