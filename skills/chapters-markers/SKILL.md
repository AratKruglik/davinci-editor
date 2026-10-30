---
name: chapters-markers
description: YouTube chapters for a cut timeline in DaVinci Resolve Studio 21+ - takes the user's Blue chapter markers (name = chapter title) and, where they are missing, proposes chapter starts from the topics of the transcript, snaps every start to the beginning of a sentence on the cut, checks YouTube's rules (first chapter at 0:00, at least 3, each 10 s or longer) with a script, and writes the description block plus a JSON hand-off for timestamp and SEO tools.
when_to_use: User wants YouTube chapters, timestamps for the description, a table of contents of the video, or has Blue markers to turn into chapters; the chapters step of edit-episode stage D. Triggers - "зроби розділи", "таймкоди для опису", "таймстемпи", "розбий на розділи", "глави для ютуба", "chapters", "timestamps".
argument-hint: "[timeline]"
arguments: [timeline]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *chapters.py *)"
  - "Bash(python3 *timeline_map.py *)"
  - "Bash(python3 *shorts.py sentences *)"
  - "Bash(python3 *tc.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Chapters

Follow `resolve-core` first. Timeline: `$timeline` (default current: the final cut; chapters on a timeline that will still change go stale).

Script: `${CLAUDE_SKILL_DIR}/scripts/chapters.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/chapters.py selftest`).

Why bother with rules: YouTube silently ignores the whole chapter list if one rule is broken (first stamp not 0:00, fewer than 3, a chapter under 10 s). A good list also helps search and retention: titles say what the viewer gets, not "Частина 2".

## 1. Read

1. Timeline dump and words on the cut (`resolve-core/reference.md#timeline-dump`, `timeline_map.py words`), then sentences: `python3 ${CLAUDE_SKILL_DIR}/../shorts-cutdown/scripts/shorts.py sentences "<words>" --out "<work>/chapters-sentences.json"`.
2. **Blue** markers on the timeline (`marker-edit` rules; skip `claude:done:*`): name = the chapter title, exactly as written. A Blue marker without a name → propose a title from what is said right after it. Blue markers on media pool clips from before the cut: map their frame through the dump (the item that shows that source frame); a marker whose moment was cut out → tell the user, don't move it silently.

## 2. Complete the list

- Snap each start to a sentence start: the start of the sentence the marker falls in if the marker is in its first half, otherwise the start of the next sentence (users put a chapter marker just before the new topic begins, often at the tail of the previous sentence). Say which markers moved and by how much; a move over 3 s → ask.
- Missing intro: if the first chapter isn't at 0:00, add `Вступ` at 0 (or the user's own first title).
- Few or no Blue markers: propose chapter starts where the topic changes (a new step, a new question, "тепер перейдемо до…"), about every 1–4 min for a tutorial. These are **proposals**: put a Cream marker at each one (`customData` `claude:chapters`, name = proposed title) and list them separately from the user's.
- Titles: 2–6 words, what the viewer learns or does ("Підключаємо роутер до мережі"), Ukrainian, no numbering, no timestamps, no clickbait.

Show the table `# | TC | title | source (marker / Claude) | length`. Wait for the yes.

## 3. Check and write

`<work>/chapters.json`: `[{"frame": <frames from the timeline start>, "title", "source"}]`, then

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/chapters.py check "<work>/chapters.json" --fps <fps> --duration-frames <end - start> --out "<work>/chapters.txt"
```

Errors → fix with the user (merge a short chapter into its neighbour, add the 0:00 one) and run again. `chapters.txt` is the block for the YouTube description:

```
0:00 Вступ
0:40 Підключаємо роутер до мережі
```

## 4. Hand-off and markers

- Tell the user the path of `chapters.txt` and paste its content in the reply.
- If skills such as `youtube-timestamps` or `youtube-seo-architect` are installed, offer to pass them `chapters.json` and the transcript for the description and tags. They are optional; this skill's output is complete without them.
- Chapter cards on screen: offer `fusion-motion-graphics` (kind `kinetic`, the chapter titles) only if the user wants them.
- Mark handled Blue markers `claude:done:chapters-markers:<date>`. Never add Blue markers yourself or rename the user's.

## Never

- Write a chapter list that fails the check, or reuse a stale `chapters.txt` after the cut changed (re-dump and re-check).
- Change the user's titles beyond trimming spaces; suggest edits instead.
