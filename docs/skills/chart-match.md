# `chart-match`: ColorChecker match before the CST

[← All skills](README.md)

## What it does

Matches Apple Log footage to an X-Rite ColorChecker Classic 24 chart. It measures the chart on an ungraded frame, fits white balance, exposure and a 3×3 color matrix in linear light, writes the correction as a DCTL (or a 33-point LUT) on the `CHART` node of every clip in the scene, then measures again and reports the CIEDE2000 error (ΔE00) per patch.

The correction sits on `CHART`, **before** the CST, so it works on the real camera signal and the CST still receives valid Apple Log. It is a technical match, not a look: skin and creative grading come next.

## When it triggers

Automatically when you shot a ColorChecker and want accurate, consistent color, white balance and exposure across clips or cameras before grading, or when a Sand marker marks a chart frame. Trigger phrases: «піджени колір по таблиці», «корекція за колорчекером», "chart match", "color checker", «вирівняй баланс білого по таблиці», «зроби однаковий колір на всіх кліпах сцени». In `edit-episode` it is stage A, step 3, only if a chart was shot.

Explicit call:

```
/davinci-editor:chart-match [scene or color group name]
```

| Argument | Meaning | Default |
|---|---|---|
| `scene` | scene or Color Group the chart belongs to (one chart = one lighting setup = one scene) | asks if empty |

## Before you start

- Clips carry the base template with labeled nodes `CHART` → `CST` → … on the remote `claude` version: run [`log-to-rec709`](log-to-rec709.md) first. That's also where you capture the DRX template once; `chart-match` uses the same template from `templates_dir` to measure.
- **Apple Log only.** The bundled math decodes Apple Log (Rec.2020 gamut). For Apple Log 2, HLG, PQ or anything else the skill stops and tells you chart matching for that format isn't supported yet.
- The project is on node-based color science. With Resolve Color Management on, the skill stops and explains: the measured values would be in timeline space. It continues only after you switch the project to the node-based route.
- A **Sand** marker on the chart frame (below). A good chart frame: sharp, flat-lit, the chart fills at least 1/6 of the frame, no glare.
- The chart was shot **in the same light** as the scene. A chart in different light makes things worse, not better.

## Markers it reads

| Color | Task | Effect |
|---|---|---|
| **Sand** | `chart` | the frame to measure; placed on the clip in the Media Pool so it's tied to the footage and visible from any timeline |

