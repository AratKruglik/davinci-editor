# `voice-isolation`: AI Voice Isolation on dialogue

[← All skills](README.md)

## What it does

Turns on Resolve's AI Voice Isolation for dialogue with a set strength (0–100): on whole audio tracks (the default) or on specific timeline clips. It reads the state back to verify it, and never touches music, SFX or room-tone tracks. Voice isolation is real-time and non-destructive: turning it off restores the original sound.

## When it triggers

Automatically when you want to clean dialogue of noise, hum, room echo or background sounds, or ask for voice isolation / noise removal on the voice; also for Rose markers about noise on the voice. Ukrainian trigger phrases: «прибери шум», «почисти голос», «ізоляція голосу», «шумодав на голос». In `edit-episode` it is stage C, step 1.

Explicit call:

```
/davinci-editor:voice-isolation [track number | selected] [amount 0-100]
```

| Argument | Meaning | Default |
|---|---|---|
| `target` | an audio track number, or `selected` for the clips selected on the timeline | the Voice track, plus Voice 2 if present |
| `amount` | isolation strength, 0–100 | `voice_isolation_amount` (60) |

## Before you start

- A cut timeline with the dialogue on a track named `Voice` (and `Voice 2` for a second speaker). No Voice track: Claude shows the audio tracks (index, name, items) and asks which carry dialogue, or offers to run `track-layout`.
- For clip-level work: select the problem clips on the timeline, or put Rose markers on them.

## Markers it reads

| Color | Task | Effect |
|---|---|---|
| **Rose** | audio problem about noise on the voice | on the Voice track, the clip under the marker gets clip-level isolation; the note says what the problem is |

Rose markers solved by isolation (hum, hiss, room noise) are marked done; clipping and distortion ones are left for `audio-finish`. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## Choosing the strength

| Material | Amount |
|---|---|
| Quiet room, lav or close mic | 30–50 |
| Typical home studio, fan or street noise | 50–70 |
| Loud background, reverberant room | 70–90 |
| 100 | only for rescue; the voice gets thin and "underwater" |

Too much isolation removes breaths and the room, and the cut sounds unnatural. Claude starts moderate and raises it only if you still hear noise.

**Track or clip.** Track level is the default: one switch that survives re-cuts and new clips on the track. Clip level is only for specific problem spots (selected clips or Rose markers). The two are never stacked on the same audio.

## Settings

| Key | Default | Effect |
|---|---|---|
| `voice_isolation_amount` | `60` | strength used when `amount` is not given |

Any setting can be overridden in the prompt: "isolation 40, it's a lav mic".

## Files

It writes no files. The previous state of everything it changes is recorded so it can be restored; progress on Rose markers lives in their `customData`.

## Workflow and approval stops

1. Finds the voice tracks by role (`Voice`, `Voice 2`); asks if there are none.
2. Chooses track or clip level (selected clips or Rose markers on the Voice track mean clip level).
3. Saves the project, records the previous state, enables isolation with the amount and reads the state back.
4. **Listening check:** asks you to listen to 10–20 s of the noisiest part (Resolve is the only place to hear it) and offers ±15 steps.
5. Marks Rose markers solved by isolation `claude:done:voice-isolation:<date>`.
6. Saves the project and reports track or clip → state → amount, from the re-read values.

## What it never does

- Apply isolation to Music, SFX or Ambience: it would eat the music.
- Stack track-level and clip-level isolation on the same audio.
- Mark clipping or distortion Rose markers as solved (they go to `audio-finish`).

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`text-based-cut` → `split-edits` → **`voice-isolation`** → `sound-design` → `audio-finish`

Isolate first, normalize after: heavy isolation before `audio-finish` loudness normalization can raise the noise floor of what's left.

## Example prompts

**Minimal:**

> Clean up the voice on the rough cut, there's an air conditioner humming in the background.

**With arguments:**

```
/davinci-editor:voice-isolation selected 75
```

**Overriding a setting:**

> Voice isolation on the Voice track at 40 instead of the usual 60: it's a lav mic in a quiet room, I only want the faint hiss gone.

**Professional brief:**

> Voice isolation on the cut timeline: Voice and Voice 2 at track level, typical home studio with a fan, so start around 55. The window section has street noise too: if 55 isn't enough there, tell me and offer a higher track amount; don't put clip isolation on top. The Rose marker about clipping in the intro, leave it for audio-finish. Music and SFX tracks stay as they are. Report each track with its amount, read back from Resolve.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Remove the noise" | "Leave the Voice track off and isolate only the Rose-marked clips at about 70: traffic noise through the window, the rest of the recording is clean." |

The strong prompt names the noise, the level (clip, not track) and the strength, so nothing clean gets processed.

## What to check afterwards

- Listen on headphones to the noisiest part: noise gone, but the voice not thin or "underwater"? Ask for ±15 if not.
- Breaths and the room still sound natural at the joins.
- Music and SFX tracks have no isolation on them.
