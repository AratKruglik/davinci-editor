# `log-to-rec709`: Apple Log and Apple Log 2 to Rec.709

[← All skills](README.md)

## What it does

Converts iPhone Apple Log and Apple Log 2 footage to Rec.709 with an explicit **Color Space Transform** node from a DRX template. The template goes onto each clip as a **remote** grade version named `claude`, so the conversion follows the clip into every timeline, including the rough cut. It detects per clip whether the footage is really log, HLG / Dolby Vision or plain Rec.709, and never mixes Apple Log with Apple Log 2.

The template it applies is the base node tree that every later color skill builds on (`CHART` → `CST` → `PRIMARY` → `SKIN` → `DEPTH` → `LOOK`).

## When it triggers

Automatically when you ask to convert, normalize or "develop" Apple Log / iPhone log footage, set up the CST node, or prepare footage for grading. Trigger phrases: «Apple Log у Rec.709», «конвертуй лог», «переведи в 709», «зроби нормальну картинку з лог», «CST для айфона», "convert log footage". In `edit-episode` it is stage A, step 2.

Explicit call:

```
/davinci-editor:log-to-rec709 [bin path or timeline name] [gamma 2.4|2.2]
```

| Argument | Meaning | Default |
|---|---|---|
| `scope` | Media Pool bin (`/`-separated from the root) or a timeline name | `footage_bin` (`01_Footage/A-Roll`) |
| `gamma` | output gamma of the Rec.709 transform: 2.4 or 2.2 | `output_gamma` (`Gamma 2.4`) |

Gamma 2.4 is for YouTube / TV mastering on a calibrated monitor; use 2.2 only if you grade for computer screens.

## Before you start

**The base DRX template (one-time).** The Resolve API cannot create nodes, so the skill needs a template you build once per log version: `base-apple-log.drx` and `base-apple-log-2.drx` in `templates_dir`. If the template is missing, the skill walks you through capturing it:

1. On the Color page, on one clip of that log version, build serial nodes and label them (right-click → Node Label):
   - `CHART`: empty;
   - `CST`: Color Space Transform with the settings below;
   - `PRIMARY`: empty;
   - `SKIN`: HSL qualifier on skin hue (Hue only, wide soft edges, Clean Black / White about 5), no correction;
   - `DEPTH`: Resolve FX **AI CineFocus** with a moderate background blur (or Depth Map → key output into a node `DEPTH BLUR` with Lens Blur), then **disable** the node(s) with Ctrl/Cmd+D; `depth-background-blur` turns them on per clip;
   - `LOOK`: empty.
2. Tell Claude you're done. It grabs a still from that clip, exports it as DRX into `templates_dir`, renames it to the exact template name if Resolve added a suffix, and confirms the file exists.

From then on it applies the template by itself. Apple Log and Apple Log 2 always get separate templates. If `templates_dir` is empty, Claude asks for a folder once and suggests setting it. The label convention is explained in [`resolve-core`](resolve-core.md#color-node-convention).

Also:

- The project should be on node-based color science, not Resolve Color Management (`project-bootstrap` sets this).
- If your Resolve build doesn't list Apple Log 2 in the CST, the skill uses Apple's official Apple Log 2 → Rec.709 LUT on the `CST` node instead. You download it from Apple; Claude doesn't download it without your permission.

## What it detects

Per clip, from Resolve's clip properties; if those are inconclusive, by probing the file's color tags.

| Detected | Gamut / transfer | Action |
|---|---|---|
| Apple Log | Rec.2020 / Apple Log (iPhone 15 Pro and newer Pro models) | Apple Log template |
| Apple Log 2 | Apple Wide Gamut / Apple Log 2 (newer Pro iPhones that offer it) | Apple Log 2 template |
| HLG or PQ (Dolby Vision) | not log | stops for these clips and offers an HLG/PQ → Rec.709 transform instead |
| Rec.709 SDR | already Rec.709 | nothing to do |
| unclear | — | asks you (or which iPhone model and capture setting); never guesses between versions |

iPhone HEVC is often not log at all: HDR video is HLG or Dolby Vision. Log is never inferred from the codec. Each row of the table shows its confidence: `metadata`, `file probe` or `user`.

CST settings in the template: Tone Mapping `DaVinci`, Gamut Mapping `Saturation Compression`, Apply Forward OOTF on, Use White Point Adaptation on, output Rec.709 / your gamma.

## Opt-in: Resolve Color Management

Only if you explicitly prefer RCM and don't need chart matching (with RCM the working space is hidden from the node tree, so `chart-match` can't measure the camera signal). Claude first warns that it changes how every clip and title renders project-wide and waits for your yes. It reads the current color settings, switches to DaVinci YRGB Color Managed v2 with a DaVinci Wide Gamut / DaVinci Intermediate timeline and Rec.709 / your gamma output, re-reads every key, and sets each clip's Input Color Space using the exact label you set on one clip in the UI.

