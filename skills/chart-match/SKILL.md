---
name: chart-match
description: Matches Apple Log footage to an X-Rite ColorChecker Classic 24 chart in DaVinci Resolve Studio 21+ - measures the chart on an ungraded frame, fits white balance, exposure and a neutral-preserving 3x3 matrix in linear light, writes the correction as a DCTL (or 33-point LUT) on the CHART node of every clip in the scene, then re-measures and reports CIEDE2000 error per patch.
when_to_use: User shot a ColorChecker / color chart and wants accurate, consistent color, white balance and exposure across clips or cameras before grading. Also when a Sand marker marks a chart frame. Triggers - "піджени колір по таблиці", "корекція за колорчекером", "chart match", "color checker", "вирівняй баланс білого по таблиці", "зроби однаковий колір на всіх кліпах сцени".
argument-hint: "[scene or color group name]"
arguments: [scene]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_docs"
  - "Bash(python3 *chart_match.py *)"
  - "Read"
---

# ColorChecker match

Follow `resolve-core` first. Scene: `$scene` (ask if empty; one chart = one lighting setup = one scene).

Prerequisite: clips carry the base template with labeled nodes `CHART` → `CST` → … (run `log-to-rec709` first). The correction lives on `CHART`, **before** the CST, so it works on the real camera signal and the CST still sees valid Apple Log.

How the math works (so you can explain results): the still's Apple Log code values are decoded to linear Rec.2020 scene light; per-channel gains from the neutral 8…3.5 patches set white balance and exposure; a 3×3 matrix with rows summing to 1 (greys stay neutral) is least-squares fitted to the 2014 X-Rite reference; the result is re-encoded to Apple Log. Accuracy is reported as CIEDE2000 (ΔE00) per patch.

Scripts: `${CLAUDE_SKILL_DIR}/scripts/chart_match.py` (pure Python 3, no dependencies). Self-check if anything looks off: `python3 ${CLAUDE_SKILL_DIR}/scripts/test_chart_match.py`.

## 0. Supported footage

The bundled math decodes **Apple Log (Rec.2020 gamut) only**. Check the clip format detected by `log-to-rec709` (or detect it the same way). Apple Log 2, HLG, PQ or anything else → stop and tell the user chart matching for that format is not supported yet. Never run it with `--log linear` as a workaround: the result would look plausible and be wrong.

## 1. Find the chart frame

The user marks the chart frame with a **Sand** marker (color from `${user_config.marker_colors}`, task `chart`) on the clip in the media pool, so it is tied to the footage and visible from any timeline.

1. Read `clip.GetMarkers()` for the clips of the scene and keep the Sand markers (skip ones whose `customData` is `claude:done:chart-match:*`). Also accept a timeline/clip marker named or noted `chart` / `таблиця` as a fallback.
2. Several → one per scene; pick the one for `$scene`. None → ask the user to put a Sand marker on a frame where the chart is sharp, flat-lit, fills ≥ 1/6 of the frame and has no glare (don't place it yourself: user marker colors are theirs; Claude's own markers are Cream only).
3. Put the playhead on that frame of a timeline that contains the clip: timeline frame = item start + (marker frame − item source start).
4. The chart must be in the same light as the scene. A chart shot in different light than the takes makes things worse, not better: say so if the user mentions it.

## 2. Export an ungraded still

Color management must be off for the export to contain raw Apple Log: check `project.GetSettings()["colorScienceMode"]` is `davinciYRGB`. If RCM is on, stop and explain (the measured values would be in timeline space); offer to continue only after the user switches the project to the node-based route.

Measure on a throw-away **local** version so the user's grade is never touched (there is no API to read which nodes are enabled, so disabling nodes on the real grade can't be undone exactly):

