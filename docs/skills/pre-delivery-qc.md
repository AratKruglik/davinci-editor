# `pre-delivery-qc`: read-only check before the render

[← All skills](README.md)

## What it does

Checks a timeline before rendering and fixes nothing by itself: offline media, black frames and gaps in the picture, one- and two-frame flash frames, voice dropouts, disabled clips and tracks, frame-rate mismatches, timeline settings against the delivery format, empty tracks, unhandled user markers and leftover Claude markers, missing grades, subtitles and chapters, plus the measured loudness and peak of the mix. It reports every problem with its timecode and who should fix it, puts Cream markers on the errors and gives one verdict that `deliver` gates on.

Principle: this skill only looks. Every fix is an editorial decision or needs your eyes, and a QC that "fixes" silently can't be trusted.

## When it triggers

Automatically before any final render or upload, after late edits, when you ask whether everything is ready, or as the gate `deliver` runs first. Ukrainian trigger phrases: «чи все готово?», «перевір перед рендером», «QC», «чи все ок з таймлайном», «знайди чорні кадри», «перевір дірки», «офлайн медіа». In `edit-episode` it is stage D, step 7, run on the episode and on every Short.

Explicit call:

```
/davinci-editor:pre-delivery-qc [timeline] [youtube|shorts]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the timeline to check | the current timeline |
| `target` | `youtube` or `shorts` | `youtube` |

Targets:

| Target | Expected format | Extra checks |
|---|---|---|
| `youtube` | the episode's own settings (reported: UHD 3840×2160 or 1920×1080, fps) | subtitles and chapters |
| `shorts` | `shorts_resolution`, same fps | none |

## Before you start

- The timeline you are about to render. Late edits are fine: that is what the check is for.
- For `youtube`: the subtitles from `subtitles-uk` and the chapters from `chapters-markers`, otherwise they come up as findings.
- Optional: a loudness measurement from `audio-finish` taken after the last audio change; it is reused instead of measuring again.

## Markers it reads

| Markers | Finding |
|---|---|
| your markers of any color whose `customData` is not `claude:done*` or `claude:skipped*` | `open-marker` (warning): not handled yet; the fix is the skill of that color (`marker-edit`) |
| **Cream** markers still on the timeline | `claude-marker` (info): review, then remove |

Claude marks each error that has a frame with a **Cream** marker (name = kind, note = the message, `customData` `claude:qc:<kind>`), one frame later if one of your markers sits there. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## What it checks

Severity: **error** = will be visible or audible in the render; **warn** = probably a mistake, you decide; **info** = cleanup.

| Kind | What | Severity |
|---|---|---|
| `black` | no picture on any enabled non-title track (black under a title is still black) | error |
| `tail` | audio or titles running past the last picture: black at the end | warn |
| `sliver` | an item of 3 frames or less (flash frame) | error |
| `offline` | media not `Online` | error |
| `track-disabled` / `clip-disabled` | a disabled track or clip that won't render | warn |
| `speed` | a speed-changed item | info |
| `fps` | a clip whose frame rate differs from the timeline's: judder or frame blending | warn |
| `audio-dropout` | a 1–2 frame hole between Voice items: click or dropout | warn |
| `empty-track` | an empty track | info |
| `open-marker`, `claude-marker` | see above | warn, info |
| `settings` | timeline size or fps doesn't match the delivery format | error |
| `ungraded` | an A-roll / B-roll / Screen item without the remote `claude` version or your own grade | set by Claude |
| `critic-stale` | graphics, zooms, captions or PiP were placed by a skill, but `frame-critic` hasn't checked them, or checked them before the last edit: run `frame-critic` | warn |
| `look` | stills at 0 %, 25 %, 50 %, 75 % and the last second: a frame still log-flat or wildly off in color; on Fusion titles the skills didn't record (yours, MotionVFX templates): a missing font, text outside the safe area, a PiP covering the title. Also every `error` from `frame-critic` (cut-off text, a covered face, a short hold…), with the owner skill and its suggested change, even when that check predates the last edit | set by Claude / error |
| `subtitles-stale` | (`youtube`) the SRT is missing or older than the last edit | set by Claude |
| `chapters` | (`youtube`) `chapters.json` fails the `chapters-markers` check against the current duration | set by Claude |
| `loudness` | integrated loudness more than ±1 LU off `loudness_target_lufs`, or a peak over `true_peak_db` | error |

Loudness: reused from `audio-finish` if it measured this timeline after the last audio change (Claude says from when). Otherwise measured exactly as `audio-finish` does it: the render format is recorded and restored, only Claude's own audio-only job is added and only that job is deleted. On Resolve 21.1.2+ a mix that is off also gets per-clip loudness of the Voice and Music items (measured without a render) in the finding, so you see which clip to fix.

**Verdict:** `PASS` (no errors), `PASS WITH WARNINGS`, or `FAIL`, with counts.

## Settings

| Key | Default | Effect |
|---|---|---|
| `shorts_resolution` | `1080x1920` | expected frame of a `shorts` timeline |
| `loudness_target_lufs` | `-14` | loudness target of the mix |
| `true_peak_db` | `-1` | peak ceiling of the mix |

Any setting can be overridden in the prompt: "check loudness against -16 LUFS".

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `timeline-<timeline>.json` | dump of the checked timeline |
| `qc-<timeline>.json` | every finding, the `verdict` and the timeline `state` (end frame, item counts) it checked; read by `deliver` |
| `qc-<timeline>.md` | the report shown to you |
| `qc/<n>.png` | stills for the look check (`.tif` on Resolve before 21.1.2) |
| `critic-<timeline>.json` | read only: the `frame-critic` verdict and its open findings |
| `audio/mix-check.wav` | mixdown for the loudness measurement, only when it is measured anew |
| `subtitles/<timeline>.uk.srt`, `chapters.json` | read only, for the `youtube` checks |

## Workflow and approval stops

1. Dumps the timeline and runs the timeline checks against the expected format (`qc.py check`).
2. Checks grades, exports and looks at the stills, reads the `frame-critic` verdict, checks subtitles and chapters (`youtube`), measures or reuses loudness. Each finding goes into the same `qc-<timeline>.json` through `qc.py add`, never by editing the JSON by hand.
3. Writes and shows the report: verdict and counts, then `# | severity | TC | track | problem | suggested fix (who)`. Fixes name their owner: black / flash frame / dropout → trim or extend in the edit (you, or `text-based-cut` again); offline → relink in the Media Pool (you); empty tracks → `track-layout cleanup`; open markers → the skill of that color (`marker-edit`); loudness → `audio-finish`; stale subtitles → `subtitles-uk`; `critic-stale` → `frame-critic`; `look` → the skill the critic named.
4. Puts Cream markers on the errors.
5. **Question: old QC markers.** Cream `claude:qc:*` markers from a previous run are removed only after you agree, named one by one.

