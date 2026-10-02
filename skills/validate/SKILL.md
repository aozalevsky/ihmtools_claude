---
name: validate
description: Get or interpret an IHMValidation report for an integrative structure. Uploads an IHMCIF file to the PDB-IHM validation server (validate.pdb-ihm.org) with the ihmv CLI, tracks it, and downloads the PDF reports, or runs a local IHMValidation Apptainer image when the user has one. Use when the user asks to validate an IHM/IHMCIF model, get or download a validation report, run IHMValidation, check validation status, or explain a PDB-IHM validation report.
argument-hint: <file.cif> | status <RID> | explain <report.pdf>
---

# IHMValidation reports

There are two routes. Default to the server; use the local route only when
the user already has an IHMValidation image.

Describe server output as "the IHMValidation report from
validate.pdb-ihm.org". This plugin is unofficial: never present its own
output (for example `check` findings) as a PDB-IHM assessment.

## Probe

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"
```

The server route needs `ihmv`. If it is missing, offer `pip install ihmtools`
and ask before installing. The local route needs `apptainer` (or
`singularity`) plus an image, either from `IHMV_SIF` or a path the user gives.

## Server route

1. **Pre-flight.** If the `check` skill has not run on this exact file in
   this conversation, offer it, and recommend it strongly if the file was
   edited.
2. **Account.** Run `ihmv whoami`. If it reports that nobody is logged in, ask
   the user to type `! ihmv login`: it prints a Globus URL and reads back a code,
   which you cannot do for them. Then run `ihmv whoami` again and confirm it
   is the account they mean.
3. **Confirm the upload.** Say: "This uploads `<file>`, an unreleased
   structure, to the PDB-IHM validation server as `<account>`. Proceed?"
   Then end your turn and run the upload only after an explicit yes in the
   user's next message. A request that already names the file, server, or
   options is not the confirmation: the user has not yet seen which account
   the upload will use.
4. **Upload.** Run `ihmv upload <file>` and record the RID it prints. Use the
   production server unless the user explicitly asks for `--mode dev`. If
   ihmv reports that the file was already submitted, tell the user and ask
   whether to use the existing record or resubmit with `-f`.
5. **Wait.** Run `ihmv get_status <RID>`. Exit codes: 0 done, 1 error,
   2 pending, 3 unknown. Validation takes 5 to 115 minutes. Do not poll in
   a tight loop: check every 5 to 10 minutes in the background, or tell the
   user they can come back and ask for the status of `<RID>`.
6. **Download.** When done, run `ihmv download <RID> -o <stem>_validation`.
   On error, `ihmv get_status <RID> -v` prints the processing log; summarize
   it and offer the `ihmtools:curator` agent for triage.
7. **Reprocess** (after a fix on the server side): confirm with the user,
   then run `ihmv set_status <RID> --to Reprocess -y`.
8. **Delete a record:** confirm with the user, naming the RID, then run
   `ihmv delete <RID> -y`.

`ihmv set_status` and `ihmv delete` ask for confirmation on the terminal,
which hangs in a non-interactive shell. Always confirm in chat first, then
add `-y`. `ihmv get_status` with no RID lists the user's entries, newest
first.

## Local route (Apptainer image)

Use it only when `IHMV_SIF` points to an image or the user names one. If
neither is true, ask the user for the path. Never search the filesystem for
images (`find`, `locate`): on shared or network filesystems that is slow and
reads directories the user never mentioned. Never build the image: that needs
Chimera and ChimeraX downloads and about 25 minutes (see the IHMValidation
README).

```bash
apptainer run --pid "$IHMV_SIF" --cache-root <cache-dir> --output-root <out-dir> -f <absolute-path-to-file>
```

- Use `singularity run` if only singularity is installed.
- Run it in the background.
- Add `--html-mode local` when the user wants to browse the HTML report.
- Outputs: `<out-dir>/<stem>/<stem>_full_validation.pdf`,
  `<stem>_summary_validation.pdf`, and `<stem>_html.tar.gz`.
- `-h` lists all options.
- To find which section fails, disable sections one at a time with
  `--enable-sas false`, `--enable-cx false`, `--enable-em false`,
  `--enable-prism false`, or `--enable-format-check false`.

## Explaining a report

Read `${CLAUDE_SKILL_DIR}/references/report-sections.md` first. When
explaining:

- Section content depends on the data the entry contains. An empty SAS
  section on an entry with no SAS data is expected.
- Separate what the depositor can fix in the file (missing dataset
  references, wrong representation) from properties of the model or data
  (restraint satisfaction, clashes).
- Point to https://pdb-ihm.org/validation_help.html for metric definitions.
