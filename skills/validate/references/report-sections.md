# What an IHMValidation report contains

Full definitions: https://pdb-ihm.org/validation_help.html. The pipeline
follows the wwPDB IHM Task Force recommendations (Berman et al. 2019) and
the SAS, crosslinking-MS, and 3DEM community guidelines.

Each run produces a **full report** (PDF, plus HTML in a `.tar.gz`) and a
**summary table** (PDF).

## Full report sections

| Section | Content | Depends on |
|---|---|---|
| 1. Overview | Summary of models, datasets, and representation; "at a glance" plots for model quality, data quality, fit to data used for modeling, and fit to data used for validation | everything below |
| 2. Model details | Ensembles; representation (rigid and flexible segments); datasets used; methods, protocol, and software | every entry has this |
| 3. Data quality | SAS: scattering profiles, MW and volume estimates, flexibility (Porod-Debye, Kratky), P(r), Guinier. Crosslinking-MS: only for datasets deposited in PRIDE in compliant form, with entities matched to the PRIDE data. 3DEM: elements of the wwPDB EM map validation | which data types the entry has |
| 4. Model quality | Atomic models: MolProbity (bonds, angles, clashscore, rotamers, Ramachandran). Coarse-grained models: excluded-volume violations between beads. PrISM precision (regions of high and low precision) | atomic vs. coarse-grained representation |
| 5. Fit to data used for modeling | SAS: chi-squared and CorMap p-values, from SASBDB fits. Crosslinking-MS: restraint types, distograms, satisfaction per restraint group. 3DEM: map-model fit as in the wwPDB EM report | which data types the entry has |
| 6. Fit to data used for validation | Under development | |

## Summary table

Entry composition and datasets; representation (scale, rigid and flexible
segments); physical and experimental restraints; validation (sampling
precision, ensembles, models per ensemble, deposited models, model
precision, plus one-line data quality, model quality, and fit-to-data
results); methods and software.

## Reading a report with the user

- **Empty sections.** A section for a data type the entry does not contain
  is empty by design. Crosslinking-MS data quality is empty when the dataset
  is not a compliant PRIDE deposition, even if crosslinks are in the file.
- **Problems the depositor can fix in the file.** A dataset missing its
  database reference (`ihm_dataset_related_db_reference`) or used by no
  restraint; crosslink restraints at the wrong granularity for the
  representation; representation details that disagree with the
  coordinates. The `check` skill and the `ihmtools:curator` agent can find
  these in the file.
- **Properties of the model or data.** Low restraint satisfaction, clashes,
  poor SAS fit. These are scientific results to discuss, not file errors;
  do not "fix" them by editing the entry.
- **Pipeline failure** (no report, or an error status): get the processing
  log (`ihmv get_status <RID> -v`) and hand it to the `ihmtools:curator`
  agent, which decides whether the cause is the entry data, the pipeline
  code, or the environment.
