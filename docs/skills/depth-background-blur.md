# `depth-background-blur`: shallow depth of field behind the speaker

[← All skills](README.md)

## What it does

Blurs the background behind the speaker for a "portrait mode" look, fully automated, with no manual masks. The blur is AI CineFocus or Depth Map + Lens Blur, already prepared in the base grade template. The skill switches it on per clip (the `DEPTH` node) or per scene with a chosen strength (the Color Group post-clip graph). It turns on node caching so playback stays real time, and checks the result on a still. An optional A/B still comparison of CineFocus and Depth Map is offered.

Why it works this way: the API can't add Resolve FX or change their parameters. It can only apply a DRX, enable or disable nodes and set LUT/CDL. Applying a DRX to a clip replaces its whole node tree, so the chart LUT and skin CDLs would be lost. That's why the blur already sits, **disabled**, in the base template, and this skill only switches it on.

## When it triggers

Automatically when you ask for background blur, bokeh, a "cinematic" or "portrait mode" look, to separate the speaker from a busy background, or to compare CineFocus with Depth Map. Ukrainian trigger phrases: «розмий фон», «боке», «розмиття заднього плану», «як портретний режим». English ones: "depth blur", "CineFocus". In `edit-episode` it is stage A, step 5, after `natural-skin-grade`.

Explicit call:

```
/davinci-editor:depth-background-blur [scene or color group] [light|medium|strong|off]
```

| Argument | Meaning | Default |
|---|---|---|
| `scene` | Color Group of the scene, or a clip list you confirm | none: Claude asks |
| `strength` | `light`, `medium`, `strong` or `off` | `depth_strength` (`medium`) |

## Before you start

- The clips have the base template on their remote `claude` grade version (`log-to-rec709`), with the node `DEPTH` (and `DEPTH BLUR` for the Depth Map variant), set up and **disabled**. If the label is missing, the skill offers the template upgrade from `resolve-core`: you configure the `DEPTH` node once on the template clip (checklist in `log-to-rec709`), and Claude shows the clip list and asks before upgrading.
- The scene's clips are in a Color Group, or you confirm a list.
- For `light` or `strong` only: `depth-light.drx` / `depth-strong.drx` in `templates_dir`. If the file is missing, Claude asks you to capture it once: a clip with **only** the depth node(s) at that strength (no CST, no other nodes), grabbed and exported as a still DRX, then renamed to the exact file name. If `templates_dir` is empty, Claude asks for a folder once.

## Routes and strength

| Route | Strength | Where | When |
|---|---|---|---|
| clip | the template's (`medium`) | `DEPTH` node of each clip, remote `claude` version | default |
| group | `light` / `strong` | post-clip graph of the scene's Color Group, from `depth-<strength>.drx` | you want another strength for a scene |
| off | none | disables the `DEPTH*` nodes; nothing else is reset | you dislike it, or an interview with two people at different distances |

A Color Group's post-clip graph is a separate graph, so a DRX applied there doesn't touch the clip grades.

Where the blur sits in the grade:

- **clip route:** after `SKIN`, before `LOOK`;
- **group route:** after the whole clip grade, `LOOK` included. That's fine for blur, but a strong vignette or grain in `LOOK` gets softened too.

CineFocus or Depth Map:

- **AI CineFocus** (Resolve 21) does depth estimation and bokeh in one node and usually holds hair edges better.
- **Depth Map + Lens Blur** is lighter on the GPU and friendlier to older projects.

If you haven't chosen, Claude offers the A/B.

## Settings

| Key | Default | Effect |
|---|---|---|
| `depth_strength` | `medium` | strength used when `strength` is not given; `medium` = the template's `DEPTH` node |
| `templates_dir` | empty | folder with `depth-light.drx` / `depth-strong.drx` for the group route |

Any setting can be overridden in the prompt: "strong blur for this scene", "turn the blur off in the interview scene".

## Files

| File | Contents |
|---|---|
| `<templates_dir>/depth-light.drx`, `depth-strong.drx` | depth-only templates for the group route, captured once |
| `<work_dir>/<project>/grades/<scene>-depth.json` | per clip: depth nodes, state, cache, date. The API can't read whether a node is enabled, so this record is the source of truth for undo |
| `<work_dir>/<project>/stills/<scene>-depth-a.png`, `-b.png` | A/B stills, only when you ask for the comparison |

