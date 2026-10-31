# `subtitles-uk`: Ukrainian subtitles and animated Shorts captions

[← All skills](README.md)

## What it does

Builds Ukrainian subtitles for a cut timeline from the word-level transcript. It maps every word onto the current cut, proofreads terms and names with you, and writes a YouTube-ready SRT (42 characters, 2 balanced lines, reading speed, no dangling prepositions). On request it places the SRT on a `Subtitles UA` track for review in context. For Shorts it builds animated burned-in captions of 2–4 words with the spoken word highlighted in the brand accent color.

Why from the transcript: Resolve's own auto-captions (`CreateSubtitlesFromAudio`) recognize the audio again and ignore the checked transcript and your fixes. Resolve 21.1.2 lists a Ukrainian option, but it hasn't been verified yet; with `AUTO` they pick a neighbouring language and write nonsense. The word timings from `uk-transcribe` are already Ukrainian and already checked.

## When it triggers

Automatically when you ask for subtitles, captions, an SRT for YouTube, burned-in or animated captions for Shorts/Reels, or subtitles fixed after re-editing. Ukrainian trigger phrases: «зроби субтитри», «субтитри українською», «SRT для ютуба», «анімовані субтитри», «підписи для шортс», «караоке-субтитри». In `edit-episode` it is stage D, step 3, and `shorts-cutdown` runs it in `shorts` mode for every Short.

Explicit call:

