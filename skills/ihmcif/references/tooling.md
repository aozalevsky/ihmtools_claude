# Tools for IHMCIF files

Choose the tool by the level the problem lives at. Using the wrong level is
the most common way to waste a cycle.

## gemmi: lexical and dictionary level

Use it for loop syntax, duplicated or missing tags, category surgery on files
python-ihm refuses to open, and coordinate access. gemmi reads some broken
files that python-ihm rejects, so it is the first tool to reach for after a
parse failure. Use the Python module (`import gemmi`); the pip package does
not install a `gemmi` command-line program. gemmi's Python reader handles
text and gzipped mmCIF, not BinaryCIF.

```python
import gemmi
doc = gemmi.cif.read('ENTRY.cif')
block = doc.sole_block()

# Full category inventory. Iterating only `if item.loop` is WRONG: single-row
# categories are stored as `pair` items, and on a small entry that hides most
# of the ihm_* metadata (on 9A8R: 11 loops vs. 35 categories). Cover both:
cats = set()
for item in block:
    if item.loop is not None:
        cats.add(item.loop.tags[0].split('.')[0])
    elif item.pair is not None:
        cats.add(item.pair[0].split('.')[0])

tbl = block.find('_ihm_model_group_link.', ['group_id', 'model_id'])  # read a loop
block.find_mmcif_category('_ihm_dataset_list.').erase()  # works on pair and loop forms
doc.write_file('ENTRY.fixed.cif')
st = gemmi.read_structure('ENTRY.cif')                   # coordinate view
```

`block.find()` returns an **empty table instead of raising** when a requested
tag is absent, so a typo or a retired item looks like "no rows in a good
file". Confirm the tag exists in the dictionary before believing an empty
result.

## python-ihm: semantic and model level

Use it to answer whether the entry means what it says: the object graph,
restraint-to-dataset wiring, ensembles, protocol steps. A clean read/write
round-trip is the strongest single correctness signal.

```python
import ihm.reader, ihm.dumper
with open('ENTRY.cif') as fh:          # BinaryCIF: open(..., 'rb'), format='BCIF'
    systems = ihm.reader.read(fh)
s = systems[0]
# s.entities, s.asym_units, s.orphan_datasets, s.restraints, s.state_groups,
# s.ensembles, s.orphan_protocols, s.orphan_representations

for group, model in s._all_models():   # yields 2-tuples, NOT 4-tuples
    print(group._id, model._id, len(model._atoms), len(model._spheres))

with open('roundtrip.cif', 'w') as fh:
    ihm.dumper.write(fh, systems)
```

- A round-trip is a **check, not a repair method**. `ihm.dumper.write` emits
  only what python-ihm models; anything else is silently dropped (on 9A8R,
  `_entity_name_com` disappears). Diff the round-trip against the original
  to learn what is unmodeled, then patch the real file with gemmi.
- `ihm.dumper.write` checks that every atom or sphere fits the model's
  representation and assembly, and raises `ValueError` otherwise. Pass
  `check=False` only for diagnosis.
- `UnknownCategoryWarning` / `UnknownKeywordWarning` (enabled with
  `warn_unknown_category=True`, `warn_unknown_keyword=True`) mean python-ihm
  has no model for an item, not that the item is invalid. Python-ihm emits
  dozens of them even on files it wrote itself. Never report them as
  defects; dictionary validation is the authority on unknown items.
- `ihm.reader.read(..., reject_old_file=True)` flags files written against an
  obsolete dictionary version.

## Dictionary validation (in Python, no CLI)

```python
import urllib.request, ihm.dictionary
BASE = 'https://mmcif.wwpdb.org/dictionaries/ascii/'
with urllib.request.urlopen(BASE + 'mmcif_pdbx_v50.dic') as fh:
    d_pdbx = ihm.dictionary.read(fh)
with urllib.request.urlopen(BASE + 'mmcif_ihm_ext.dic') as fh:
    d_ihm = ihm.dictionary.read(fh)
with open('ENTRY.cif') as fh:
    (d_pdbx + d_ihm).validate(fh)      # raises ihm.dictionary.ValidatorError
```

- `mmcif_ihm_ext.dic` and `mmcif_ihm.dic` are the same file under two names:
  the IHM extension plus the PDBx parent categories it extends, not all of
  PDBx. Merge with `mmcif_pdbx_v50.dic` for full coverage. Cache them
  locally (the `check` skill keeps them in `~/.cache/ihmtools/`) instead of
  refetching 6 MB on every run.
- The validator lowercases keyword names in its messages.
- **Dictionary validation is blind to atom nomenclature.** It skips
  `chem_comp_*` parents, so `_atom_site.label_atom_id` is never checked
  against the CCD. An entry using obsolete PDB v2.3 hydrogen names (`1HB`,
  `2HG2`) validates clean. Use `check --check-atom-names`, or compare each
  component's `_chem_comp_atom.atom_id` set from the CCD with the distinct
  `(comp_id, atom_id)` pairs in `atom_site`; the CCD's `alt_atom_id` column
  maps old names to current ones.

## ChimeraX: geometry and visuals

```bash
chimerax --nogui --offscreen --silent --exit \
  --cmd "open ENTRY.cif; info; clashes #1; save shot.png width 1200"
```

Use `--script script.py` for anything nontrivial. Good for clashes,
distances, sanity-checking multi-scale representations, and rendering.
Bead models have no standard atoms: check what actually loaded (`info`)
before trusting a geometry command's output. ChimeraX is optional; the
probe script reports whether it is installed.
