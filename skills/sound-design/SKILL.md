---
name: sound-design
description: Atmospheric sound design for a cut timeline in DaVinci Resolve Studio 21+ - reads the transcript, timeline structure and the user's Lavender (SFX) and Sky (music) markers, proposes a cue sheet (time, sound, music mood per section) for approval, picks files from the user's indexed SFX and music library with license sources checked for YouTube Content ID, and places them on the SFX, Music and Ambience tracks with base levels and fades.
when_to_use: User wants sound effects, background music, whooshes on titles and transitions, ambience or a music bed for a cut; stage C of edit-episode after voice-isolation; Lavender or Sky markers. Triggers - "саунд-дизайн", "додай музику", "підбери звуки", "звуки на переходи", "фонова музика", "атмосфера", "sound design", "music bed".
argument-hint: "[timeline] [subtle|normal|rich]"
arguments: [timeline, density]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *sound_library.py *)"
  - "Bash(python3 *tc.py *)"
  - "Bash(python3 *show.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Sound design

Follow `resolve-core` first. Timeline: `$timeline` (default current). Density: `$density` (default `normal`).

Music sources already cleared or refused: !`python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/show.py '${user_config.work_dir}/sound-licenses.json' 60 'none yet (no sound-licenses.json)'`

Script: `${CLAUDE_SKILL_DIR}/scripts/sound_library.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/test_sound_library.py`).

Principle: sound supports the speech, never competes with it. A tutorial with a whoosh on every jump cut sounds cheap; a well-chosen bed and a few accents sound expensive.

## 0. Library and licenses

1. Index (first time, after the user adds sounds, or if the index is older than the library):
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/sound_library.py index --sfx "${user_config.sfx_library_dir}" --music "${user_config.music_library_dir}" --out "${user_config.work_dir}/sound-library.json"
   ```
   Empty library settings → ask for the folders and suggest saving them in the plugin config. No library at all → stop: don't download sounds or music without the user's go-ahead.
2. The summary lists `sources` (first folder under each library: vendor/pack) with a `license` file if one was found. Music on YouTube can trigger **Content ID** claims even when it's licensed. Keep `${user_config.work_dir}/sound-licenses.json` (`{source: "ok" | "no" | "ask"}`); for every music source not yet in it, ask the user once whether it's cleared for their monetized channel (show the license file path). Music from `no`/unknown sources is never placed. SFX packs: ask only if the license file says something unusual.

## 1. Read the material

- Transcript: `<work>/transcripts/*.txt` (`uk-transcribe`), mapped to the timeline through the A-roll items, or a fresh look at the timeline's own subtitles if any.
- Structure: timeline length; Blue markers (chapters); items on Titles (title appearances), transitions on A-roll/B-roll/Screen, B-roll and Screen inserts, Cream `cut` markers (jump cuts — not sound moments by themselves).
- The user's markers (timeline and clips, `marker-edit` rules): **Lavender** = SFX, note = which sound; **Sky** = music start / mood change / end, note = mood. They are decisions, not suggestions.

## 2. Cue sheet

Build `<work>/cues.json`: `[{"id", "tc", "frame", "kind": "sfx|music|ambience", "what", "mood", "reason", "source": "marker|claude", "candidates": [paths], "choice", "length_frames"}]`.

Music: one cue per section, sections from Sky markers, else chapters, else intro / body / outro. Mood from what is said (calm explanation, building tension before a reveal, upbeat result, outro). Prefer instrumental tracks without vocals under speech; tempo steady; change at section borders only.

SFX, by density (`subtle` ≈ 1 per 30 s, `normal` ≈ 1 per 15 s, `rich` ≈ 1 per 8 s on average; Lavender markers don't count toward the limit):
- title or callout appearing → soft whoosh / pop, starting 2–4 frames **before** the title;
- transitions between sections → whoosh or riser into the cut;
- reveals, results, "і ось результат" moments → a subtle hit or shimmer;
- UI demos on screen (clicks) → light clicks only if the recording is silent.
Never on: sentences of dense explanation, every jump cut, two sounds within 1 s.

Ambience: only when the picture is outdoor or a B-roll place needs air (room tone under a silent B-roll), on `Ambience`.

Pick 2–3 candidates per cue with `search` (tags are mostly English; translate the mood yourself):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/sound_library.py search "${user_config.work_dir}/sound-library.json" --kind sfx --max-s 2 whoosh soft
python3 ${CLAUDE_SKILL_DIR}/scripts/sound_library.py search "<index>" --kind music --min-s <section seconds> calm piano
```

A music candidate shorter than its section is still allowed (it ends with a fade), but say so; suggest a longer one if there is.

Approval: show one table — `# | TC | kind | what / mood | reason | file (candidate 1) | alternatives` — marker cues first. Accept edits in one round ("12 не треба, для 5 другий варіант"). Nothing is placed before the yes.

## 3. Place

1. Tracks by role: `SFX`, `Music`, and `Ambience` if any cue needs it (`track_index(..., create=True)` for audio is fine: audio track order doesn't affect the mix). Lock `A-roll` and `Voice` for this stage (`track-layout lock sound`) if `edit-episode` hasn't.
2. Import each chosen file once into `02_Sound/SFX` or `02_Sound/Music` (reuse an item whose `File Path` matches); never copy the file.
3. Append with `mediaType: 2`, `trackIndex` of the role, `recordFrame` from the cue, `startFrame` 0 and `endFrame` = the cue length or the file length (append calibration from `resolve-core`). Overlapping cues on one track → put the later one on `SFX 2` / `Music 2` (`track-layout`).
4. Levels (one call per group, then read back): `tl.NormalizeAudioLevel(items, {...})` with the BS.1770 / LUFS mode from `tl.GetNormalizeAudioModes()`:
   - music under speech → `targetLoudness` `${user_config.music_bed_lufs}` (default -30 LUFS);
   - music without speech (intro, outro, pauses > 3 s) → `${user_config.music_solo_lufs}` (default -20 LUFS); split the cue at speech borders into separate items so each gets its level (this is the ducking: Resolve's API has no volume keyframes);
   - SFX → sample-peak mode, `targetLevel` `${user_config.sfx_peak_db}` (default -12 dBFS).
   If no LUFS mode exists in this build, fall back to `item.SetProperties({"AudioVolume": dB})` with a level you estimate and say so.
5. Fades: music items `item.SetFades({"FadeIn": 1 s, "FadeOut": 2 s})` in frames, shorter (8–12 frames) at internal level changes so the steps are smooth; re-read with `GetFades()`.
6. `track-layout recolor`, save.

## 4. Check and report

- Counts per track == approved cues; every item at its cue frame (`GetStart`).
- Mark handled Lavender/Sky markers `claude:done:sound-design:<date>`.
- Ask the user to listen to three spots: the first title whoosh, a music change, the outro. Offer ±3 dB for music and SFX as a whole.
- Report: cues placed / skipped, files and their sources, any music shorter than its section, what `audio-finish` will do next (final loudness, true peak, fine ducking).

## Never

- Place music whose source isn't cleared in `sound-licenses.json`.
- Put SFX or music on Voice or A-roll tracks, or change Voice items.
- Download or generate sounds without asking.
