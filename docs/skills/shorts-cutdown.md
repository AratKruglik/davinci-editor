# `shorts-cutdown`: vertical Shorts from the finished episode

[← All skills](README.md)

## What it does

Cuts YouTube Shorts / Reels from a finished horizontal episode. It finds self-contained 30–60 s moments in the transcript (a hook in the first seconds, one idea, a payoff, no "as I said earlier") plus your Mint markers, proposes them for approval, then builds each approved Short on its **own vertical timeline** from the source media, so it stays editable. It reframes with Smart Reframe, checks the face on stills, and hands over to animated captions and delivery.

Principle: a Short is a new video, not a piece of the old one. Viewers arrive with no context and decide in about two seconds; a clip that opens with "so, as I said before" loses them, however good the rest is.

## When it triggers

Automatically when you ask for Shorts, Reels, TikToks, vertical clips or a teaser from an episode, or when you have Mint markers. Ukrainian trigger phrases: «зроби шортс», «наріж шортсів», «вертикальні відео», «рілс з цього відео», «знайди моменти для шортс». In `edit-episode` it is stage D, step 5.

Explicit call:

```
/davinci-editor:shorts-cutdown [timeline] [count]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the source timeline: the finished cut, not the selects | the current timeline |
| `count` | how many Shorts to propose | one per Mint marker; with no Mint markers, up to 3 proposals |

When `count` asks for more Shorts than you have Mint markers, Claude adds its own proposals after the Mint ones.

## Before you start

- The finished cut as the source timeline. Claude dumps it and maps the transcript words onto the cut, so the transcripts from `uk-transcribe` must exist.
- Optional: Mint markers on the moments you want as Shorts (below).
- The episode's grade in the remote version `claude`: each Short loads it on its items.

## Markers it reads

| Color | Task | Effect |
|---|---|---|
| **Mint** | `shorts` | a marker with duration is exactly that range (still snapped to the nearest sentence border within ±1 s, and Claude says so); a point marker means "build a 30–60 s Short around it"; the note is the hook idea or the title |

Markers are read from the timeline by the `marker-edit` rules; markers whose `customData` is `claude:done:*` are skipped. After the build, handled Mint markers get `claude:done:shorts-cutdown:<date>`. Claude's own proposal markers are **Cream**, never Mint. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## How moments are chosen

Each candidate (Mint first, then Claude's own) is judged from the text:

| Criterion | What Claude looks for |
|---|---|
| Hook (0–2 s) | the range opens on a claim, a question, a surprising number or a result, not on a greeting or a connective. If the best hook sentence sits later in the range, Claude proposes moving it to the front as a cold open (one extra join) |
| One idea, with a payoff | ends on the answer, the result or a punchline, not mid-explanation |
| Self-contained | no references to earlier parts, slides or "this screen above"; no step that only makes sense on a horizontal screen recording (code and UI are unreadable in 9:16, so talking-head moments are preferred) |
| Tight | a digression inside the range may be dropped (up to 2 extra joins), cutting on sentence borders only |

The proposals come as one table: `# | source TC range | seconds | hook (first words) | payoff (last words) | joins | why it works | risk`.

## How each Short is built

- A new timeline `<episode> - short <n> <title>`, frame size from `shorts_resolution`, same frame rate as the source, mismatched input set to `scaleToCrop` (fills the frame).
- Tracks laid out by `track-layout`: A-roll, Voice, Titles; Music only if you want music in Shorts.
- Built from the **original media**, not by nesting the episode: every range is mapped back to source clip ranges with 3 frames of air before and 8 after. Screen recordings are included only if you approved a screen moment on purpose.
- Grade: the remote `claude` version is loaded where needed.
- **Smart Reframe** on each A-roll item, then a still of each item to check the face is inside the frame and not cut at the chin or forehead. A bad reframe gets its `Pan` set by hand toward the face, and Claude tells you.
- Sound: clip gain and Dialogue Leveler of the source items don't come along, so `audio-finish` runs on the Short (YouTube plays Shorts at the same -14 LUFS).
- Captions: `subtitles-uk shorts` for animated captions. Optionally a 2–3 word title at the top for the first 2 s (`fusion-motion-graphics` `kinetic`) if the hook needs it; Claude asks.

