# `project-bootstrap`: new project, bins and import

[← All skills](README.md)

## What it does

Creates the DaVinci Resolve project for an episode: timeline resolution and frame rate (horizontal or vertical), node-based color science for the grading pipeline, the transcription language, the standard bin structure, and the import of camera footage, screen recordings and external audio into the right bins. Files are referenced in place, never copied, moved or renamed. At the end it creates a selects timeline for grading.

It also tidies an **already open** project into the same bins: it moves clips that are already in the Media Pool instead of importing them again.

Settings that can't change later (frame rate once a timeline exists, resolution of existing timelines) are set before anything is imported. That's why this skill runs first.

## When it triggers

Automatically when you start a new video, episode or shoot, ask for a new Resolve project, the bin structure, the footage imported, or an untidy Media Pool sorted, even if you only say "import the footage" or "make bins". Trigger phrases: «новий проєкт», «створи проєкт», «структура бінів», «створи біни», «імпортуй матеріал», «підготуй проєкт під епізод», «розклади по бінах», «наведи лад у media pool», "new project", "vertical project для Shorts". In `edit-episode` it is stage A, step 1.

Explicit call:

```
/davinci-editor:project-bootstrap [project name] [footage folder] [horizontal|vertical]
```

| Argument | Meaning | Default |
|---|---|---|
| `name` | project name | — |
| `source` | folder with the shoot | asks if empty |
| `format` | `horizontal` or `vertical` | `timeline_format` (`horizontal`) |

## Before you start

- Resolve running. If the open project has unsaved changes, the skill saves it (and says so), because creating a project switches away from it.
- The shoot in one folder: camera takes, screen recordings, recorder audio. Nothing in it is modified.
- Know your frame rate. If the camera clips differ from `timeline_fps`, the skill asks which wins (mixed rates get retimed).

## New project or the open one

| Mode | When | What happens |
|---|---|---|
| **New** | default when you name a new episode or project | creates the project, sets timeline and color settings, builds bins, imports, creates the selects timeline |
| **Open project** | you say "here", "in the current project", "sort into bins" without asking for a new project, or the open project already holds this episode's clips | no new project. If the project already has timelines, frame rate and resolution are **not** changed (that would retime existing edits); mismatches are only reported. Bins are built and clips already in the Media Pool are **moved** into them. Only files not yet in the pool are imported |

Running the skill twice duplicates nothing: existing bins are reused (matched by name under the same parent) and files already imported are skipped. Moving instead of re-importing matters: a re-import makes duplicates that lose markers, transcripts and grades.

## Bin structure

| Bin | What goes there | How it's recognised |
|---|---|---|
| `01_Footage/A-Roll` (= `footage_bin`) | camera takes of the presenter | video from the camera (iPhone: `IMG_*.MOV`, Apple metadata) |
| `01_Footage/B-Roll` | cutaways | a subfolder or names you point out |
| `01_Footage/Screen` | screen recordings | names like `Screen Recording`, `Запис екрана`, `CleanShot`, OBS; computer resolutions (2880×1800, 3024×1964…); no camera metadata |
| `02_Sound/Voice` | external mic / recorder audio | `.wav` / `.m4a` next to the takes |
| `02_Sound/SFX`, `02_Sound/Music` | filled later by `sound-design` | — |
| `03_Assets/Graphics`, `03_Assets/Templates` | logos, images, DRX / DRT | images, `.drx`, `.drt` |
| `04_Render`, `05_Thumbnails`, `Edit` | empty | — |

Timeline settings by format, at `timeline_fps`:

| Format | Resolution | Use for |
|---|---|---|
| `horizontal` | `timeline_resolution` (3840×2160) | YouTube episodes |
| `vertical` | the same, swapped (2160×3840) | vertical-first shoots only; `shorts-cutdown` later makes vertical timelines from a horizontal project anyway |

On a new project, color science is set to node-based `davinciYRGB`: the grading skills need an explicit CST node, not Resolve Color Management.

## Settings

| Key | Default | Effect |
|---|---|---|
| `timeline_format` | `horizontal` | format used when `format` is not given |
| `timeline_resolution` | `3840x2160` | horizontal resolution; vertical swaps it |
| `timeline_fps` | `25` | project frame rate |
| `transcription_language` | `uk` | project transcription language, used later by `uk-transcribe` |
| `footage_bin` | `01_Footage/A-Roll` | the bin that receives the camera takes |

