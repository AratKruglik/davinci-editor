---
name: audio-effects
description: Five sound design treatments on timeline clips in DaVinci Resolve Studio 21+ - "live" music played inside the scene (EQ + Reverb), realistic room for too-clean SFX (light Reverb), a pan sweep that follows a subject across the frame, Music Remixer to mute the vocals (and drums) of a song under speech, and an Expander on the dialogue track for background noise. EQ and effects are pasted from the user's reference clips with CopyAttributes (21.1.2 without a reference - plugins added with default settings, values by hand); what the API can't set (pan keyframes, Remixer, track Dynamics) is set as far as possible and finished with exact manual steps.
when_to_use: User wants music to sound like it plays live in the room / at a concert, sound effects to blend into the scene instead of sounding studio-clean, sound that moves left-right with the subject, the song's vocals out of the way of the speaker, or an Expander/gate for noise. Triggers - "звук як наживо", "ніби грає в залі", "музика з концерту", "реверб на звуки", "щоб звук не був стерильним", "звук рухається за людиною", "панорама звуку", "прибери вокал з музики", "music remixer", "експандер", "live audio effect", "pan audio".
argument-hint: "[live|room|pan|no-vocals|expander] [selected | track name]"
arguments: [effect, target]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *memory.py *)"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Audio effects

Follow `resolve-core` first. Effect: `$effect` (none given → pick from the request; ask if two fit). Target: `$target` (default: `tl.GetSelectedClips()` audio items; none selected → ask which clips).

Edit memory (`resolve-core` §11): learn at the start, read this skill's rules before the plan, and take a snapshot as the last step of every write.

## What the API can and can't do

| Effect | By script | By hand in Resolve |
|---|---|---|
| `live` — song plays inside the scene | EQ + Reverb pasted from the `LIVE` reference clip; no reference on 21.1.2 → Reverb + Fairlight EQ added with default settings | defaults route: the plugin values |
| `room` — SFX blend into the place | Reverb pasted from the `ROOM` reference clip; no reference on 21.1.2 → Reverb added with default settings | defaults route: the plugin values |
| `pan` — sound follows the subject | start pan `AudioPan` | the keyframes |
| `no-vocals` — song stops fighting the voice | only if the build exposes a Remixer property (probe below) | Music Remixer |
| `expander` — background noise on dialogue | — (track Dynamics has no API) | Expander on the track |

21.1.2 can add and remove audio plugins (`resolve-core` §10: `AddEffect("audio", id)`, `GetEffects("audio")`, `DeleteEffects`), but only with default settings: there is no parameter API for plugins, no setter for the clip Equalizer, Music Remixer or Dynamics, and no volume/pan keyframes. Parameters reach a clip only by pasting from a reference clip or by hand. Say up front which part you do and which the user does; never claim a manual step as done.

## Reference clips (built once by the user)

`live` and `room` copy the clip EQ and audio effects from a reference timeline, the same idea as the DRX color template. Timeline `Audio FX Templates`, any short audio clip on each track, tracks named by preset:

| Track | Build it in the Edit page Inspector → Audio |
|---|---|
| `LIVE` | Equalizer on: Band 4 on, Band 3 off, shape a band-pass that cuts the lows and the top (small-speaker sound); Effects → Fairlight FX → Reverb: Room Size max, Distance max, Reverb Time min |
| `ROOM` | Effects → Fairlight FX → Reverb, preset `Vocal Wide`, then tighten it: Distance down, Dry/Wet toward dry, so only a little room is added |

Missing timeline or track → show this table and offer two routes: build the reference first (best: tuned once, reused), or, on 21.1.2 (`resolve-core` §10 gate), add the plugins with default settings now and set the values from this table by hand on the first clip (see *Defaults route*). Before 21.1.2 only the first route exists: stop for that effect. Don't improvise values in a script (there is no setter for them). Find the source item by track name in the reference timeline, never by index.

## Steps

1. **Read.** Project, timeline, target items (name, track, start TC, current `GetProperties()` `AudioPan`, `AudioVolume`). Effects on dialogue (`Voice`) are allowed only for `expander`; `live` goes on `Music`, `room` on `SFX`/`Ambience` items (tracks by role, `track-layout`). A target on another role → say so and ask.
2. **Plan, then yes.** One table: `# | effect | clip | track | by script | by hand`. Nothing changes before the yes.
3. **Protect.** Save the project. `live`/`room` by paste → `tl.DuplicateTimeline(...)` backup first (resolve-core §3): plugins could be removed with `DeleteEffects`, but the pasted clip Equalizer has no API to undo it. Defaults route → record each target's `len(item.GetEffects("audio"))`; undo is `DeleteEffects` of the added ones (guarded), no backup needed. `pan`/`no-vocals` are property changes: record the previous values instead.
4. **Apply** per effect below.
5. **Listen.** Ask the user to play each changed clip; offer the next step from the effect's notes.
6. Save. Report per clip: what the script set (re-read values), what the user still has to do by hand.

### live / room

