---
name: make-codex-pet
description: Create, resume, validate, repair, package, and install Codex-compatible v2 animated pets from user-provided reference images or text. Use when a user asks to make a custom Codex pet, turn an image into a pet, resume an interrupted pet run, validate a pet atlas, or install a generated pet.
---

# Make Codex Pet

Use `scripts/petctl.py` as the only workflow planner. It persists progress and emits one next action, so never reconstruct the full pipeline from memory.

## Safety

- Keep references and generated media in the run directory, never inside this skill or plugin.
- Use only the current user's inputs. Do not reuse examples, prior pets, unrelated runs, or generated outputs.
- Do not initialize Git, publish, upload a repository, or copy run artifacts into plugin source.
- Image generation sends the current run's attached references to the configured image-generation service. State this if the user asks about privacy.

## Runtime

Call `load_workspace_dependencies` once. Use its exact Python executable for every script command. Set:

```text
SKILL_DIR=<directory containing this SKILL.md>
PETCTL=<SKILL_DIR>/scripts/petctl.py
RUN_DIR=<new directory outside the plugin>
```

## Start or resume

For a new run:

```text
python PETCTL init --run-dir RUN_DIR --reference IMAGE --pet-name NAME --description DESCRIPTION --style-preset auto --mode balanced
```

Omit `--reference` for text-only pets. Infer a short name and description when the user omits them. For an existing run, call `status`, then continue with `next`.

## Generation loop

1. Call `python PETCTL next --run-dir RUN_DIR`.
2. Follow the returned action:
   - `generate`: read only the returned prompt and that job's object in `imagegen-jobs.json`. Attach every listed input image. Invoke `$imagegen`; never draw a row locally.
   - `build-standard`: call `python PETCTL build-standard --run-dir RUN_DIR`, then visually inspect `qa/contact-sheet.png` and motion previews once.
   - `finalize`: call `python PETCTL finalize --run-dir RUN_DIR`.
   - `blocked`: stop and report the named job and its recorded error.
3. For a generated image, check frame count, identity, flat chroma background, separation, clipping, and forbidden detached effects. Then call:

```text
python PETCTL record-generation --run-dir RUN_DIR --job JOB --source GENERATED_FILE
```

4. Repeat. `record-generation` performs incremental deterministic checks and applies retry limits automatically. Do not regenerate completed jobs.

Generate at most three independent ready standard rows concurrently when useful, but keep one image-generation call per visual job. Generate `look-row-10` only after `look-row-9` passes registration.

## Balanced review

After `finalize`, inspect `qa/contact-sheet-extended.png`, `qa/look-directions.png`, previews, and validation JSON.

- Require stable identity, readable state motion, no clipping, transparent backgrounds, and an 8x11 `1536x2288` atlas.
- Require `000` up, `090` screen-right, `180` down, and `270` screen-left to be unmistakable.
- Record all 16 labeled direction verdicts in `qa/direction-semantics.json`.
- Treat subtle intermediate directions or metric-only continuity warnings as review notes when the loop remains coherent.
- If a standard row fails, call `repair` for that row. If a look direction fails, repair the complete containing look row.
- Ordinary jobs allow one retry; cardinal and look jobs allow two. Stop after the controller reports `blocked`.
- Run three isolated blind direction reviewers only when a cardinal remains uncertain or when the user requests strict mode.

Approve only after deterministic validation and visual review:

```text
python PETCTL approve --run-dir RUN_DIR --result pass --notes "short evidence" --semantics RUN_DIR/qa/direction-semantics.json
```

## Package and install

Package to a review directory:

```text
python PETCTL package --run-dir RUN_DIR --output PACKAGE_DIR
```

Install only when the user requested it:

```text
python PETCTL install --run-dir RUN_DIR
```

The installed pair must be `pet.json` plus `spritesheet.webp`, with `spriteVersionNumber: 2`. Tell desktop users to open Settings > Pets, select Refresh, choose the pet, and enter `/pet`.

Read `references/codex-pet-contract.md` only when diagnosing a structural incompatibility. Read `references/animation-rows.md` only when diagnosing row semantics. Read `references/qa-rubric.md` only when resolving a visual QA disagreement.
