---
name: depth-background-blur
description: Shallow depth-of-field look in DaVinci Resolve Studio 21+ - blurs the background behind the speaker with AI CineFocus or Depth Map + Lens Blur from the base grade template, switched on per clip (DEPTH node) or per scene with a chosen strength (Color Group post-clip graph), with node caching for playback and a still-based A/B check. Fully automated, no manual masks.
when_to_use: User wants background blur, bokeh, a "cinematic" or "portrait mode" look, to separate the speaker from a busy background, or to compare CineFocus with Depth Map; stage A of edit-episode after natural-skin-grade. Triggers - "розмий фон", "боке", "розмиття заднього плану", "як портретний режим", "depth blur", "CineFocus".
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
2. Find `DEPTH` (and `DEPTH BLUR`) by label on each. Missing → template upgrade from `resolve-core` §6 (the user configures the `DEPTH` node once on the template clip; `log-to-rec709` §2 has the checklist).
3. Skip clips without a person in front of a background (screen recordings, B-roll close-ups, titles): blur there just softens the picture. Ask when unsure.

## 2. Templates for the group route

Needed only for `light`/`strong`. Look for `depth-light.drx` / `depth-strong.drx` in `${user_config.templates_dir}`. Missing → one-time capture: ask the user to set up a clip with **only** the depth node(s) at that strength (no CST, no other nodes), grab and export it as a still DRX (`log-to-rec709` §2, step 2 shows the calls), rename to the exact file name.

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

## 6. Report

Route, strength, clips changed / skipped and why, cache state. Say where the blur sits: the clip route runs after `SKIN` and before `LOOK`; the group route runs after the whole clip grade, `LOOK` included (fine for blur, but a strong vignette or grain in `LOOK` gets softened too).

## Never

- Re-apply the base template on a graded clip just to get the depth node (template upgrade only, with the chart LUT restored).
- Blur clips without a foreground subject.
- Use Magic Mask: it needs manual strokes and is out of scope for automation.
