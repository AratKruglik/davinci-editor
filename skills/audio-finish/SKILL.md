---
name: audio-finish
description: Final audio pass on a cut timeline in DaVinci Resolve Studio 21+ - fixes the user's Rose-marked audio problems, evens out dialogue with Dialogue Leveler and per-clip loudness normalization, optionally applies the user's Fairlight preset (bus limiter, music ducking), renders an audio-only mixdown, measures integrated loudness (ITU-R BS.1770 / LUFS) and peak, and trims the whole mix to the YouTube target (-14 LUFS) without clipping.
when_to_use: User wants the sound finished, levels evened out, loudness for YouTube, "the voice jumps between quiet and loud", music too loud under speech, or a pre-render audio check; last step of edit-episode stage C; Rose markers about clipping or level. Triggers - "зведи звук", "вирівняй гучність", "нормалізуй під ютуб", "-14 LUFS", "музика заглушує голос", "фінальний звук", "loudness", "audio finish".
argument-hint: "[timeline] [target LUFS]"
arguments: [timeline, target]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *loudness.py *)"
  - "Read"
  - "Bash(python3 *memory.py *)"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Audio finish

Follow `resolve-core` first. Timeline: `$timeline` (default current). Target: `$target` (default `${user_config.loudness_target_lufs}` LUFS integrated), peak ceiling `${user_config.true_peak_db}` dBFS.

Edit memory (`resolve-core` §11): learn at the start, read this skill's rules before the plan, and take a snapshot as the last step of every write.

Script: `${CLAUDE_SKILL_DIR}/scripts/loudness.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/loudness.py selftest`).

Why measure instead of trusting settings: YouTube turns loud videos down to about -14 LUFS and never turns quiet ones up. A mix at -18 just sounds weak next to other videos; a mix at -10 gets turned down and loses punch to its own limiter. Only the rendered mix tells the truth, because Dialogue Leveler, voice isolation and bus processing all change the level after clip gain; 21.1.2's per-item `AnalyzeAudioLevels` is a quick look at single clips, not at the mix.

Order matters: voice isolation (already done by `voice-isolation`) → leveling → normalization → mix trim. Normalizing before isolation would raise the noise that isolation later removes unevenly.

## 0. Before

1. `project.SetCurrentTimeline(tl)`: the Dialogue Leveler properties work on the active timeline only.
2. Roles: `Voice` (+ `Voice 2`), `Music`, `SFX`, `Ambience` via `track_index` from `track-layout`. No Voice track → ask which tracks carry dialogue.
3. Save the project and write `<work>/audio-finish-before.json`: per audio item its track, name, `GetProperties()` audio keys (`AudioVolume`, leveler keys). Everything here is reversible from that file; no timeline copy is needed.
4. **Quick per-item levels (21.1.2, no render;** `resolve-core` §10 gate**).** On every Voice, Music and SFX item `item.AnalyzeAudioLevels("YouTube")` → `{"Integrated", "TruePeak"}` (`-100.0` = nothing measured); add them to the same file and show a short table. It spots, before any render: Voice clips far apart (more than ~3 LU), which step 2 evens out, and items whose true peak is above `${user_config.true_peak_db}`. Whether the number follows clip gain and the Dialogue Leveler is unverified: measure one Voice item again after step 2, and only if it moved trust the quick values as "after". It is per item: never add items up into a mix value. Before 21.1.2 skip this; the mixdown in §4 is the measurement either way.

## 1. Rose markers (audio problems)

Read Rose markers (timeline and clips, `marker-edit` rules), skip `claude:done:*`. Sort by the note:

| Problem in the note | Action here | Otherwise |
|---|---|---|
| noise, hum, hiss, room, echo | track isolation off → clip-level isolation on that item per `voice-isolation`; track isolation already on → don't stack a clip-level one on top: offer +10–15 on the track amount (affects the whole track) and let the user choose | — |
| too quiet / too loud phrase | clip gain on that item (`AudioVolume` ± dB), after step 2 | — |
| clipping, distortion, crackle | lower clip gain doesn't repair it; tell the user it needs Fairlight De-Clipper / re-record; add a Cream marker with the reason | manual |
| plosive "п/б", mouth click, breath | Cream marker + suggest Fairlight De-Esser / De-Hummer / manual cut | manual |

## 2. Dialogue

On Voice items:

