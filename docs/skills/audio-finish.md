# `audio-finish`: final mix and measured loudness for YouTube

[← All skills](README.md)

## What it does

The final audio pass on a cut timeline. It fixes your Rose-marked audio problems (or tells you which ones need manual work), evens out dialogue with Dialogue Leveler and per-clip loudness normalization, optionally applies your Fairlight preset (bus limiter, music ducking), renders an audio-only mixdown, **measures** its integrated loudness (ITU-R BS.1770 / LUFS) and peak, and trims the whole mix to the YouTube target (-14 LUFS) without clipping.

Why measure instead of trusting settings: YouTube turns loud videos down to about -14 LUFS and never turns quiet ones up. A mix at -18 sounds weak next to other videos; a mix at -10 gets turned down and loses punch. Only the rendered mix tells the truth, because Dialogue Leveler, voice isolation and bus processing all change the level after clip gain.

## When it triggers

Automatically when you want the sound finished, levels evened out, loudness for YouTube, when "the voice jumps between quiet and loud" or the music is too loud under speech, for a pre-render audio check, or for Rose markers about clipping or level. Ukrainian trigger phrases: «зведи звук», «вирівняй гучність», «нормалізуй під ютуб», «-14 LUFS», «музика заглушує голос», «фінальний звук». In `edit-episode` it is the last step of stage C, and every Short gets it in stage D.

Explicit call:

