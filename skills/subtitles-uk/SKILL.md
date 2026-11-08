---
name: subtitles-uk
description: Ukrainian subtitles for a cut timeline in DaVinci Resolve Studio 21+ built from the checked word-level transcript, not Resolve's auto-captions - maps every word onto the cut, proofreads terms and names with the user, writes a YouTube-ready SRT (42 characters, 2 balanced lines, reading speed, no dangling prepositions) and optionally places it on a Subtitles UA track; for Shorts builds animated burned-in captions of 2-4 words with the spoken word highlighted in the brand accent color.
when_to_use: User wants subtitles, captions, an SRT for YouTube, burned-in or animated captions for Shorts/Reels, or subtitles fixed after re-editing; the subtitles step of edit-episode stage D and of shorts-cutdown. Triggers - "зроби субтитри", "субтитри українською", "SRT для ютуба", "анімовані субтитри", "підписи для шортс", "караоке-субтитри", "subtitles", "captions".
argument-hint: "[timeline] [youtube|shorts]"
arguments: [timeline, mode]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *subtitles.py *)"
  - "Bash(python3 *timeline_map.py *)"
  - "Bash(python3 *tc.py *)"
  - "Bash(python3 *placed.py *)"
  - "Bash(python3 *memory.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Ukrainian subtitles

Follow `resolve-core` first. Timeline: `$timeline` (default current). Mode: `$mode` (default `youtube`; `shorts` on a vertical timeline).

Edit memory (`resolve-core` §11): learn at the start, read this skill's rules before the plan, and take a snapshot as the last step of every write.

Script: `${CLAUDE_SKILL_DIR}/scripts/subtitles.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/subtitles.py selftest`).

Why from the transcript: `tl.CreateSubtitlesFromAudio` recognizes the audio again and ignores the checked transcript and its fixes. The 21.1.2 API lists `AUTO_CAPTION_UKRAINIAN`, but it is not verified on a running Resolve; with `AUTO` it picks a neighbouring language and writes nonsense. The word timings from `uk-transcribe` are already Ukrainian and already checked, so subtitles are built from them.

## 1. Words on the cut

1. Transcripts in `<work>/transcripts/*.json` (`uk-transcribe`). Missing → run it first. Corrected in Resolve since the export → export again (`uk-transcribe` §4), otherwise the fixes are lost.
2. Timeline dump and words (`resolve-core/reference.md#timeline-dump`):
   `python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/timeline_map.py words "<dump>" "<work>/transcripts" --track Voice --source-offset <calibration> --out "<work>/words-<timeline>.json"`
   Only words that are still in the cut come out; removed takes never reach the subtitles. Report the script's warnings (speed-changed or disabled items).
3. Two speakers (`Voice 2`): map both tracks and merge by time; mark speaker changes with a leading `— ` in the cue text.

## 2. Text pass