```
/davinci-editor:subtitles-uk [timeline] [youtube|shorts]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | timeline to subtitle | the current timeline |
| `mode` | `youtube`: an SRT file for YouTube Studio, optionally on a `Subtitles UA` track; `shorts`: animated captions burned in on the `Titles` track of a vertical Short | `youtube` (`shorts` on a vertical timeline) |

## Before you start

- Transcripts in `<work_dir>/<project>/transcripts/*.json` from `uk-transcribe`. Missing, the skill runs `uk-transcribe` first. If you corrected the transcript in Resolve since it was exported, it is exported again, otherwise your fixes are lost.
- Subtitle the cut you will publish: words are taken from the current timeline, so removed takes never reach the subtitles.
- Two speakers: a `Voice 2` track; both tracks are mapped and merged by time.
- `shorts`: a vertical timeline from `shorts-cutdown`. The caption composition's length is your *Standard generator duration* preference and the API can't trim it; if it is shorter than the Short, you are asked to drag its end to the end of the timeline (or raise the preference so it can be re-inserted) before the build.

## Subtitle rules

**Text pass** (both modes, on a copy of the words, keeping every word's timing):

- Hard fillers from `filler_words` and the `(...)` silence marks are removed; soft fillers stay when they carry meaning.
- Suspected recognition errors (technical terms, product names, English words in Ukrainian speech, numbers such as "сто дев'яносто два" → `192` in an address) come to you in one table. Only fixes you approve are applied.
- On Resolve 21.1.2 Studio, Claude offers to write the term and name fixes back into Resolve's own transcripts too (through `uk-transcribe`), so the next export, chapters and Shorts get them.
- Typography: Ukrainian apostrophe `ʼ` (or `'` if you prefer), «лапки», digits for addresses, versions and prices.
- What was said is never paraphrased or shortened.

**YouTube SRT** (`youtube`):

| Rule | Value |
|---|---|
| Cue break | at a sentence end, a pause over 0.6 s, or a clause comma once the cue is long enough |
| Lines | at most 2 lines of `subtitle_max_chars` characters, balanced |
| Line ends | never on «в, у, і, з, на, що, не…» |
| Duration | at least 1 s, at most 7 s, stretched toward `subtitle_max_cps` characters/s when the next cue allows |
| Gap | at least 2 frames between cues |
| Time 0 | the first frame of the timeline, which is what YouTube expects |

**Shorts captions** (`shorts`): 2–4 words at a time (`shorts_caption_words`) in the brand font, white with a dark outline, the spoken word in the accent color, placed at about 36 % from the bottom so YouTube's buttons and description don't cover it. If this Resolve build's Text+ has no usable Write On inputs for the highlight, the captions are rebuilt without the word highlight (phrase pop only) and you are told why.

## Settings

| Key | Default | Effect |
|---|---|---|
| `filler_words` | `е,ее,еее,ем,…` | hard fillers removed from the subtitle text |
| `subtitle_max_chars` | `42` | longest SRT line |
| `subtitle_max_cps` | `17` | reading speed a cue is stretched toward, characters per second |
| `shorts_caption_words` | `3` | most words shown at once in Shorts captions |
| `brand_font` | `Montserrat` | font of Shorts captions |
| `brand_font_style` | `Bold` | style of that font |
| `brand_accent_color` | `#FFD400` | color of the spoken word in Shorts captions |

Any setting can be overridden in the prompt: "36 characters per line", "2 words per caption".

## Files

Under `<work_dir>/<project>/` (the work folder from `resolve-core`):

| File | Contents |
|---|---|
| `transcripts/*.json` | input from `uk-transcribe` |
| `words-<timeline>.json` | words still in the cut, on timeline time; the text pass works on a copy |
| `subtitles/<timeline>.uk.srt` | the YouTube SRT |
| `shorts/<short>-captions.json` | caption groups of a Short, word-timed |
| `shorts/<short>-captions-spec.json` | the Fusion build spec of those captions |

In Resolve: the SRT is imported into bin `05_Subtitles` and placed on track `Subtitles UA` (only if you want it there).

## Workflow and approval stops

1. Maps the words onto the cut (`timeline_map.py words`) and reports its warnings (speed-changed or disabled items).
2. Removes hard fillers and silence marks from a copy of the words.
3. **Approval: the fixes table.** Suspected recognition errors with proposed fixes; you answer once.
4. `youtube`: writes the SRT with `subtitles.py srt`, reports fast-speech warnings with timecodes, and reads 10–15 cues at the start, middle and end.
5. `youtube`, **question: into Resolve?** If yes: adds the `Subtitles UA` track, imports the SRT into `05_Subtitles` and places it, then checks that the first cue starts on the first spoken word. If the API won't place it, you get the manual route: File → Import → Subtitle, then drag onto `Subtitles UA`.
6. `shorts`: builds the caption groups, inserts one Fusion composition on `Titles` at the Short's first frame (other video tracks temporarily locked), applies the spec, and checks three captions on stills: text inside the frame, highlight on the right word, no caption over the face (moved up or down if needed, and you are told).
7. Saves and reports: cues or captions, fixes applied, fast-speech spots, file paths, what's on the timeline.

The SRT goes to YouTube Studio as Ukrainian subtitles; `deliver` can also export it next to the video. Burn-in on the main video happens only if you ask.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Call `CreateSubtitlesFromAudio` for Ukrainian speech.
- Invent text that isn't in the transcript, or paraphrase what was said.
- Subtitle from `plan.json` or the source clips' timecode instead of the current cut.
- Change Voice or A-roll items.

## Place in the workflow

Stage D: `fusion-motion-graphics` → `tutorial-zooms` → **`subtitles-uk`** → `chapters-markers` → `shorts-cutdown` (each Short: `subtitles-uk shorts`) → `thumbnail-frames` → `pre-delivery-qc` → `deliver`

Next: `deliver` (the SRT as a separate file for the main video; Shorts captions are burned in by being on `Titles`).

## Example prompts

**Minimal:**

> Make Ukrainian subtitles for YouTube.

**With arguments, YouTube SRT:**

```
/davinci-editor:subtitles-uk "Router - rough cut" youtube
```

**With arguments, Shorts captions:**

```
/davinci-editor:subtitles-uk "Short 1 - Wi-Fi password" shorts
```

**Overriding a setting:**

> Subtitles for the current cut, but 37 characters per line: the channel's audience watches mostly on phones.

**Professional brief:**

> Ukrainian SRT for the rough cut "Router - rough cut", from the transcript, not Resolve's captions. Keep "ну" where it changes the tone, drop the hard fillers. Product names: Wi-Fi, TP-Link, Archer; the router address must be digits, 192.168.0.1. Show me the fixes table before writing. Put the SRT on a Subtitles UA track so I can review it in context, and check the first cue lands on the first word. Report the fast-speech spots with timecodes.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Add captions" | "Ukrainian SRT for YouTube from the current cut; names and terms: Wi-Fi, TP-Link; addresses as digits; show me the fixes table first." |

The strong prompt names the mode and gives the terms in advance, so the fixes table is short and the SRT is right on the first pass.

## What to check afterwards

- Read the fixes table carefully: names, terms and numbers are where recognition goes wrong.
- Scrub the `Subtitles UA` track (if placed): the first cue on the first word, nothing from removed takes.
- The fast-speech spots: are the cues readable there?
- Shorts: captions clear of the face and of YouTube's buttons, highlight on the spoken word.
- Re-run the skill after any re-edit: subtitles from an older cut drift.