```
/davinci-editor:audio-finish [timeline] [target LUFS]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the timeline to finish | the current timeline |
| `target` | integrated loudness target, LUFS | `loudness_target_lufs` (-14) |

## Before you start

- A cut timeline with tracks by role: `Voice` (+ `Voice 2`), `Music`, `SFX`, `Ambience`. No Voice track: Claude asks which tracks carry dialogue.
- `voice-isolation` and `sound-design` done first. Order matters: isolation → leveling → normalization → mix trim.
- Optional: a Fairlight preset you made once, named in `fairlight_preset`.
- Optional: Rose markers on the problem spots, with a note saying what's wrong.

## Markers it reads

| Color | Task | Effect |
|---|---|---|
| **Rose** | audio problem | handled by the note, see the table below |

Markers already `claude:done:*` are skipped; solved ones are marked `claude:done:audio-finish:<date>`. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

| Problem in the note | What happens |
|---|---|
| noise, hum, hiss, room, echo | track isolation off → clip-level isolation on that item (as `voice-isolation` does it); track isolation already on → no stacking: it offers +10–15 on the track amount (affects the whole track) and you choose |
| too quiet / too loud phrase | clip gain on that item, after the dialogue leveling |
| clipping, distortion, crackle | lowering gain doesn't repair it: you are told it needs Fairlight De-Clipper or a re-record, and a Cream marker with the reason is added |
| plosive, mouth click, breath | Cream marker with a suggestion: Fairlight De-Esser / De-Hummer or a manual cut |

## Dialogue, preset and measurement

- **Dialogue Leveler** on Voice items (moderate mode, reduce loud, lift soft; its background reduction stays off where voice isolation is on, so the voice isn't processed twice). For whispery or very dynamic presenters other modes exist; Claude asks if unsure.
- **Per-clip normalization** of Voice items to 2 LU under the target, to even out clips recorded on different days or distances; music and SFX add the rest. Music and SFX levels come from `sound-design` and are not renormalized here.
- **Fairlight preset:** applied first to a **duplicate** of the timeline; if track count, names and items stay the same, it is applied to the real timeline and the test copy is deleted (a permission prompt names it as the test copy). If the structure changes, it stops and leaves the real timeline untouched. Without a preset, Claude explains once what it buys and how to make one on the Fairlight page (main bus Limiter at -1 dBTP; a Compressor on Music with sidechain from Voice, ratio 3:1, about 6 dB reduction; Fairlight → Presets → Save), then continues without it.
- **Measure and trim:** an audio-only mixdown to `mix-check.wav`, measured with `loudness.py`. Within ±1 LU of the target and no peak problem: done. Otherwise the **whole** mix is trimmed by the same dB on every audio item on Voice, Music, SFX and Ambience, which keeps the balance. If the peaks don't allow the full gain and there is no limiter preset, it raises the mix only as far as the peak ceiling (with 0.5 dB margin) allows and reports a final loudness under the target: a quieter clean mix beats a clipped one. It renders and measures once more, and never loops more than twice.

The script measures sample peak, not oversampled true peak (it can read up to about 0.5 dB low), which is why the extra 0.5 dB margin is kept.

## Settings

| Key | Default | Effect |
|---|---|---|
| `loudness_target_lufs` | `-14` | integrated loudness target when `target` is not given |
| `true_peak_db` | `-1` | peak ceiling of the mix, in dBFS (checked as sample peak, with 0.5 dB margin) |
| `fairlight_preset` | — | your Fairlight preset; empty = continue without one |
| `music_bed_lufs` | `-30` | music level, only if `sound-design` didn't run |
| `sfx_peak_db` | `-12` | SFX peak level, only if `sound-design` didn't run |

Any setting can be overridden in the prompt: "target -16 LUFS, it's a calm lesson".

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `audio-finish-before.json` | per audio item: track, name and audio properties before any change; everything is reversible from it |
| `audio/mix-check.wav` | the audio-only mixdown used for measurement |

## Workflow and approval stops

1. Makes the timeline active, finds the tracks by role, saves the project and writes `audio-finish-before.json`.
2. Handles the Rose markers by their note; on noise with track isolation already on, **you choose** whether to raise the track amount.
3. Dialogue Leveler and per-clip normalization on Voice, read back.
4. Fairlight preset, tested on a duplicate first (or a one-time explanation if none is set).
5. Renders the mixdown. This changes your Deliver page settings: the previous format and codec are recorded and restored, video export is switched back on, the test render job is deleted, and you are told that the target folder and file name were changed for the check.
6. Measures, trims the whole mix if needed, renders and measures once more.
7. **Listening check:** asks you to listen on headphones and on laptop speakers to the loudest and quietest passages.
8. Marks solved Rose markers, saves the project and reports a before / after table: integrated loudness, sample peak, voice items leveled / normalized, Rose markers handled / left for you.

## What it never does

- Normalize or level Music / SFX as if they were dialogue.
- Touch the voice isolation set by `voice-isolation`, except for Rose fixes.
- Push the mix into clipping to hit the target.
- Leave render jobs or test timelines behind.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`voice-isolation` → `sound-design` → **`audio-finish`**

Next: stage D (graphics, Shorts, QC). The delivery render (`deliver`) should use the same audio settings.

## Example prompts

**Minimal:**

> Mix the sound on the rough cut for YouTube, the voice keeps going from quiet to loud.

**With arguments:**

```
/davinci-editor:audio-finish "Router Setup - rough cut 2026-11-02" -14
```

**Overriding a setting:**

> Finish the audio, target -16 LUFS instead of -14 and peak ceiling -2 dBFS: this one also goes to a course platform with stricter peaks.

**Professional brief:**

> Final audio on the current timeline, target -14 LUFS. Voice isolation and sound design are done; keep the music and SFX balance from sound-design. My Rose markers: the hum in the window section, the too-quiet phrase after the demo, and the clipping in the intro. For the clipping just leave me a Cream marker, I'll fix it in Fairlight. My preset "YT Bus Limiter" is set in the config: test it on a copy first. Report loudness and peak before and after, and which Rose markers you couldn't fix.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Make it louder" | "Finish the audio to -14 LUFS without clipping; the voice jumps between takes, and two too-quiet phrases have Rose markers. Report before / after loudness and peak." |

The strong prompt states the target, the real problems and the evidence you want, instead of a gain change that would clip.

## What to check afterwards

- Listen on headphones and laptop speakers to the loudest and quietest passages.
- The report's final loudness: if it is under the target, the peaks blocked more gain; a limiter preset would let it go further.
- **The Deliver page:** the target folder and file name were changed for the check render. Set them back before your next render.
- Step through the Cream markers left for manual fixes (clipping, plosives, clicks).
