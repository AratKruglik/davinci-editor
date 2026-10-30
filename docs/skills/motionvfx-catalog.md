# `motionvfx-catalog`: catalog of installed Fusion templates

[← All skills](README.md)

## What it does

Builds and searches a catalog of the Fusion templates installed for DaVinci Resolve: MotionVFX and other packs in `.drfx` bundles or loose `.setting` files. For each template it records the exact name, category (Titles, Transitions, Effects, Generators), vendor, pack and published controls (text fields, colors). Other davinci-editor skills pick titles, transitions and PiP frames from this catalog instead of guessing names.

It only reads the template files. Nothing in Resolve or in your template folders changes.

## How it runs: a forked helper

This skill runs **forked**: as a separate general-purpose agent on the Haiku model, in its own context, not in your conversation. It does the job, then returns a short summary; the full data stays in the catalog file. For you this means:

- the scan output doesn't fill your conversation; you get counts and the best matches;
- other skills call it when they need an exact template name, and work with what it returns;
- search replies list the best matches only; the full data is in the catalog file.

## When it triggers

Automatically when you ask which MotionVFX titles, transitions or effects are installed, when you installed a new pack, or when another skill needs an exact template name (Cocoa transition markers, PiP frames, Cyan titles naming a template). Ukrainian trigger phrases: «які є титри MotionVFX», «онови каталог шаблонів», «знайди перехід», «що в mTutorial».

Explicit call:

```
/davinci-editor:motionvfx-catalog [scan | search words]
```

| Argument | Meaning | Default |
|---|---|---|
| `action` | `scan` builds or rebuilds the catalog; `search <words>` finds templates by words, optionally limited to a category (Titles, Transitions, Effects, Generators), a vendor or a minimum number of text fields | `scan` |

## Before you start

- Templates installed in the standard Fusion folders: `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates` and the same path under `/Library`. Templates elsewhere: name the folder and it is scanned too.
- Resolve doesn't need to be running: the skill reads the files directly.
- Rescan after you install or remove a pack. `search` without a catalog runs `scan` first.

## Settings

| Key | Default | Effect |
|---|---|---|
| `work_dir` | `resolve-work` | folder of the catalog file |

## Files

| File | Contents |
|---|---|
| `<work_dir>/motionvfx-catalog.json` | the catalog; machine-wide, not per project |

## Workflow

1. **`scan`:** reads every `.drfx` (zip) and `.setting` in the template folders and writes the catalog. Returns the total, counts per vendor and category, unreadable files, and 3–5 packs most useful for tutorials (lower thirds, callouts, placeholders and corner screens for PiP, transitions).
2. **`search`:** returns the best 5–10 matches with the exact `name` (what Resolve's insert calls take), category, pack, number of text fields and main controls.

There are no approval stops: the skill changes nothing.

## How other skills use the catalog

| Skill | Uses it for | How it lands in Resolve |
|---|---|---|
| `fusion-motion-graphics` | a Cyan marker whose note names a MotionVFX title | inserted as a Fusion title; the text goes into its text fields |
| `marker-edit` | the transition named in a Cocoa marker | added as a Fusion transition on the outgoing clip |
| `dual-video-sync-pip` | a styled frame or corner screen for PiP | effects can't be attached through the API: you get the list of PiP items and the effect name, and drag it on yourself |

The name passed to Resolve is the `.setting` file name without extension, exactly as in the catalog (spaces, brackets and all).

## What it never does

- Change the `.drfx` or `.setting` files.
- Copy `.drfx` files into the project or the work folder: MotionVFX packs are licensed per user.

## Place in the workflow

Not a stage of its own: a helper for `fusion-motion-graphics` (stage D), `marker-edit` (Cocoa transitions, stage B) and `dual-video-sync-pip` (PiP frames, stage B). Run `scan` once after installing packs; the other skills search it.

## Example prompts

**Minimal:**

> Which MotionVFX titles do I have installed?

**With arguments, scan:**

```
/davinci-editor:motionvfx-catalog scan
```

**With arguments, search:**

```
/davinci-editor:motionvfx-catalog search lower third
```

**Extra template folder:**

> Rescan the templates and also include the folder ~/Templates/Fusion, I keep a pack there.

**Professional brief:**

> I just installed mTutorial. Rescan the catalog, then find lower thirds with two text fields for a name and a role, callouts that point at a spot on screen, and corner screens for PiP. For each give me the exact name, pack, number of text fields and main controls. I'll use the first lower third in my Cyan marker notes.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Find a nice title" | "Search Titles from MotionVFX with 2 text fields: lower thirds for name and role." |

The strong prompt names the category, the vendor and the number of text fields, which are exactly the filters the search takes, so the matches are usable without another round.

## What to check afterwards

- Unreadable files in the scan summary: a broken or partial pack install.
- Copy template names exactly as returned when you write them into Cyan or Cocoa marker notes.
- After installing a new pack, rescan before other skills look for it.
