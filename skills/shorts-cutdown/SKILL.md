---
name: shorts-cutdown
description: Cuts YouTube Shorts / Reels from a finished horizontal episode in DaVinci Resolve Studio 21+ - finds self-contained 30-60 s moments in the transcript (a hook in the first seconds, one idea, a payoff, no "as I said earlier") and the user's Mint markers, proposes them for approval, builds each on its own vertical timeline from the source media (so it stays editable), reframes with Smart Reframe and checks the face on stills, then hands over to animated captions and delivery.
when_to_use: User wants Shorts, Reels, TikToks, vertical clips or a teaser from an episode, or has Mint markers; the Shorts step of edit-episode stage D. Triggers - "зроби шортс", "наріж шортсів", "вертикальні відео", "рілс з цього відео", "знайди моменти для шортс", "shorts", "vertical cutdown".
argument-hint: "[timeline] [count]"
arguments: [timeline, count]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *shorts.py *)"
  - "Bash(python3 *timeline_map.py *)"
  - "Bash(python3 *tc.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Shorts cutdown

Follow `resolve-core` first. Source: `$timeline` (default current; the finished cut, not the selects). Count: `$count` (default: the Mint markers, else up to 3 proposals). Length `${user_config.shorts_min_s}`–`${user_config.shorts_max_s}` s, frame `${user_config.shorts_resolution}`.

Script: `${CLAUDE_SKILL_DIR}/scripts/shorts.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/shorts.py selftest`).

Principle: a Short is a new video, not a piece of the old one. Viewers arrive with no context and decide in about two seconds; a clip that starts with "отже, як я вже казав" loses them, however good the rest is.

## 1. Material

1. Timeline dump and words on the cut (`resolve-core/reference.md#timeline-dump`, `timeline_map.py words`).
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/shorts.py sentences "<work>/words-<timeline>.json" --out "<work>/shorts/sentences.json"`, then read it.
3. **Mint** markers (timeline, `marker-edit` rules, skip `claude:done:*`): marker with duration = exactly that range (still snap to the nearest sentence border inside ±1 s and say so); point marker = build a 30–60 s Short around it; note = hook idea or title.

## 2. Pick the moments

For each candidate (Mint first, then your own if `$count` asks for more), judge from the text:
- **Hook (0–2 s):** the range starts on a claim, a question, a surprising number or a result ("Цей роутер можна налаштувати за 3 хвилини"), not on a greeting or a connective. If the best hook sentence sits later in the range, propose moving it to the front as a cold open (one extra join).
- **One idea, with a payoff:** ends on the answer, the result or a punchline, not mid-explanation.
- **Self-contained:** no references to earlier parts, slides or "this screen above"; no step that only makes sense with a horizontal screen recording (code and UI are unreadable in 9:16; prefer talking-head moments).
- **Tight:** you may drop a digression inside the range (up to 2 extra joins), cutting on sentence borders only.

Propose in one table: `# | source TC range | seconds | hook (first words) | payoff (last words) | joins | why it works | risk`. Put a Cream marker at each proposal's start on the source timeline (`customData` `claude:shorts:<id>`, name = proposed title). Put the whole table, every proposal with its ranges, hook and payoff, into the approval question itself (not a pointer to a later report), and wait for the yes; the user may change ranges.

Write the approved ones to `<work>/shorts/shorts.json` (`[{"id", "title", "ranges": [[start, end], …]}]`, cut-timeline frames from `sentences.json`).

## 3. Plan

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/shorts.py plan "<dump>" "<work>/shorts/shorts.json" --min-s ${user_config.shorts_min_s} --max-s ${user_config.shorts_max_s} \
  --video A-roll --audio Voice --out "<work>/shorts/plan.json"
```

It maps every range back to source clip ranges (with 3 frames of air before and 8 after each range), so the Short is built from the original media, not nested. Add `Screen` to `--video` only if a screen moment was approved on purpose. Any warning (length, gap, speed-changed item) → show it and fix the range before building.

## 4. Build each Short

1. `mp.CreateEmptyTimeline(f"{episode} - short {n} {title}")` (unique name). Before adding clips: `useCustomSettings` `"1"`, `timelineResolutionWidth/Height` from `${user_config.shorts_resolution}`, same frame rate as the source, `timelineInputResMismatchBehavior` `"scaleToCrop"` (fills the frame); re-read with `GetSettings()`.
2. `track-layout setup` on it (A-roll, Voice, Titles; Music only if the user wants music in Shorts).
3. Append calibration (`resolve-core`), then append the plan entries: video to A-roll, audio to Voice (`mediaType` 1 / 2, `recordFrame` = `tl.GetStartFrame() + record`), batches ≤ 50; relink pairs with `SetClipsLinked`. Verify count and total length against the plan.
4. Grades: check `GetCurrentVersion()` on the items and load the remote `claude` version where needed (`resolve-core` §7).
5. **Smart Reframe:** `item.SmartReframe()` on each A-roll item, poll `project.GetSmartReframeStatus()` in separate calls. Then a still from each item, Read it: face inside the frame and not cut at the chin or forehead. 21.1.2+: `tl.ExportFrame(frame - tl.GetStartFrame(), {"outputType": "file", "filePath": "<work>/shorts/<id>-<n>.jpg", "maxDimension": 1280})` at a frame inside the item (`resolve-core` §10): the timeline composite shows the reframe, no playhead move. Not `item.ExportFrame`: whether it shows the reframe is unverified. A bad result → set that item's `Pan` by hand toward the face and say so; never leave the speaker half out of frame.
6. Sound: the source items' clip gain and Dialogue Leveler don't come along. Run `audio-finish` on the Short (YouTube plays Shorts at the same -14 LUFS).
7. `subtitles-uk shorts` for the animated captions. Optional: a 2–3 word title at the top in the first 2 s (`fusion-motion-graphics` `kinetic`) if the hook needs it; ask.
8. Save the project.

The user changes the **end** of a built Short: on 21.1.2+ trim the last A-roll and Voice items, each with its own `SetRightOffset(ro + k, False, False)` (`ro - k` to extend) (`resolve-core/reference.md#resolve-2112-editing-calls`), before captions and titles. A changed start or inner join leaves gaps: re-plan and rebuild that Short.

## 5. Report

Per Short: timeline name, length, joins, hook line, stills to check. Mark Mint markers `claude:done:shorts-cutdown:<date>`. Next: `deliver shorts`.

## Never

- Edit the source timeline beyond Claude's Cream markers, or nest it into the Short.
- Build a Short outside the configured length, or one that opens mid-sentence.
- Publish or upload anything.