`deliver` renders only after a `PASS`, or after you accepted the listed errors by name, and only while `qc.py stale` says the timeline hasn't changed since this check.

## What it never does

It is read-only. It never trims, deletes, relinks or moves anything, and never changes items, tracks, settings or your markers. The only things it writes:

- reports in the work folder (`qc-<timeline>.json`, `qc-<timeline>.md`, the look stills and, when measuring loudness, the mixdown);
- Cream markers on the errors;
- a temporary audio-only render job for loudness, which it deletes again, restoring the render format.

It also never:

- marks the timeline as passed while an error is open;
- drops a finding because it is "probably intended" (it lists it as a warning instead);
- leaves the loudness render job or a changed render format behind.

Any script that deletes or resets something, such as removing the previous run's Cream markers, becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`shorts-cutdown` → `thumbnail-frames` → `track-layout cleanup` → **`pre-delivery-qc`** (episode and every Short) → `deliver`

Errors go back to the skill that owns them; run the check again after the fix.

## Example prompts

**Minimal:**

> Is everything ready for the render?

**With arguments, episode:**

```
/davinci-editor:pre-delivery-qc "Router Setup - final" youtube
```

**With arguments, a Short:**

```
/davinci-editor:pre-delivery-qc "Router Setup - short 1 password" shorts
```

**Overriding a setting:**

> Check the rough cut before the YouTube render, loudness target -16 LUFS and peak ceiling -2 dBFS for this one: it goes to a podcast feed too.

**Professional brief:**

> QC of "Router Setup - final" for YouTube before I render tonight. I made late trims around the speed test, so look hard for black frames, flash frames and clicks in the Voice track there. The B-roll from the phone may be 30 fps, flag it. Audio-finish measured the mix yesterday before I changed the music, so measure loudness again. Check the subtitles are newer than my last edit. Don't fix anything, just list every finding with timecode, track and who fixes it, and mark the errors on the timeline.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Check the video" | "Pre-delivery QC of the final cut for YouTube: I trimmed the ending late, re-measure loudness, list errors with timecodes and owners, change nothing." |

The strong prompt names the timeline and the target and points at the risky part, so the report focuses on what changed instead of re-explaining a clean timeline.

## What to check afterwards

- Read the report top-down: errors first, each with its timecode and owner.
- Jump to the Cream `claude:qc:*` markers and look at each problem in context.
- Warnings are your call: an intended speed ramp or a deliberate disabled clip can stay, but decide it by name.
- After fixing, run the check again: `deliver` refuses a stale QC.
