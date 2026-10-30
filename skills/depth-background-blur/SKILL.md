---
name: depth-background-blur
description: Shallow depth-of-field look in DaVinci Resolve Studio 21+ - blurs the background behind the speaker with AI CineFocus or Depth Map + Lens Blur from the base grade template, switched on per clip (DEPTH node) or per scene with a chosen strength (Color Group post-clip graph), with node caching for playback and a still-based A/B check. Fully automated, no manual masks.
when_to_use: User wants background blur, bokeh, a "cinematic" or "portrait mode" look, to separate the speaker from a busy background, or to compare CineFocus with Depth Map; stage A of edit-episode after natural-skin-grade. Also rack focus requests (manual only, see "Rack focus"). Triggers - "розмий фон", "боке", "розмиття заднього плану", "як портретний режим", "depth blur", "CineFocus", "перевід фокусу", "rack focus".
argument-hint: "[scene or color group] [light|medium|strong|off]"
arguments: [scene, strength]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Depth background blur

Follow `resolve-core` first. Scene: `$scene` (ask if empty). Strength: `$strength` (default `${user_config.depth_strength}`).

## Why it works this way

- The API can't add Resolve FX or change their parameters; it can only apply a DRX, enable/disable nodes and set LUT/CDL.
- Applying a DRX to a clip replaces its whole node tree (chart LUT and skin CDLs would be lost). So the blur already lives, **disabled**, in the base template as the `DEPTH` node (and `DEPTH BLUR` for the Depth Map variant); this skill only switches it on.
- A Color Group's post-clip graph is a separate graph, so applying a DRX there doesn't touch clip grades. That's the route for a strength other than the template's.

| Route | Strength | Where | When |
|---|---|---|---|
| clip | the template's (`medium`) | `DEPTH` node of each clip, remote `claude` version | default |
| group | `light` / `strong` | post-clip graph of the scene's Color Group, from `depth-<strength>.drx` | user wants another strength for a scene |
| off | — | disable `DEPTH*` nodes / reset nothing else | user dislikes it, or interview with two people at different distances |

AI CineFocus (Resolve 21) does depth estimation and bokeh in one node and usually holds hair edges better. Depth Map + Lens Blur is lighter on the GPU and older-project friendly. If the user hasn't chosen, offer the A/B in step 3.

## 1. Check the clips

1. Scene clips from Color Group `$scene` or a confirmed list. Video items only, remote `claude` version loaded.
2. Find `DEPTH` (and `DEPTH BLUR`) by label on each. Missing → template upgrade from `resolve-core` §6 (the user configures the `DEPTH` node once on the template clip with the checklist in "DEPTH node setup" below).
3. Skip clips without a person in front of a background (screen recordings, B-roll close-ups, titles): blur there just softens the picture. Ask when unsure.

## DEPTH node setup (one-time, by the user)

The API can't set these parameters, so give the user this checklist whenever a template with depth nodes is built or re-captured (base template, `depth-light.drx`, `depth-strong.drx`). Work on a talking-head clip on the Color page. Wait for "готово".

**AI CineFocus** (one node `DEPTH`):
1. Effects → search `CineFocus` → drag it onto the `DEPTH` node.
2. Press the **Focus** button and click the speaker's eyes. The preview shows in-focus areas clear and out-of-focus areas highlighted white: the whole face and hair must stay clear.
3. Adjust **Focus Distance** and **Depth of Field** until the background behind the speaker is white in that preview and the speaker isn't. The blur amount is the strength (`light` / `medium` / `strong`).
4. **Quality and Speed** → turn on **Skip foreground blur**: hands, mic and desk in front of the speaker stay sharp instead of getting smeared.
5. **Result → Aperture**: bokeh shape to taste; keep it modest for a talking head.
6. Make sure the viewer shows the normal picture, not the white focus highlight, before the capture.

**Depth Map + Lens Blur** (two serial nodes, `DEPTH` **before** `DEPTH BLUR`):
1. Effects → `Lens Blur` onto `DEPTH BLUR`; set the blur look (this is the strength).
2. Effects → `Depth Map` onto `DEPTH`, the node in front of it.
3. Drag the **blue key output** of `DEPTH` to the **blue key input** of `DEPTH BLUR`: the map then drives where the blur goes.
4. Depth Map **Quality → Faster** (playback stays usable; go up only if hair edges break).
5. Turn on **Invert**: in focus = black, out of focus = white. Adjust the map levels until the speaker is **completely black** and the background **completely white**; grey on the face means a soft face.
6. Turn **off** the depth map preview. If it stays on, the template outputs the grey map instead of the picture.