- One Sand marker per scene; with several, the one for `scene` is used.
- Markers whose `customData` is `claude:done:chart-match:*` are skipped. A timeline or clip marker named or noted `chart` / `таблиця` is accepted as a fallback.
- No marker → Claude asks you to place one. It never places a Sand marker itself (your colors are yours; Claude's own markers are Cream only).
- When done, it writes `claude:done:chart-match:<date>` into the marker's `customData`, never touching its color, name or note.

The color comes from `marker_colors`. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## How the match works

The still's Apple Log code values are decoded to linear Rec.2020 scene light. Per-channel gains from the neutral 8…3.5 patches set white balance and exposure. A 3×3 matrix whose rows sum to 1 (so greys stay neutral) is least-squares fitted to the 2014 X-Rite reference, and the result is re-encoded to Apple Log.

Quality gate on the predicted error:

| Predicted ΔE00 | Decision |
|---|---|
| mean ≤ 2 and max ≤ 5 | proceeds |
| mean 2–3 | proceeds, names the patches that are off |
| mean > 3 | stops: usually wrong patch positions, glare, mixed light, or a still that wasn't raw log |

Clipped patches are excluded automatically; if a grey patch 8–3.5 clipped, the shot is overexposed and you're told so.

## Settings

| Key | Default | Effect |
|---|---|---|
| `marker_colors` | `…,Sand=chart,…` | which marker color marks the chart frame |
| `templates_dir` | empty | where the base DRX template used for measuring is found |
| `work_dir` | `resolve-work` | where stills and the generated correction are written |

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `stills/<scene>-chart-log.tif`, `.png` | the ungraded chart frame (TIFF to measure, PNG to look at) |
| `chart/chart-<scene>.dctl` | the fitted correction |
| `chart/chart-<scene>.lut-transform.py` | the same correction as a LUT transform, for the fallback |
| `stills/<scene>-chart-corrected.tif` | the chart frame after the correction, measured again |

In Resolve the correction is written as the DCTL `MCP/chart-<scene>.dctl`, or the LUT `MCP/chart-<scene>.cube` if the node refuses the DCTL.

## Workflow and approval stops

1. Finds the Sand marker for the scene and that frame on a timeline that contains the clip. On Resolve 21.1.2+ the stills are exported straight from the clip, so your playhead isn't moved; older versions move the playhead onto the frame.
2. Exports an ungraded still on a temporary **local** version `claude-measure` (template applied, every node disabled), then restores your version and deletes the temporary one. Your grade is never touched. Deleting `claude-measure` is exempt from the delete prompt.
3. Reads the PNG and locates the patches by four of them: 1 (dark skin), 6 (bluish green), 24 (black), 19 (white), whatever the chart's orientation. If it can't tell confidently, it **asks you** for the four pixel coordinates (for example from Resolve's viewer) instead of guessing.
4. Fits the correction. Patches that don't look uniform mean a position missed: it fixes the coordinates and fits again. Then applies the quality gate above.
5. Writes the DCTL (it's compiled first; a compile error stops the run).
6. **Approval: the clip list**, only when there is no Color Group named `scene` (with one, the group's clips are the scene). On the remote `claude` version of every clip it sets the DCTL on the node labeled `CHART` and reads it back. If the node refuses the DCTL, it falls back to a 33-point LUT (exact vs tiny interpolation error; you're told). If you use Color Groups and the group's pre-clip graph has a `CHART` node, one correction goes there for the whole scene.
7. Verifies on the real frame: the same temporary-version export with only `CHART` enabled, measured again. A gap of more than 1 ΔE from the prediction means the node isn't receiving what it should (RCM, an extra node, wrong clip), and it says so.
8. Marks the Sand marker done and reports.

Any other script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Fit on a graded or RCM-transformed still.
- Disable nodes on your real grade versions: it measures on a temporary local version.
- Reuse one scene's correction on another lighting setup without saying so.
- Run on Apple Log 2, HLG or PQ with a workaround: the result would look plausible and be wrong.
- Place a Sand marker, or change a marker's color, name or note.

## Place in the workflow

`project-bootstrap` → `log-to-rec709` → **`chart-match`** → `natural-skin-grade` → `depth-background-blur`

Next: `natural-skin-grade` on `PRIMARY` and `SKIN`, then your creative `LOOK`.

## Example prompts

**Minimal:**

> Match the color to the chart for the scene kitchen.

**With arguments:**

```
/davinci-editor:chart-match kitchen
```

**Overriding a setting:**

> Chart match for the scene desk. My grade templates are in `~/Grades/templates`, and the chart frame is on a Sand marker on IMG_4140.

**Professional brief:**

> Chart match for the scene kitchen: Color Group `kitchen`, clips IMG_4127–IMG_4129, all Apple Log, window light. The Sand marker is on IMG_4127 where the chart is flat to camera; it's slightly rotated in the frame. If you're not sure about the patch positions, ask me for the coordinates rather than guessing. Put one correction on the group's pre-clip graph if it has a `CHART` node, otherwise on each clip. Report ΔE per patch before → after, mean and max, and which patches stay above 3.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Fix the colors with the checker" | "Chart match for scene kitchen from the Sand marker on IMG_4127; apply to every clip in Color Group `kitchen` and report ΔE per patch before and after." |

The strong prompt names the scene, the chart frame and the clips that share the light, so the correction lands on exactly the clips it was measured for.

## What to check afterwards

- The ΔE report: mean and max after, and which patches are still off.
- Compare the scene's clips in the viewer: white balance and exposure should now match.
- On the Color page the `CHART` node of each clip (or the group's pre-clip graph) holds the DCTL or LUT.
- The Sand marker is unchanged in color, name and note.