```python
ref_tl = next((t for t in (project.GetTimelineByIndex(n) for n in range(1, project.GetTimelineCount() + 1))
               if t.GetName() == "Audio FX Templates"), None)
i = next((i for i in range(1, ref_tl.GetTrackCount("audio") + 1) if ref_tl.GetTrackName("audio", i) == PRESET), None) if ref_tl else None
src = (ref_tl.GetItemListInTrack("audio", i) or [None])[0] if i else None
ok = src.CopyAttributes([target], {"audioEqualizer": True, "audioPlugins": True}) if src else None
```

`src` is `None` → the two routes under *Reference clips* (reference first, or the *Defaults route* on 21.1.2). `ok` is `False`, or the user sees nothing new in the Inspector (pasting from another timeline is unverified) → by hand: select the reference clip, Edit → Copy; select the target, Edit → Paste Attributes; under Audio Attributes tick only Equalizer and Plugins, leave Volume off. The batch afterwards copies from the first target, on the same timeline.

- Only `audioEqualizer` + `audioPlugins`. Never `allAudioAttributes` (it carries `audioVolume` and would undo `sound-design`/`audio-finish` levels) and never clip attributes (markers are the user's instructions).
- No getter exists for EQ or plugin values, so the return value proves nothing: paste onto **one** target first, ask the user to check its Inspector (Equalizer / Effects present, values as in the reference) and listen. Tweaks ("суші" = less wet, "більше залу" = more distance) the user makes on that first clip; then that clip becomes the source for the rest, pasted in one call. Never paste twice onto the same clip: whether a second paste replaces or stacks the Reverb is unverified.
- On 21.1.2, also compare `len(target.GetEffects("audio"))` before and after the paste: one more plugin is a sign the Reverb landed (its values still only show in the Inspector). Whether pasted plugins appear there is unverified, so no change is not proof of failure: the Inspector check decides.
- `live`: also offer crowd/applause from the library via `sound-design` (a cue under the song); don't place it here.

### Defaults route (21.1.2, no reference clip)

```python
ids = {e["name"]: e["id"] for e in resolve.GetEffectsList("audio")}   # e.g. "Audio FX/Fairlight FX/Reverb"
fx = target.AddEffect("audio", ids["Reverb"])                          # live: also ids["Fairlight EQ"]
n = len(target.GetEffects("audio"))                                      # re-read: one more than recorded in step 3
```

The name isn't in `ids` → show the user the audio effect names and ask. One target first; the user opens Inspector → Effects on it and sets the values from the reference table (`live`: in the Fairlight EQ cut the lows and the top; Reverb Room Size max, Distance max, Reverb Time min; `room`: Reverb `Vocal Wide`, Distance down, toward dry) and listens. Then that clip is the source for the rest: paste as above (`audioPlugins` only, the clip Equalizer was not used). Undo: `target.DeleteEffects([fx])` (guard prompt: say it removes only the plugin you added).

### pan

1. Direction (`L→R`, `R→L`) from the user; not given → ask. Don't guess from the picture.
2. `item.SetProperties({"AudioPanEnabled": True, "AudioPan": start})`, start = the side the subject enters from (`-100…100`, which sign is left is unverified: set one clip, ask the user where they hear it, flip if wrong). Re-read `GetProperties()["AudioPan"]`.
3. Manual keyframes (no API): playhead on the frame the subject enters → Inspector → Audio → Pan → keyframe diamond; playhead where the subject reaches the other side → set pan to the other side (a second keyframe is added). Give both timecodes if the user named the moments.
Never fake the sweep by blading the clip into stepped pan segments: that is a structural edit and the steps are audible.

### no-vocals

1. Probe a music item once: `{k: v for k, v in item.GetProperties().items() if "Remix" in k or "Stem" in k}` and `search_scripting_api("Remix|Stem")`. A key exists → set it, re-read, and tell the user its name and values in the report (don't write it into plugin files).
2. Otherwise (21.1.x) by hand: select the music clip → Inspector → Audio → Music Remixer on → Voice muted (slider to 0); still busy under speech → Drums muted too. Studio only; it analyses the clip the first time, wait for it.
3. Compare with the alternative first if the song is just too loud: `audio-finish` music level (`${user_config.music_bed_lufs}`). Instrumental tracks need neither; `sound-design` prefers them.

### expander

Noise on dialogue is `voice-isolation`'s job: AI isolation cleans more with fewer artifacts. Offer the Expander only when the user asks for it or isolation sounds "underwater". By hand, Fairlight page: double-click the Dynamics area of the dialogue track's mixer strip → Expander on → Range max → Ratio about half to two-thirds → play the noisiest part and raise Threshold until the line sits just left of most of the speech points on the Dynamics graph. Then listen to word endings: if they get chopped, lower the threshold. Don't stack it with heavy voice isolation on the same track.

## Order

`voice-isolation` → `sound-design` → **`audio-effects`** → `audio-finish`. Reverb and EQ change loudness, so `audio-finish` measures after them.

## Never

- Paste `audioVolume`, markers or any non-audio attribute.
- Paste onto many clips before the user confirmed the first one.
- Treat a `True` from `CopyAttributes` or `SetProperties`, or an `Effect` from `AddEffect`, as proof; re-read what has a getter, ask the user for the rest.
- Remove plugins the user added themselves: `DeleteEffects` only on the effects this skill added.
