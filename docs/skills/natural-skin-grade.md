# `natural-skin-grade`: measured base grade that keeps skin natural

[← All skills](README.md)

## What it does

Builds the base grade of a scene from a measured frame after the CST. It balances neutrals and exposure with a CDL on the `PRIMARY` node, nudges skin **part-way** toward the vectorscope skin tone line with a CDL inside the qualified `SKIN` node, caps skin saturation, then measures the corrected frame again. It works per scene on the remote `claude` grade version, so the grade survives the cut.

Natural means *toward* the line, not *onto* it: people differ, and a face forced exactly onto the line looks plastic.

## When it triggers

Automatically when you want natural or correct skin, a base or primary grade after log conversion, to fix a green, magenta or orange face, or consistent skin across the clips of a scene. Trigger phrases: «природний скінтон», «виправ шкіру», «обличчя зелене/пурпурне», «базовий грейд», «первинна корекція», "skin tone", "primary grade". In `edit-episode` it is stage A, step 4, after `chart-match`.

Explicit call:

```
/davinci-editor:natural-skin-grade [scene or color group] [strength 0-1]
```

| Argument | Meaning | Default |
|---|---|---|
| `scene` | scene or Color Group (one scene = one lighting setup) | asks if empty |
| `strength` | share of the skin hue error that gets corrected, 0–1 | `skin_strength` (`0.6`) |

## Before you start

- Clips carry the base template on the remote `claude` version with the labels `CHART`, `CST`, `PRIMARY`, `SKIN`: run [`log-to-rec709`](log-to-rec709.md) first (that's where the one-time DRX template is captured), and [`chart-match`](chart-match.md) before this skill if a chart was shot.
- No `SKIN` label → the template is from stage 1. The skill offers the template upgrade ([`resolve-core`](resolve-core.md#color-node-convention)). If you decline, it corrects only neutrals on `PRIMARY` and reports the skin offset without fixing it.
- The scene's clips: the Color Group named `scene`, or a list you confirm.
- One representative frame per scene: face large, frontal, evenly lit, no motion blur. With several people or a lighting change in the scene, the skill asks which frame to use.

## What the numbers mean

| Term | Meaning |
|---|---|
| hue | the vectorscope angle; the skin tone line is at about 123° for every skin color |
| deadband | skin within ±3° of the line is left alone |
| max rotation | one pass rotates skin by at most 8° |
| strength | the share of the hue offset that is corrected (0.6 = 60 %) |
| saturation cap | skin with a chroma/luma ratio above `skin_max_saturation` is toned down |

Darker and lighter skin differ in **luma and saturation**, not in hue. So the skill corrects hue, caps saturation, and never pushes skin luma toward a "standard" value.

`PRIMARY` gets the neutral balance (from something grey or white in the same light) and affects the whole picture. `SKIN` gets the skin rotation and saturation cap, only inside its qualifier, so walls and clothes don't shift. Exposure is never changed by the script; Claude suggests an equal `PRIMARY` slope only if the face is badly exposed, and only applies it with your yes.

## Settings

| Key | Default | Effect |
|---|---|---|
| `skin_strength` | `0.6` | strength used when `strength` is not given |
| `skin_max_saturation` | `0.35` | chroma/luma ratio above which skin saturation is reduced |

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `stills/<scene>-skin.tif`, `.png` | the measured frame after the CST, before skin correction |
| `stills/<scene>-skin-after.tif` | the same frame with the proposed CDLs, measured again |
| `grades/<scene>-skin.json` | per clip, the CDLs set on `PRIMARY` and `SKIN`; the only record, because Resolve can't read a CDL back |

## Workflow and approval stops

1. Exports the chosen frame in the "after CST, before skin" state on a temporary local version `claude-measure` (chart correction kept, `DEPTH` and `LOOK` off), then restores your version and deletes the temporary one. Your grade is never touched. Deleting `claude-measure` is exempt from the delete prompt.
2. Reads the PNG and picks the sample boxes: 1–3 on cheeks and forehead (lit side; no eyes, lips, beard, hair, highlights or deep shadow) and one on something truly grey or white in the same light. No neutral surface → no neutral box (a colored wall is never used). Not sure where the face is → it **asks you** for the boxes.
3. Analyzes the still with `skin_grade.py`. Warnings about clipped samples or a colored "neutral" mean the boxes are wrong: it fixes them and reruns.
4. Shows the skin hue offset before → predicted, skin luma, saturation ratio, the `PRIMARY` and `SKIN` CDLs, and a plain-language summary ("the face is 9° toward magenta, turning it back 5°; toning the skin down a little").
5. Verifies before touching your grade: repeats the export on a fresh temporary version with the CDLs applied and measures again. More than 2° off the prediction means the qualifier isn't catching the face or another node interferes: it stops and says so.
6. **Approval: before and after.** Both stills side by side (or you compare in the viewer). Nothing is applied to the scene without your yes.
7. On every clip of the scene, on the remote `claude` version, sets the CDLs on `PRIMARY` and `SKIN` (found by label), in batches of up to 50, and records them in `grades/<scene>-skin.json`. A clip whose framing or light clearly differs (another person, window light) gets its own measurement instead of the scene's CDL.
8. Reports per scene: frame used, measured skin offset before → after, CDLs, clips changed, anything skipped.

Any other script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Apply a DRX to a graded clip to add skin nodes: it would wipe the chart correction. The template upgrade is used instead.
- Move skin onto the line at full strength unless you ask.
- Normalize skin luma.
- Change exposure without your yes.
- Measure on a still with `LOOK` or `DEPTH` active.

## Place in the workflow

`project-bootstrap` → `log-to-rec709` → `chart-match` → **`natural-skin-grade`** → `depth-background-blur`

Next: `depth-background-blur`, then your creative `LOOK`.

## Example prompts

**Minimal:**

> Make the skin tone natural for the scene kitchen: the face looks magenta and the wall is a bit green.

**With arguments:**

```
/davinci-editor:natural-skin-grade kitchen 0.4
```

**Overriding a setting:**

> Base grade for the scene desk, strength 0.5 and skin saturation cap 0.3: my face gets red under this lamp.

**Professional brief:**

> Base grade for Color Group `kitchen`, three clips, one presenter, window light from the left. Measure on IMG_4127 around 00:00:12: face large and frontal. The grey wall behind me is a real neutral, use it for the balance. Correct skin part-way only, default strength; my skin is naturally warm and shouldn't end up on the line. Don't touch exposure unless the face is clearly off, and ask me first. Show me before and after side by side before applying to the scene, and report the measured offset, the CDLs and which clips got them.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Fix the colors" | "Natural skin grade for scene kitchen: the face reads magenta and the wall has a green cast; balance on the grey wall, correct skin part-way, show me before and after." |

The strong prompt names the scene, the problem and a true neutral, so the measurement uses the right samples and the correction is aimed at what you actually see.

## What to check afterwards

- Look at 2–3 clips of the scene in the viewer: skin natural, walls and clothes unshifted.
- `grades/<scene>-skin.json` lists every clip that got the CDLs.
- Clips with different framing or light were measured separately, or listed as skipped.
- After a later template upgrade, run this skill again: CDLs can't be carried over.
