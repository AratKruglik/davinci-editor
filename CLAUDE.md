# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`davinci-editor`: a Claude Code / Cowork plugin of skills that edit in DaVinci Resolve Studio 21+ through Resolve's own MCP server (`DaVinci_Resolve`, tools `mcp__DaVinci_Resolve__*`). There is no app to build: the product is `skills/<skill>/SKILL.md` (instructions for the model) plus small Python helpers in `skills/<skill>/scripts/`. Manifest and user settings: `.claude-plugin/plugin.json`.

## Commands

All scripts are Python 3.10+ standard library only; nothing to install. Each helper has either a `selftest` subcommand or a `test_*.py` file; run one directly:

```bash
python3 skills/resolve-core/scripts/tc.py selftest
python3 skills/chart-match/scripts/test_chart_match.py
claude plugin validate .
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold   # real, billed model runs
python3 scripts/build_cowork.py                                  # → dist/davinci-editor-cowork-<version>.zip
```

The full self-test list lives in two places that must stay in sync: README "Development" and `.github/workflows/release.yml`. A new script with a selftest goes into both.

## Architecture

- **`resolve-core`** (hidden, `user-invocable: false`) holds the shared rules every other skill says to "follow": connection check, safe `run_script` use, backups before edits, timecode math, tracks by role, marker etiquette, the color node-label convention, file locations. Verified API gotchas and the append calibration are in `skills/resolve-core/reference.md`. Read these before changing any skill's Resolve logic.
- **Shared helpers** in `skills/resolve-core/scripts/`: `tc.py` (timecode/frames; other skills import it via `sys.path.insert`), `timeline_map.py` (maps transcript words onto a cut timeline and back), `show.py`, and `guard.py`.
- **Delete guard**: skills that change the project declare a `PreToolUse` hook in their frontmatter running `guard.py` on `mcp__DaVinci_Resolve__run_script.*`; it turns delete/reset/clear API calls into a permission prompt. Changes to `guard.py` need its selftest to keep passing (recent commits closed Unicode/reflection bypasses).
- **Skill frontmatter** carries `allowed-tools` (pre-approved MCP tools and `Bash(python3 *<script>.py *)` patterns), `arguments`, and settings via `${user_config.<key>}`; scripts are referenced as `${CLAUDE_SKILL_DIR}/scripts/...`. A new setting goes into `userConfig` in `plugin.json` and the table in `docs/settings.md`.
- **Orchestration**: `edit-episode` runs the whole workflow in stages with approval stops, keeping progress in `episode.md`; `marker-edit` maps marker colors to tasks and dispatches to the matching skills. Marker colors and track roles are design contracts documented in `docs/marker-color-system.md` and `docs/track-layout.md`.
- **Color pipeline**: the API cannot create nodes, so color skills work on a user-captured DRX template with labeled serial nodes `CHART → CST → PRIMARY → SKIN → DEPTH → LOOK`, found by label, edited only with per-node calls, stored in a remote grade version named `claude`.
- **Cowork build**: `scripts/build_cowork.py` copies `skills/` without `evals/`, renames the plugin to `davinci-editor-cowork`, bundles `.mcp.json`, and rewrites the literal prefix `mcp__DaVinci_Resolve__` in every `.md` to the plugin-scoped name. Always spell tool names with that exact prefix in skills.

## Evals

`skills/<skill>/evals/<case>/`: `case.yaml` (expected outcome, `scaffold_script: place-files.sh`), `prompt.md`, `graders/NN-*.md` (LLM graders with frontmatter), and `files/` with an offline `resolve_state.json` plus pre-written `resolve-work/` outputs, so no running Resolve is needed. Media fixtures (`.wav/.mov/.png/.tif/.mp4`) are gitignored and kept local only.

## Releasing

Bump `version` in `.claude-plugin/plugin.json`, commit, push a tag `v<version>` (CI fails if they differ); the release workflow runs self-tests and publishes the Cowork zip.

## Conventions

- README.md is in English; `docs/` design notes are in Ukrainian. Skills talk to the user in the user's language but keep Resolve UI names in English.
- Skill scripts never write into media folders; outputs go under `${user_config.work_dir}/<project>/`.
