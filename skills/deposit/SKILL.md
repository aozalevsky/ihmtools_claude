---
name: deposit
description: Deposit an integrative structure to PDB-IHM and manage the deposition with the ihmdep CLI. Uploads an IHMCIF file (optionally with a preview image), checks deposition status, moves an entry from DRAFT to DEPO or from RECORD READY to SUBMIT, downloads generated files and reports, and deletes entries that are still DRAFT or DEPO. Use when the user wants to deposit or submit a model to PDB-IHM, or asks about the status of a PDB-IHM deposition.
argument-hint: <file.cif> [--image file.png] | status [RID]
---

# Deposit to PDB-IHM with ihmdep

Every state-changing action needs explicit confirmation from the user, every
time, naming the entry and the action: ask, end your turn, and act only on a
yes in the user's next message. A request that already names the file, server,
or options is not the confirmation: the user has not yet seen which account
and which entry the action will use. Reading status and downloading are free.

## Probe and account

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"
```

`ihmdep` comes with `pip install ihmtools`; ask before installing. Then run
`ihmdep whoami`. If there are no credentials, ask the user to type
`! ihmdep login` (it prints a Globus URL and reads back a code). One login
covers both `ihmv` and `ihmdep`. Confirm the account is the one they mean.

The production server is the default. Use `--mode dev` only when the user
asks for it, for example to try the workflow on the development server.

## Upload

1. Recommend the `check` skill first, and the `validate` skill when the user
   has no validation report yet.
2. Confirm: "This deposits `<file>` [with image `<png>`] to PDB-IHM
   (production) as `<account>`. Proceed?"
3. Run `ihmdep upload <file> [--image <file.png>]`. Add `--draft` when the
   user wants to create the entry without starting processing (DRAFT instead
   of DEPO). Record the RID it prints.
4. If ihmdep says the file was already deposited, tell the user; resubmit
   with `-f` only if they ask.

## Status

- `ihmdep get_status` lists the user's entries, newest first.
- `ihmdep get_status <RID>` gives the workflow and process state. Exit codes:
  0 done, 1 error, 2 pending, 3 unknown. `--workflow` or `--process` prints
  only one of them; `-v` prints the full status detail.
- Workflow states the user drives: DRAFT, DEPO, RECORD READY, SUBMIT. Other
  states are written by the backend or by curators.

## The two transitions the user drives

`ihmdep set_status` allows exactly two:

- `--to DEPO`, only from DRAFT: start processing a draft.
- `--to SUBMIT`, only from RECORD READY: submit the processed entry to
  curation. Before asking, tell the user to review the generated files
  (`ihmdep download <RID>`) first.

Confirm, naming the RID and the transition, then run
`ihmdep set_status <RID> --to <STATE> -y`. The `-y` is required because the
interactive prompt hangs in a non-interactive shell; the chat confirmation
replaces it.

## Download

`ihmdep download <RID> -o <dir>` fetches the generated mmCIF and the
validation reports. Narrow it with `--mmcif`, `--full`, `--summary`, or
`--logs` (error and diagnostic files).

## Delete

Possible only for DRAFT or DEPO entries. Confirm, naming the RID, then run
`ihmdep delete <RID> -y`. Entries further along can only be deleted from the
PDB-IHM deposition web interface; this plugin does not attempt it.