Subtitles are read, so they must be right, but they must also match what is said.
- Remove hard fillers (`${user_config.filler_words}`) and the `(...)` silence marks from a copy of the words file; keep soft fillers when they carry meaning.
- List suspected recognition errors in one table: technical terms, product names, English words in Ukrainian speech, numbers ("сто дев'яносто два" → `192` when it's an address). Ask once; apply the approved fixes to the words copy, keeping each word's timing. Never paraphrase or shorten what was said.
- Term and name fixes also help the next export, chapters and Shorts: offer to write them into the source clips' Resolve transcripts with `uk-transcribe` §6 (21.1.2 Studio, asks first). Subtitle typography (digits, «лапки») stays in the words copy only.
- Typography: Ukrainian apostrophe `ʼ` (or `'` if the user prefers), «лапки», numbers as digits for addresses, versions and prices.

## 3. YouTube SRT (`youtube`)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/subtitles.py srt "<words copy>" --out "<work>/subtitles/<timeline>.uk.srt" \
  --max-chars ${user_config.subtitle_max_chars} --max-cps ${user_config.subtitle_max_cps}
```

Rules it applies: a cue ends at a sentence end, a pause over 0.6 s, or a clause comma once it's long enough; ≤ 2 lines × 42 characters, balanced, never ending a line on «в, у, і, з, на, що, не…»; ≥ 1 s on screen, ≤ 7 s, stretched toward 17 characters/s when the next cue allows; ≥ 2 frames between cues. Time 0 = the first frame of the timeline, which is what YouTube expects. Report the fast-speech warnings with their timecodes; Read 10–15 cues at the start, middle and end.

Deliver: the SRT goes to YouTube Studio as Ukrainian subtitles (tell the user); `deliver` can also export it next to the video. Burn-in on the main video only if the user asks.

Into Resolve (ask; useful to review subtitles in context):
1. Track `Subtitles UA` (`track-layout add`, subtitle track).
2. `mp.ImportMedia([srt_path])` into bin `05_Subtitles` and append it to that track. How the SRT lands (track, time offset) is in the runtime-discovery list: check that the first cue starts on the first spoken word. An offset of exactly the timeline start → write a shifted copy and import that. If the API won't place it, tell the user: File → Import → Subtitle, then drag onto `Subtitles UA`.

## 4. Animated Shorts captions (`shorts`)

On a vertical timeline (from `shorts-cutdown`). Style: 2–4 words in `${user_config.brand_font}` `${user_config.brand_font_style}`, white with a dark outline, the spoken word in `${user_config.brand_accent_color}`, placed at ~36 % from the bottom so YouTube's buttons and description don't cover it.

1. Words for the Short (step 1 on the Short's timeline), text pass (step 2).
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/subtitles.py captions "<words copy>" --out "<work>/shorts/<short>-captions.json" --max-words ${user_config.shorts_caption_words}`
3. One Fusion composition for all captions on the `Titles` track at the Short's first frame (`tl.InsertFusionCompositionIntoTimeline()`, other video tracks temporarily locked as in `fusion-motion-graphics` §3). Its length is the *Standard generator duration* preference and the API can't trim: if the item is shorter than the Short, ask the user to drag its end to the end of the timeline (or raise the preference and re-insert) before building.
4. Spec and build:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/subtitles.py fusion "<captions>" --item-start <item.GetStart()> --comp-start <comp start> --width <w> --height <h> --font … --style … --text … --accent … --out "<work>/shorts/<short>-captions-spec.json"`
   Apply with the Fusion builder (`resolve-core/reference.md#fusion-builds-from-a-spec`), in batches of ~40 tools per call. The highlight uses Text+ **Write On** (`Start`/`End`) on an accent copy of the phrase, so both layers share one layout. First build: check those input ids with `GetInputList()`; if Text+ has no usable Write On inputs in this build, rebuild with `--no-highlight` (phrase pop without the word highlight) and tell the user why.
5. Verify on stills at three captions: text inside the frame, highlight on the right word, no caption over the face (move `spot` up or down if it is, and say so).
6. Record the captions in the ledger `frame-critic` reads: `tl.GetUniqueId()`, the comp's `item.GetUniqueId()` and `item.GetStart()`, then every group of `<short>-captions.json` as one part (`--part` = its index from 0; its `start` / `end` are timeline frames; it is fully on once its pop is over, `pop_frames` from the step 4 output or spec). Drop the item first, so a rebuild with other groups leaves no old parts; one Bash call, chained with `&&`:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/placed.py drop "<work>/placed-<timeline>.json" --item-id <item id> && \
   python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/placed.py add "<work>/placed-<timeline>.json" --timeline-id <tl id> --item-id <item id> --owner subtitles-uk --kind caption --track Titles --part <n> \
     --item-start <item.GetStart()> --start <start> --end <end> --full <start + pop_frames> --hold-end <end> --gone <end> --spec "<work>/shorts/<short>-captions-spec.json" --text="<group text>" && …
   ```

## 5. Finish

Save. Report: cues / captions, fixes applied, fast-speech spots, file paths, what's on the timeline. Next: `deliver` (SRT as a separate file for the main video, captions burned into the Short by being on Titles).

`shorts` mode: then run `frame-critic <timeline> subtitles-uk` on the Short. When `shorts-cutdown` called this skill, skip it: that skill runs the critic once for the whole Short.

## 6. Fix from frame-critic (`shorts`)

`frame-critic` hands over findings whose `fix.skill` is `subtitles-uk`: element id (`subtitles-uk/<item_id>#<n>`), kind, TC, message and `fix.change` (words per caption, a line break, a caption's duration).

1. Change only what `fix.change` names: re-run `subtitles.py captions` with another `--max-words` / `--max-chars`, or edit those groups in `<short>-captions.json` (split a group, move a boundary to a word edge); never change the words themselves. Then `subtitles.py fusion` again.
2. Re-apply on the same comp, never by hand in Resolve: the builder as in §4 step 4, stills (step 5), and re-record every group (step 6: drop, then every part, since the indices may shift).
3. Return the element ids of the changed captions (after a regrouping, every caption of that Short) so the critic re-checks them with `check --changed`. A fix you can't apply stays open: say which and why.

## Never

- Call `CreateSubtitlesFromAudio` for Ukrainian speech, or invent text that isn't in the transcript.
- Subtitle from `plan.json` or the source clips' timecode instead of the current cut.
- Change Voice / A-roll items.