```python
item = tl.GetCurrentVideoItem()
before = item.GetCurrentVersion()                      # e.g. {"versionName": "claude", "versionType": 1}
item.AddVersion("claude-measure", 0); item.LoadVersionByName("claude-measure", 0)
g = item.GetNodeGraph(); g.ApplyGradeFromDRX(BASE_TEMPLATE, 0)
try:
    for i in range(1, g.GetNumNodes() + 1):
        g.SetNodeEnabled(i, False)
    ok = project.ExportCurrentFrameAsStill(f"{work}/stills/{scene}-chart-log.tif")
    project.ExportCurrentFrameAsStill(f"{work}/stills/{scene}-chart-log.png")
finally:
    item.LoadVersionByName(before["versionName"], before["versionType"])
    item.DeleteVersionByName("claude-measure", 0)
result = {"ok": ok, "restored": item.GetCurrentVersion()}
```

`BASE_TEMPLATE` is the base DRX for this log version from `${user_config.templates_dir}`. Confirm `restored` equals `before`.

`work` = `${user_config.work_dir}/<project name>`.

## 3. Locate the patches

1. Read the PNG (Read tool) and note the image size from the file (the viewer may show it downscaled; scale coordinates back to full resolution).
2. Estimate pixel centers of patch 1 (dark skin, brown), patch 6 (bluish green), patch 24 (black), patch 19 (white). Orientation is whatever the frame shows: if the chart is rotated or upside-down, the corner order still follows those patches, not the image corners.
3. If you can't tell confidently, ask the user for the four coordinates (e.g. from Resolve's viewer with the mouse) instead of guessing.

## 4. Fit

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/chart_match.py fit "<work>/stills/<scene>-chart-log.tif" \
  --corners X1,Y1 X6,Y6 X24,Y24 X19,Y19 --out "<work>/chart" --name "chart-<scene>"
```

Read the JSON:
- `warnings` — "not uniform" means a center missed its patch: fix corners and rerun (look at `centers`). "clipped" patches are excluded automatically; if any grey 8–3.5 clipped, the shot is overexposed: tell the user.
- `before` / `after_predicted` — mean and max ΔE00.

Quality gate (predicted): mean ≤ 2 and max ≤ 5 → proceed. Mean 2–3 → proceed but tell the user which patches are off. Mean > 3 → stop: usually wrong corners, glare, mixed light, or the still wasn't raw log.

## 5. Write and apply

1. Write the DCTL with `update_dctl` (path `chart-<scene>.dctl`, content = the generated `.dctl` file). It is compiled before writing; a compile error means stop and report.
2. On the remote `claude` version of every clip in the scene (scene = Color Group `$scene` if it exists, else ask the user to confirm the clip list), find the `CHART` node index by label and `graph.SetLUT(idx, "MCP/chart-<scene>.dctl")`; re-read `graph.GetLUT(idx)`.
3. If `SetLUT` refuses the DCTL (re-read is empty), fall back: `generate_lut` with path `chart-<scene>.cube`, size 33, transform = contents of the generated `.lut-transform.py`; then `SetLUT(idx, "MCP/chart-<scene>.cube")`. Mention that the DCTL is exact while the LUT has tiny interpolation error.
4. Prefer the Color Group's pre-clip graph if the user uses groups — one LUT for the whole scene instead of per clip — but only if its pre-clip graph has a node labeled `CHART`.

## 6. Verify on the real frame

1. Same throw-away local version as in step 2, but after applying the template set the same `CHART` LUT/DCTL on it and disable every node except `CHART`; export `<scene>-chart-corrected.tif`; restore the previous version and delete the temporary one.
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/chart_match.py measure "<...>-chart-corrected.tif" --corners <same>`
3. Its `before` block is the real post-correction error. Compare with the prediction; a gap > 1 ΔE means the node isn't receiving what we think (RCM, an extra node, wrong clip).

## 7. Mark done and report

Write `claude:done:chart-match:<YYYY-MM-DD>` into the Sand marker's `customData` (`clip.UpdateMarkerCustomData(frame, value)`, re-read with `GetMarkerCustomData`). Never change its color, name or note.

Report: table per patch (name, ΔE before → after), mean/max before → after, which clips got the correction, files written. Remind the user: this is a technical match, not a look; skin and creative grading come next on `PRIMARY` and `LOOK`.

## Never

- Fit on a graded or RCM-transformed still.
- Disable nodes on the user's real grade versions; measure on a temporary local version.
- Reuse one scene's correction on another lighting setup without saying so.