## Settings

| Key | Default | Effect |
|---|---|---|
| `shorts_min_s` | `30` | shortest Short it builds |
| `shorts_max_s` | `60` | longest Short it builds |
| `shorts_resolution` | `1080x1920` | vertical frame of the Short timelines |

Any setting can be overridden in the prompt: "Shorts of 20–45 s this time".

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `timeline-<timeline>.json` | dump of the source timeline |
| `words-<timeline>.json` | transcript words mapped onto the cut |
| `shorts/sentences.json` | sentence list Claude picks ranges from |
| `shorts/shorts.json` | approved Shorts: id, title, ranges in cut-timeline frames |
| `shorts/plan.json` | append plan: every range mapped back to source clips |

## Workflow and approval stops

1. Dumps the source timeline, maps the words onto the cut and splits them into sentences (`shorts.py sentences`).
2. Reads the Mint markers.
3. Picks the moments and puts a Cream marker at each proposal's start on the source timeline (name = proposed title, `customData` `claude:shorts:<id>`).
4. **Approval: the proposals.** The whole table, every proposal with its ranges, hook and payoff, is in the question itself. You may change ranges. Nothing is built before your yes.
5. Writes the approved Shorts and builds the plan (`shorts.py plan`). Any warning (length, gap, speed-changed item) is shown and the range is fixed before building.
6. Builds each Short as above and verifies item count and total length against the plan. **Question: a kinetic title** in the first 2 s, asked only if the hook needs it. Saves the project.
7. Reports per Short: timeline name, length, joins, hook line, stills to check. Marks the Mint markers done.

## What it never does

- Edit the source timeline beyond Claude's Cream markers, or nest it into the Short.
- Build a Short outside the configured length, or one that opens mid-sentence.
- Leave the speaker half out of frame after reframing.
- Publish or upload anything.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`subtitles-uk` → `chapters-markers` → **`shorts-cutdown`** (each Short: `audio-finish`, `subtitles-uk shorts`) → `thumbnail-frames` → `pre-delivery-qc` → `deliver`

Next: `pre-delivery-qc shorts` on every Short, then `deliver shorts`.

## Example prompts

**Minimal:**

> Make Shorts from this episode.

**With arguments:**

```
/davinci-editor:shorts-cutdown "Router Setup - final" 3
```

**From your Mint markers plus Claude's picks:**

> Cut two Shorts from the rough cut: one from my Mint marker, pick the second one yourself.

**Overriding a setting:**

> Find three Shorts in the current timeline, 20 to 45 seconds each: this channel's Shorts audience drops off early.

**Professional brief:**

> Shorts from the timeline "Router Setup - final". I put two Mint markers: the one with duration on the password tip is exactly the range I want, the point marker on the speed test result is a Short around it. Propose one more of your own, talking-head only: the router admin UI is unreadable vertically. Every Short must open on the claim or the result, not on "so" or "as I said". If the best line is at the end of a range, propose it as a cold open. No music in Shorts. Check every reframe on stills and fix the ones where my head is cut. In the proposal table show the hook and the payoff words and the risk of each.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Cut some shorts" | "Two Shorts from the final cut: the Mint marker on the Wi-Fi password tip and your best talking-head moment with a hook in the first two seconds. No screen recordings, no music." |

The strong prompt names the source, the count, what to protect and what to avoid, so the proposal table needs one round, not three.

## What to check afterwards

- Watch the first two seconds of every Short: does it open on the hook, without context from the episode?
- Look at the reframe stills: face inside the frame, not cut at the chin or forehead, especially where Claude set `Pan` by hand.
- Listen to the joins (cold open, dropped digressions) for clipped words.
- The Cream `claude:shorts:*` proposal markers stay on the source timeline until you remove them.