## Workflow and approval stops

1. Collects the scene's video clips from the Color Group or a confirmed list, with the remote `claude` version loaded, and finds `DEPTH` / `DEPTH BLUR` by label.
2. Skips clips without a person in front of a background: screen recordings, B-roll close-ups, titles. There, blur only softens the picture. **Asks when unsure.**
3. Group route: looks for `depth-<strength>.drx`. If it is missing, **stops for the one-time capture** (above).
4. **Optional A/B: CineFocus vs Depth Map.** Claude uses one representative clip and a temporary local version `claude-measure`. It exports a still with each variant, restores your version and deletes the temporary one. You get both stills and the no-blur still, with notes on edge artifacts around hair, glasses and hands, and **you pick**.
5. Applies the chosen route:
   - **clip:** enables the `DEPTH*` nodes and turns on node caching (depth estimation is slow), in batches of up to 50 clips;
   - **group:** first makes sure the clip-level `DEPTH*` nodes are disabled, so the blur isn't doubled, then applies the template to the group's post-clip graph. **Asks first** if that graph already has nodes, because they would be replaced;
   - **off:** disables `DEPTH*` on the clips from the record. For the group route it **asks** before replacing the post-clip graph with an empty one.
6. Verifies on a still from the real version (background visibly softer, face sharp, no halo). Then it **asks you to play 5–10 s.** Flicker in the blur means the depth estimate jumps, and Claude suggests CineFocus or the `light` strength.
7. Reports the route, strength, clips changed and skipped (and why), cache state, and where the blur sits in the grade.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Re-apply the base template on a graded clip just to get the depth node. That happens only as a template upgrade, with the chart LUT restored.
- Blur clips without a foreground subject.
- Use Magic Mask: it needs manual strokes and is out of scope for automation.
- Apply a DRX to a clip's own node graph to change the strength. Other strengths go to the Color Group post-clip graph.

## Place in the workflow

`project-bootstrap` → `log-to-rec709` → `chart-match` → `natural-skin-grade` → **`depth-background-blur`** → stage B (`uk-transcribe`, `track-layout`, `text-based-cut`…)

Grade before the cut: the clip route lives in the remote `claude` version and follows each clip into the rough cut. The `light` / `strong` blur lives on the Color Group, so after `text-based-cut` the `edit-episode` stage B checks that the groups survived and reassigns them if not.

## Example prompts

**Minimal:**

> Blur the background in the desk scene.

**With arguments:**

```
/davinci-editor:depth-background-blur desk strong
/davinci-editor:depth-background-blur interview off
```

**Turning it off:**

> Turn the background blur off in the interview scene: two people at different distances.

**Overriding a setting:**

> Light background blur in the kitchen scene instead of the default: the shelves behind me are part of the story, they should stay readable.

**Professional brief:**

> Background blur for the desk scene (Color Group "desk"), medium strength from the template. Skip the screen recordings and the keyboard close-ups in that group. I haven't decided between CineFocus and Depth Map: do the A/B on one talking-head clip and show me both stills next to the no-blur one, with notes on hair and glasses edges. Turn on caching so playback stays real time. At the end list the clips changed and skipped with the reason, and the cache state.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Make it look cinematic" | "Strong background blur, like portrait mode, in the desk scene only. Skip the screen recording in that group, and tell me before replacing anything on the group's post-clip graph." |

The strong prompt names the scene and the strength, which picks the route, and says what to skip and what to confirm, so nothing gets blurred that shouldn't.

## What to check afterwards

- Look at 2–3 clips per scene in the viewer: background softer, face sharp, no halo around hair, glasses or hands.
- Play 5–10 s of each scene: flicker in the blur means the depth estimate jumps. Try CineFocus or `light`.
- Group route: check that a vignette or grain in `LOOK` hasn't gone soft.
- Playback stays real time. If not, check the node cache.
- After the rough cut: the scene's clips are still in their Color Group (the `light` / `strong` blur depends on it).
