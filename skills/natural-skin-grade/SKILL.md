---
name: natural-skin-grade
description: Base grade that protects skin tones in DaVinci Resolve Studio 21+ - measures a real frame after the CST, balances neutrals and exposure with a CDL on the PRIMARY node, nudges skin part-way toward the vectorscope skin tone line with a CDL inside the qualified SKIN node, caps skin saturation, then re-measures the corrected frame. Works per scene on the remote grade version so it survives the cut.
when_to_use: User wants natural / correct skin, a base or primary grade after log conversion, to fix a green, magenta or orange face, or consistent skin across clips of a scene; stage A of edit-episode after chart-match. Triggers - "природний скінтон", "виправ шкіру", "обличчя зелене/пурпурне", "базовий грейд", "первинна корекція", "skin tone", "primary grade".
argument-hint: "[scene or color group] [strength 0-1]"
arguments: [scene, strength]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *skin_grade.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Natural skin grade

Follow `resolve-core` first. Scene: `$scene` (ask if empty; one scene = one lighting setup). Strength: `$strength` (default `${user_config.skin_strength}`): the share of the skin hue error that gets corrected. Natural means *towards* the line, not *onto* it: people differ, and a face forced exactly onto the line looks plastic.

Script: `${CLAUDE_SKILL_DIR}/scripts/skin_grade.py` (pure Python). Self-check: `python3 ${CLAUDE_SKILL_DIR}/scripts/test_skin_grade.py`.

## What the numbers mean

- Hue is the vectorscope angle; the skin tone line is at ~123°. It holds for every skin color: darker and lighter skin differ in **luma and saturation**, not in hue. So the skill corrects hue, caps saturation, and never pushes skin luma toward a "standard" value.
- Within ±3° of the line nothing is changed. A single pass rotates at most 8°.
- `PRIMARY` gets the neutral balance (from something grey or white in the same light) and affects the whole picture. `SKIN` gets the skin rotation and saturation cap, only inside its qualifier, so walls and clothes don't shift.

## 0. Prerequisites

1. Clips carry the base template on the remote `claude` version with labels `CHART`, `CST`, `PRIMARY`, `SKIN` (`log-to-rec709`; `chart-match` before this if a chart was shot).
2. No `SKIN` label → the template is from stage 1. Offer the template upgrade from `resolve-core` §6. If the user declines, correct only neutrals on `PRIMARY` and report the skin offset without fixing it.
3. Scene clips: Color Group `$scene` (`group.GetClipsInTimeline(tl)`) or a list the user confirms.

## 1. Measure a clean frame

Pick one representative frame per scene: face large, frontal, evenly lit, no motion blur. Ask the user if several people or lighting changes are in the scene. Take `item` = the A-roll video item at that timeline frame and `off = frame − item.GetStart()`.

Export it as a still in "after CST, before skin" state, without touching the user's versions, the same way `chart-match` does (`item.ExportFrame` on 21.1.2; older Resolve: playhead on the frame + `project.ExportCurrentFrameAsStill`, see `chart-match` §2):

```python
before = item.GetCurrentVersion()
g0 = item.GetNodeGraph()
lut = g0.GetLUT(next(i for i in range(1, g0.GetNumNodes() + 1) if g0.GetNodeLabel(i) == "CHART"))
item.AddVersion("claude-measure", 0); item.LoadVersionByName("claude-measure", 0)
g = item.GetNodeGraph(); g.ApplyGradeFromDRX(BASE_TEMPLATE, 0)
label = {g.GetNodeLabel(i): i for i in range(1, g.GetNumNodes() + 1)}
try:
    if lut:
        g.SetLUT(label["CHART"], lut)
    for name in ("DEPTH", "DEPTH BLUR", "LOOK"):
        if name in label:
            g.SetNodeEnabled(label[name], False)
    ok = item.ExportFrame(off, {"outputType": "file", "filePath": f"{work}/stills/{scene}-skin.tif"})["success"]
    item.ExportFrame(off, {"outputType": "file", "filePath": f"{work}/stills/{scene}-skin.png"})
finally:
    item.LoadVersionByName(before["versionName"], before["versionType"])
    item.DeleteVersionByName("claude-measure", 0)
result = {"ok": ok, "lut": lut, "restored": item.GetCurrentVersion()}
```

Confirm `restored` equals `before`.

## 2. Choose the sample areas

Read the PNG. Note the real image size (scale viewer coordinates back up).
- Skin: 1–3 boxes `X,Y,W,H` on cheeks and forehead, lit side. Avoid eyes, lips, beard, hair, specular highlights and deep shadow.
- Neutral: one box on something truly grey or white in the same light (wall, paper, shirt). Skip it if there is none, and don't use a colored wall.
- Not sure where the face is → ask the user for the boxes instead of guessing.

## 3. Analyze

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/skin_grade.py analyze "<work>/stills/<scene>-skin.tif" \
  --skin X,Y,W,H [--skin ...] [--neutral X,Y,W,H] --strength <strength> --max-sat ${user_config.skin_max_saturation}
```

Read `warnings` first: clipped samples or a colored "neutral" mean the boxes are wrong. Fix and rerun. Then show the user:
- skin hue offset from the line, before → predicted; skin luma; saturation ratio;
- the `PRIMARY` and `SKIN` CDLs;
- a plain-language summary ("обличчя на 9° в пурпур, повертаю на 5°; шкіру трохи приглушую").

Exposure: the script never changes it. Suggest it (a `PRIMARY` slope applied equally to all channels) only if the warning says the face is badly exposed, and only with the user's yes.

## 4. Verify before touching the real grade

There is no `GetCDL`, so the re-read rule from `resolve-core` §2 can't apply here. The proof is a measured still:
1. Repeat step 1 on a fresh `claude-measure` version, and before exporting also `item.SetCDL({"NodeIndex": label["PRIMARY"], **primary_cdl})` and the same for `SKIN` (`SetCDL` is a `TimelineItem` call; it acts on the version currently loaded, here `claude-measure`). Export `<scene>-skin-after.tif`, then restore and delete the temporary version.
2. Run `analyze` on it with the same boxes and **no** `--neutral`. Its `skin_before` is the real result. More than 2° off the prediction means the qualifier isn't catching the face or another node interferes: stop and say so.
3. Show both PNGs side by side (or ask the user to compare in the viewer). Get a yes.

## 5. Apply to the scene

On every clip of the scene, on the remote `claude` version (`LoadVersionByName("claude", 1)`), find `PRIMARY` and `SKIN` by label and call `item.SetCDL({...})` for each. Batches of ≤ 50. Record per clip what you set in `<work>/grades/<scene>-skin.json` (the only record, since CDLs can't be read back).

A clip whose framing or light clearly differs (another person, window light) gets its own measurement, not the scene's CDL.

## 6. Report

Per scene: frame used, skin offset before → after (measured), CDLs, clips changed, anything skipped. Next: `depth-background-blur`, then the user's creative `LOOK`.

## Never

- Apply a DRX to a graded clip to add skin nodes (it wipes the chart LUT). Use the template upgrade.
- Move skin onto the line at full strength without the user asking, or normalize skin luma.
- Measure on a still with `LOOK` or `DEPTH` active.