Then disable the depth node(s) (Cmd/Ctrl+D) for the base template (this skill turns them on per clip); leave them enabled in `depth-light.drx` / `depth-strong.drx`. Grab and export the still as `log-to-rec709` §2 shows.

## 2. Templates for the group route

Needed only for `light`/`strong`. Look for `depth-light.drx` / `depth-strong.drx` in `${user_config.templates_dir}`. Missing → one-time capture: ask the user to set up a clip with **only** the depth node(s) at that strength (no CST, no other nodes), following "DEPTH node setup", grab and export it as a still DRX (`log-to-rec709` §2, step 2 shows the calls), rename to the exact file name.

## 3. Optional A/B: CineFocus vs Depth Map

On one representative clip, on a temporary local version `claude-measure` (pattern from `natural-skin-grade` §1): apply the base template, restore the chart LUT, enable `DEPTH*`, export `<work>/stills/<scene>-depth-a.png`; repeat with the other variant's template, export `-b.png`; restore the user's version and delete the temporary one. Show both and the no-blur still; let the user pick. Note edge artifacts around hair, glasses, hands.

## 4. Apply

Clip route, per item (batches ≤ 50):

```python
item.LoadVersionByName("claude", 1)
g = item.GetNodeGraph()
idx = [i for i in range(1, g.GetNumNodes() + 1) if g.GetNodeLabel(i).startswith("DEPTH")]
for i in idx:
    g.SetNodeEnabled(i, True)
    g.SetNodeCacheMode(i, resolve.CACHE_ENABLED)      # depth estimation is slow; cache keeps playback real time
rows.append({"clip": item.GetName(), "depth_nodes": idx, "cache": [g.GetNodeCacheMode(i) for i in idx]})
```

There is no getter for "enabled", so the record in `<work>/grades/<scene>-depth.json` (clip, nodes, state, date) is the source of truth for undo.

Group route: make sure the clip-level `DEPTH*` nodes are **disabled** (no double blur), then `group.GetPostClipNodeGraph().ApplyGradeFromDRX(depth_template, 0)`. Ask first if that post-clip graph already has nodes: they would be replaced.

`off`: disable `DEPTH*` on the clips from the record; for the group route ask before replacing the post-clip graph with an empty one.

## 5. Verify

Export a still of one clip from the real version (playhead on it) and look at it: background visibly softer, face sharp, no halo. Ask the user to play 5–10 s: flicker in the blur means the depth estimate jumps; then suggest CineFocus or the `light` strength.

What a bad still usually means (all fixed in the template per "DEPTH node setup", then re-captured; for the base template that's a template upgrade):

| Still shows | Cause |
|---|---|
| grey depth map instead of the picture | depth map preview left on in `DEPTH` |
| white overlay on the background | CineFocus focus highlight left on |
| no blur at all (Depth Map variant) | key output of `DEPTH` not connected to `DEPTH BLUR`, or Invert off |
| face or hair soft | focus point not on the eyes (CineFocus), or map levels leave the speaker grey |
| hands, mic or desk blurred | Skip foreground blur off (CineFocus) |

## 6. Report

Route, strength, clips changed / skipped and why, cache state. Say where the blur sits: the clip route runs after `SKIN` and before `LOOK`; the group route runs after the whole clip grade, `LOOK` included (fine for blur, but a strong vignette or grain in `LOOK` gets softened too).

## Rack focus

A focus pull from one depth to another needs keyframes on the effect, and the API can't keyframe Resolve FX. Don't fake it with node toggles. If asked, give the user the manual steps on a **separate** node after `LOOK` (or on the clip's `claude` version with their OK), not on the template's `DEPTH`: Depth Map → Lens Blur wired as in "DEPTH node setup"; playhead on the first frame, turn on **Isolate specific depth** and keyframe **Target Depth**; playhead on the last frame, set Target Depth to where the second subject is sharp (check in the depth preview); turn off the depth map preview.

## Never

- Re-apply the base template on a graded clip just to get the depth node (template upgrade only, with the chart LUT restored).
- Blur clips without a foreground subject.
- Use Magic Mask: it needs manual strokes and is out of scope for automation.
- Ship a template with the depth map preview or the CineFocus focus highlight left on.
