---
name: motionvfx-catalog
description: Builds and searches a catalog of the Fusion templates installed for DaVinci Resolve - MotionVFX and other packs in .drfx bundles or loose .setting files - with exact names, category (Titles, Transitions, Effects, Generators), vendor, pack and published controls (text fields, colors). Other davinci-editor skills pick titles, transitions and PiP placeholders from it instead of guessing names.
when_to_use: User asks which MotionVFX titles, transitions or effects are installed, installed a new pack, or another skill needs an exact template name (Cocoa transition markers, PiP placeholders, titles). Triggers - "які є титри MotionVFX", "онови каталог шаблонів", "знайди перехід", "що в mTutorial", "motionvfx catalog".
argument-hint: "[scan | search words]"
arguments: [action]
context: fork
agent: general-purpose
model: haiku
allowed-tools:
  - "Bash(python3 *catalog.py *)"
  - "Read"
---

# MotionVFX / Fusion template catalog

You are running as a forked helper. Do the job, then reply with a short summary; the full data stays in the catalog file.

Action: `$action` (empty = `scan`). For `search`, the query is everything in `$ARGUMENTS` after the word `search`.

Catalog file: `${user_config.work_dir}/motionvfx-catalog.json` (machine-wide, not per project). If the `${user_config.…}` placeholder reached you unsubstituted, use `resolve-work/motionvfx-catalog.json`.

## scan

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/catalog.py scan --out "<catalog file>"
```

It reads `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates` and the same path under `/Library`, opens every `.drfx` (zip) and `.setting`, and never changes them. For templates elsewhere add `--dir <folder>`. Self-check if results look wrong: `python3 ${CLAUDE_SKILL_DIR}/scripts/test_catalog.py`.

Reply with: total, counts per vendor/category (from the printed summary), unreadable files, and 3–5 packs most useful for tutorials (lower thirds, callouts, placeholders/corner screens for PiP, transitions).

## search

Anything after `search` is the query:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/catalog.py search "<catalog file>" [--category Titles|Transitions|Effects|Generators] [--vendor MotionVFX] [--text-inputs N] words...
```

No catalog yet → run `scan` first. Reply with the best 5–10 matches: exact `name` (that is what Resolve's insert calls take), category, pack, number of text fields, main controls.

## Facts for the skills that use the catalog

- Name passed to Resolve = the `.setting` file name without extension, exactly as in the catalog (spaces, brackets and all).
- Titles: `tl.InsertFusionTitleIntoTimeline(name)`; text goes into the macro's `StyledText` inputs (`text_inputs` says how many). It *inserts with ripple* at the playhead on a track the script can't choose (`resolve-core` §10): insert and move it onto `Titles` by the route in `fusion-motion-graphics` §3 step 4.
- Transitions: `item.AddTransition({"type": name, "category": "fusion", "position": "end", "alignment": "center", "duration": frames})`.
- Effects (placeholders, corner screens, frames, camera moves), Resolve 21.1.2+ (version gate in `resolve-core` §10): the calling skill attaches them to a **media** item with its own backup and guard; this helper only reads files. Recipe (`resolve-core/reference.md#resolve-2112-editing-calls`):
  - id: look the catalog `name` up in `resolve.GetEffectsList("video")` (`category` `fusion`); several hits → pick the one whose `id` contains the catalog `pack`. Never build the id by hand.
  - `fx = item.AddEffect("fusion", id)`: only media items take effects (`None` on a generator).
  - `macro = fx.GetFusionComp().FindTool(<catalog "macro">)` (fallback `GetToolList(False)`); input ids from `macro.GetInputList()` (the catalog's `inputs` are display names, not ids), `SetInput(id, v)`, re-read with `GetInput(id)`.
  - Undo: `item.DeleteEffects([fx])` (guarded).
  - Older Resolve: list the clips and ask the user to drag the effect on, or use the built-in transform route.
- MotionVFX packs are licensed per user: never copy `.drfx` files into the project or the work folder.