## Settings

| Key | Default | Effect |
|---|---|---|
| `footage_bin` | `01_Footage/A-Roll` | bin used when `scope` is not given |
| `output_gamma` | `Gamma 2.4` | output gamma when `gamma` is not given |
| `templates_dir` | empty | where the base templates are looked up and exported |

## Files

| File | Contents |
|---|---|
| `<templates_dir>/base-apple-log.drx`, `base-apple-log-2.drx` | base node trees, one per log version |
| `<work_dir>/<project>/stills/<clip>-709.png` | check stills of 2–3 representative clips (`.tif` on Resolve before 21.1.2) |

## Workflow and approval stops

1. Reads clip properties for every video clip in the scope, probing files where needed.
2. **Approval 1: the format table.** Clip → detected format → confidence. Nothing is applied before your go-ahead.
3. Finds the template for each detected log version; a missing one → the capture steps above, waiting for you.
4. Works on a timeline that contains the clips; if there is none, it creates one from the bin. Your edit is never rearranged.
5. On every video item: adds and loads the remote version `claude`, applies the matching template, and verifies the version is current and the labels include `CST`. Batches of up to 50 clips. A clip that already has a remote `claude` version with a different grade → it asks before overwriting.
6. Optional: groups clips per scene into Color Groups if you shoot several scenes; later skills grade per group.
7. Exports stills of 2–3 representative clips (on Resolve 21.1.2+ straight from the clip, without moving your playhead) and checks for clipped highlights, neon saturation or a magenta / green shift (wrong log version) and crushed blacks. If it can't view the stills, it asks you to look at the viewer.
8. Reports a table clip → format → template → applied ✔/✘ and anything suspicious for your eye.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Mix Apple Log and Apple Log 2 templates or LUTs.
- Overwrite an existing grade or remote version without asking.
- Put a LUT on top of the CST "to be safe": that double-converts.
- Infer log from the codec, or guess between Apple Log versions.
- Switch the project to Resolve Color Management without a warning and your yes.
- Download Apple's LUT without your permission.

## Place in the workflow

`project-bootstrap` → **`log-to-rec709`** → `chart-match` → `natural-skin-grade` → `depth-background-blur`

Next: `chart-match` (on the `CHART` node, before the CST) if a chart was shot, then `natural-skin-grade`. An old template without `SKIN` / `DEPTH` is upgraded before the skin grade ([`resolve-core`](resolve-core.md#color-node-convention)).

## Example prompts

**Minimal:**

> Convert all clips in A-Roll from Apple Log to Rec.709.

**With arguments:**

```
/davinci-editor:log-to-rec709 01_Footage/A-Roll 2.4
```

**Overriding a setting:**

> Convert the timeline `Router Setup - selects` to Rec.709, output Gamma 2.2: this one is graded for computer screens, not TV.

**Professional brief:**

> Convert A-Roll to Rec.709. Two iPhones on this shoot: the 15 Pro shot Apple Log, the newer one may be on Apple Log 2, so detect each clip and keep the two strictly apart. Some B-cam clips might be HLG: list them and leave them untouched. If there's no Apple Log 2 template yet, walk me through capturing it. Group the clips into Color Groups `kitchen` and `desk` by scene. Show me the format table before applying anything, and at the end export stills of 2–3 clips and tell me if anything looks clipped or shifted.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Make the footage look normal" | "Convert A-Roll from Apple Log to Rec.709 Gamma 2.4 via the CST template; detect each clip's format first and show me the table." |

The strong prompt names the source, target and gamma and asks for the detection table, so a clip in the wrong format is caught before anything is applied.

## What to check afterwards

- Look at 2–3 clips per scene in the viewer: no neon colors, no magenta or green cast, highlights and blacks intact.
- HLG / PQ and Rec.709 clips got no log transform.
- On the Color page each converted clip shows the `claude` version and the labeled node tree.
- Apple Log 2 clips use the Apple Log 2 template, never the Apple Log one.