## Files

The skill writes no working files. Media is referenced where it lies: never copied, moved, renamed or written into. In Resolve it creates:

| Object | Contents |
|---|---|
| project `<name>` | timeline and color settings, transcription language |
| bins | the structure above, with the imported or moved clips |
| timeline `<name> - selects` in the `Edit` bin | all A-roll clips, the grading timeline for `log-to-rec709` |

## Workflow and approval stops

1. Saves the open project if it has unsaved changes.
2. Lists the footage folder and sorts every file into a bin; reads the camera clips' frame rate where possible and asks which rate wins if it differs from `timeline_fps`.
3. **Approval: the plan.** Project name, timeline settings, a file → bin table and counts. Nothing is created before your yes.
4. Creates the project (a taken name → asks for another name or whether to open the existing project) and sets resolution, frame rate, color science and transcription language. Every key is read back; one that didn't stick is reported with the value Resolve kept.
5. Builds the bins (reusing existing ones) and imports per bin, then checks the item count per bin against the plan. A file Resolve can't read (for example a variable-frame-rate screen recording) is listed with a suggestion to convert it to constant frame rate; a transcoded copy is imported only if you ask.
6. Proxies: there is no API to generate them. For 4K iPhone HEVC on a laptop it tells you: Media Pool → select `A-Roll` and `Screen` → right-click → **Generate Proxy Media**; Playback → **Use Proxy Media if Available**. Renders always use the originals.
7. Creates the selects timeline in `Edit`, checks its settings match the project, and saves.
8. Reports the read-back settings, bins with item counts, files not imported and why, the proxy steps, and the next step.

In open-project mode no project is created; with timelines present, frame rate and resolution are only compared and mismatches reported; clips already in the Media Pool are moved instead of imported.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Overwrite or open over an existing project with the same name without asking.
- Turn on Resolve Color Management (the grading pipeline needs explicit nodes).
- Write into the footage folder, or copy, move or rename media.
- Re-import clips that are already in the Media Pool.
- Change frame rate or resolution of a project that already has timelines.
- Import a transcoded copy of a file without asking.
- Build the edit timeline: `text-based-cut` creates it with the `track-layout` structure.

## Place in the workflow

**`project-bootstrap`** → `log-to-rec709` → `chart-match` → `natural-skin-grade` → `depth-background-blur`

Next: `log-to-rec709` on the selects timeline.

## Example prompts

**Minimal:**

> New project for the router episode, footage is in `~/Footage/router`.

**With arguments:**

```
/davinci-editor:project-bootstrap Router-Setup-2026-11 ~/Footage/router horizontal
```

**Overriding a setting:**

> New vertical project "Coffee Short" from `~/Footage/coffee`, 30 fps instead of 25: it was shot vertical on the phone.

**Open project:**

> Tidy up this project's media pool, everything is dumped in the root. Sort it into bins.

**Professional brief:**

> Create the project "Router Setup 2026-11" for a tutorial. The shoot is in `~/Footage/router`: iPhone takes (IMG_*.MOV), one screen recording from CleanShot and the lav recorder WAV. 4K horizontal, 25 fps; I think one take was shot at 30 by mistake, flag it and ask me before anything gets retimed. Don't touch the files themselves. Tell me which files didn't import and why, and give me the proxy steps: I edit on a MacBook Air. At the end show the read-back project settings and the item count per bin.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Import the footage" | "New horizontal 25 fps project 'Router Setup 2026-11' from `~/Footage/router`: camera takes to A-Roll, the CleanShot recording to Screen, the WAV to Voice; show me the file → bin plan first." |

The strong prompt names the project, folder, format and frame rate, so the plan you approve already matches the shoot and the irreversible settings are right from the start.

## What to check afterwards

- Project Settings: resolution, frame rate and color science match the report.
- Every bin has the expected number of clips; look at the list of files not imported.
- Generate proxies by hand if playback stutters.
- The selects timeline `<name> - selects` is in the `Edit` bin and holds all A-roll takes.
