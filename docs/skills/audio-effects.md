# `audio-effects`: live music, room for SFX, pan sweeps, vocals out of the song

[← All skills](README.md)

## What it does

Five sound design treatments on timeline clips:

| Effect | Result | Claude does | You do |
|---|---|---|---|
| `live` | a song sounds like it plays inside the scene (bar, party, concert) | pastes EQ + Reverb from your `LIVE` reference clip (no reference, Resolve 21.1.2: adds Reverb + Fairlight EQ with default settings) | — (with default settings: the plugin values) |
| `room` | downloaded SFX stop sounding studio-clean and blend into the place | pastes a light Reverb from your `ROOM` reference clip (no reference, 21.1.2: adds Reverb with default settings) | — (with default settings: the plugin values) |
| `pan` | sound moves left → right with a subject crossing the frame | sets the start pan | two pan keyframes (exact steps given) |
| `no-vocals` | the song's vocals (and drums) stop fighting the speaker | checks whether this Resolve build exposes Music Remixer to scripts | Music Remixer in the Inspector (exact steps given) |
| `expander` | background noise between phrases goes down | sends you to `voice-isolation` first | Expander on the track's Dynamics (exact steps given) |

Since Resolve 21.1.2 a script can add and remove audio plugins (Reverb, Fairlight EQ, De-Esser…), but only with their default settings: there is still no way to set plugin values, the clip EQ, Music Remixer or Dynamics, and no pan keyframes. So EQ and effects are copied from reference clips you build once (Edit page **Paste Attributes**, done by script); without a reference, on 21.1.2, Claude adds the plugins with defaults and you set the values on the first clip. The rest ends with step-by-step instructions. Claude always says which part it did and which part is yours.

## When it triggers

Automatically when you want music to sound live in the room, SFX to blend into the scene, sound to follow a subject left-right, the vocals out of a song under speech, or an Expander for noise. Ukrainian trigger phrases: «звук як наживо», «ніби грає в залі», «реверб на звуки», «звук рухається за людиною», «прибери вокал з музики», «експандер».

Explicit call:

```
/davinci-editor:audio-effects [live|room|pan|no-vocals|expander] [selected | track name]
```

| Argument | Meaning | Default |
|---|---|---|
| `effect` | one of the five effects | picked from your request; asked if two fit |
| `target` | `selected` or a track name | the audio clips selected on the timeline |

## Before you start: reference clips (once)

Make a timeline named **`Audio FX Templates`** with any short audio clip on each of these tracks, and build the effect on the clip in the Edit page Inspector → Audio:

| Track | Build |
|---|---|
| `LIVE` | Equalizer on: Band 4 on, Band 3 off, shape a band-pass that cuts the lows and the top; Effects → Fairlight FX → Reverb: Room Size max, Distance max, Reverb Time min |
| `ROOM` | Effects → Fairlight FX → Reverb, preset `Vocal Wide`, then less: Distance down, mix toward dry |

Without them `live` and `room` show you this table and offer a choice: build the reference first, or (Resolve 21.1.2) add the plugins with default settings now and set the values by hand on the first clip. Before 21.1.2 they stop. `pan`, `no-vocals` and `expander` don't need them.

## Settings

None of its own. `no-vocals` mentions `music_bed_lufs` when the real problem is just a loud song.

## Files

It writes no files.

## Workflow and approval stops

1. Reads the target clips and their tracks: `live` goes on Music, `room` on SFX / Ambience, `expander` on the dialogue track. Anything else is asked about.
2. **Plan approval:** one table of clip → effect → what the script sets → what you set by hand.
3. Saves the project. Before pasting effects it duplicates the timeline as a backup: plugins can be removed by script on 21.1.2, but a pasted clip EQ can't. When it adds plugins with default settings, it records what was there and removes only what it added if you want it undone (a permission prompt). For pan it records the previous value.
4. `live` / `room`: pastes onto (or, with defaults, adds the plugins to) **one** clip, asks you to check its Inspector and listen, lets you tweak that clip, then pastes it onto the rest.
5. `pan`: sets the start side, asks where you hear it (the sign of left is checked on the first clip), then gives the keyframe steps.
6. **Listening check** on every changed clip; report of what was set (read back from Resolve) and what's left for you.

## What it never does

- Paste volume, markers or any video or clip attribute along with the effects.
- Paste onto all clips before you confirmed the first one, or paste twice onto the same clip.
- Fake a pan sweep by cutting the clip into steps.
- Put reverb or EQ on the dialogue.
- Remove plugins you added yourself: only the ones it added.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`voice-isolation` → `sound-design` → **`audio-effects`** → `audio-finish`

Reverb and EQ change the loudness, so `audio-finish` measures after them. Crowd sounds for a live scene come from your library through `sound-design`.

## Example prompts

**Minimal:**

> In the bar scene the song sounds like it's on headphones. Make it play live in the bar.

**With arguments:**

```
/davinci-editor:audio-effects room SFX
```

**Pan:**

> The car drives from left to right between 01:00:12:05 and 01:00:15:20, make the engine sound follow it.

**Professional brief:**

> Music under the interview has vocals that fight with my voice. Check whether you can turn on Music Remixer by script; if not, give me the steps to mute Voice, and Drums too if it's still busy. Don't change the music level, audio-finish does that later.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Make the sounds better" | "The door slam and footsteps on SFX in the hallway scene sound too clean: give them a little room, mostly dry." |

The strong prompt names the clips, the effect and how much, so nothing else gets reverb.

## What to check afterwards

- The pasted clip's Inspector shows Equalizer / Effects like the reference.
- The live song still sits under the voice: if not, `audio-finish` evens it out.
- Pan: on headphones the sound starts where the subject enters and ends on the other side.