```python
item.SetProperties({
    "AudioDialogueLevelerEnabled": True,
    "AudioDialogueLevelerMode": resolve.DIALOGUE_LEVELER_MODE_OPTIMIZE_MODERATE_LEVELS,
    "AudioDialogueLevelerReduceLoudDialogue": True,
    "AudioDialogueLevelerLiftSoftDialogue": True,
    "AudioDialogueLevelerBackgroundReduction": not isolation_on,   # don't double-process with voice isolation
})
```

Re-read with `GetProperties()`. Whispery or very dynamic presenters: `…LIFT_SOFT_WHISPERY_SOURCES` / `…ALLOW_WIDER_DYNAMICS`; ask if unsure.

Then even out clips recorded on different days/distances: `tl.NormalizeAudioLevel(voice_items, {"normalizationMode": <BS.1770 / LUFS mode from tl.GetNormalizeAudioModes(), on 21.1.2 "ITU-R BS.1770-4">, "targetLoudness": target - 2, "setLevelMode": resolve.NORMALIZE_AUDIO_SET_LEVEL_INDEPENDENT})`. Dialogue sits ~2 LU under the target because music and SFX add the rest. No LUFS mode in this build → skip it and rely on step 4.

Music and SFX levels come from `sound-design`; don't renormalize them here. If `sound-design` didn't run, normalize music to `${user_config.music_bed_lufs}` and SFX to `${user_config.sfx_peak_db}` peak the same way.

## 3. Fairlight preset (optional)

`${user_config.fairlight_preset}` set → check it's in `resolve.GetFairlightPresets()`. Whether applying a preset replaces tracks and busses is unverified, so first apply it to a **duplicate** of the timeline and compare track count, names and items before/after. Same structure → apply to the real timeline and delete the duplicate (guard prompt: say it's the test copy). Different → stop, report, keep the real timeline untouched.

Not set → tell the user once what a preset buys and how to make it (Fairlight page): main bus Limiter at -1 dBTP; on Music a Compressor with sidechain from Voice (ratio 3:1, ~6 dB reduction) for smooth ducking; save via Fairlight → Presets → Save. Continue without it.

## 4. Measure and trim

1. Audio-only mixdown of the whole timeline to `<work>/audio/mix-check.wav`. This changes the user's Deliver page and there is no getter for the full render settings: record `project.GetCurrentRenderFormatAndCodec()` first, and afterwards restore that format/codec and set `ExportVideo: True` back, then tell the user the target folder and file name were changed for the check, so their next render isn't silently audio-only or misplaced. Then discover the WAV format/codec with `project.GetRenderFormats()` / `GetRenderCodecs("wav")`, then `SetCurrentRenderFormatAndCodec`, `SetRenderSettings({"SelectAllFrames": True, "ExportVideo": False, "ExportAudio": True, "TargetDir": d, "CustomName": "mix-check", "AudioSampleRate": 48000, "AudioBitDepth": 24})`, `AddRenderJob()`, `StartRendering([job])`; poll `IsRenderingInProgress()` / `GetRenderJobStatus(job)` in separate short calls. Delete only that render job afterwards (`DeleteRenderJob(job)`).
2. ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/loudness.py measure "<work>/audio/mix-check.wav" --target <target> --ceiling ${user_config.true_peak_db}
   ```
3. Within ±1 LU of the target and `needs_limiter` false → done.
4. Otherwise trim the whole mix by `gain_to_target_db`: add it to `AudioVolume` of **every** audio item on Voice, Music, SFX, Ambience (read the current value first; keep within -100…+30). That keeps the balance.
   - `needs_limiter` true and no limiter preset → raise only as far as the peak allows (`ceiling - 0.5 - sample_peak_dbfs`) and report the final loudness under target; a quieter but clean mix beats a clipped one.
5. Render and measure once more. Report both measurements. Never loop more than twice: if it still misses, something non-linear (limiter, leveler) is fighting; explain and stop.

## 5. Report

| Check | Before | After |
|---|---|---|
| integrated loudness, LUFS | | |
| sample peak, dBFS | | |
| voice items leveled / normalized | | |
| per-item outliers (quick check, 21.1.2) | | |
| Rose markers handled / left for the user | | |

Mark solved Rose markers `claude:done:audio-finish:<date>`. Save the project. Ask the user to listen on headphones and on laptop speakers to the loudest and quietest passages. Mention that the delivery render (`deliver`, stage 3) should use the same audio settings.

## Never

- Normalize or level Music/SFX as if they were dialogue, or touch Voice clips' isolation set by `voice-isolation` except for Rose fixes.
- Push the mix into clipping to hit the target.
- Leave render jobs or test timelines behind.
