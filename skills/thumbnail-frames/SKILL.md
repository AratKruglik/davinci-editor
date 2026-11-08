---
name: thumbnail-frames
description: Finds thumbnail candidate frames in a graded, cut timeline in DaVinci Resolve Studio 21+ - the user's Lemon markers plus strong moments from the transcript (result, reveal, emotion), exports a short burst of clean stills around each (titles and subtitles hidden) so a blink or motion blur doesn't cost the moment, ranks them by sharpness and exposure with a script, looks at the best ones for eyes, expression and room for text, has edit-judge rank them blind on content, and writes a thumbnail brief with full-resolution PNGs.
when_to_use: User wants frames for a YouTube thumbnail / cover, the best shot of the face, or has Lemon markers; the thumbnail step of edit-episode stage D. Triggers - "кадри для обкладинки", "знайди кадр для превʼю", "кадр для мініатюри", "thumbnail frames", "обкладинка", "найкращий кадр".
argument-hint: "[timeline] [count]"
arguments: [timeline, count]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *thumbs.py *)"
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

# Thumbnail frames

Follow `resolve-core` first. Timeline: `$timeline` (default current; graded, because the still is taken through the grade). Count: `$count` (default 5 picks).

Script: `${CLAUDE_SKILL_DIR}/scripts/thumbs.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/thumbs.py selftest`).

What makes a frame work at 160 px wide: one readable face, eyes open and looking at the lens or at the subject, a clear emotion (surprise, joy, focus), sharp, well exposed, and empty space on one side for the title text. Everything else is secondary.

## 1. Moments

- **Lemon** markers (timeline and items, `marker-edit` rules, skip `claude:done:*`): the exact frame; note = emotion or idea. Always included.
- From the words on the cut (`timeline_map.py words`): the result or "after" moment ("і ось — працює!"), a reveal, a surprise or laugh, the strongest claim of the hook. Up to 2× `$count` moments in total, spread over the video.
- B-roll or a screen frame only if the user's note asks for it (e.g. the finished product).

## 2. Clean stills

1. Hide what doesn't belong on a thumbnail: disable the `Titles`, `Subtitles UA` and subtitle tracks and the `Effects` track if it holds text (`tl.SetTrackEnable`). Read each track's state first (`GetIsTrackEnabled`) and keep it in the script's result; at the end set each track back to **that recorded value** (not simply `True`: a track the user had disabled stays disabled), even if an export fails.
2. Per moment a burst of 5 frames: offsets −6, −3, 0, +3, +6 (a blink lasts ~4 frames at 25 fps). Resolve 21.1.2+ (`resolve-core` §10): `tl.ExportFrame(frame + offset - tl.GetStartFrame(), {"outputType": "file", "filePath": "<work>/thumbnails/<n>_<offset>.tif", "maxDimension": 1280})`, the whole burst in one call, no playhead move; check every `r["success"]`. Paths are Mac paths (`resolve-core` §8). Older: `tl.SetCurrentTimecode(tc)`, `project.ExportCurrentFrameAsStill("<work>/thumbnails/<n>_<offset>.tif")`, one call per still; check the file exists.
3. Rank: `python3 ${CLAUDE_SKILL_DIR}/scripts/thumbs.py score "<work>/thumbnails" --out "<work>/thumbnails/scores.json"`. It flags soft (motion blur), under/over-exposed and clipped frames; it can't see faces.

## 3. Look

Read the two best-scored stills of every moment (more if they're close). For each, judge: eyes open and sharp, expression readable, mouth not mid-word in an awkward shape, face size (≥ ~⅓ of frame height is best), head not cut, space for text (left or right third), background not busy. Discard frames that fail on eyes or sharpness, whatever their score. Keep the best remaining still of each moment and your own order of them to yourself until the judge has answered.

**Blind ranking** (2 or more moments left; `edit-judge` §1 pick): the judge adds the content criteria (clear topic, readable when small, emotion).
1. Export each kept still again as a neutral PNG, `<work>/thumbnails/blind/cand-NN.png`, numbered in timeline order (never by score), with `maxDimension` 1280 and the tracks hidden and restored as in §2 (older Resolve: `ExportCurrentFrameAsStill` with `.png`). Stills come from the timeline already current, so no switch is needed.
2. Write `<work>/candidates-thumbnails.json`: `[{"id": "<moment>_<offset>", "label": "<moment>", "still": "thumbnails/blind/cand-NN.png"}]`.
3. `edit-judge pick "<work>/candidates-thumbnails.json"` and wait for the reply.

Show the judge's ranking first (and whether first place is a tie), then yours with the technical scores, then ask the user to pick; the user's choice decides. A judge reply without a ranking is shown as that.

For each of the `$count` picks (the user's, or the judge's top `$count` if the user leaves it to you) export a full-resolution PNG for the designer, the same call without `maxDimension` and with `.png` (older Resolve: `ExportCurrentFrameAsStill` with `.png`); on 21.1.2+ also a full-resolution 16-bit `.tif` for retouching, into `<work>/thumbnails/full/` (the burst stills in `thumbnails/` stay the 1280 px ones `thumbs.py` scored). Put a Cream marker at each pick (`customData` `claude:thumbnail`, name = short description).

## 4. Brief

Write `<work>/thumbnail-brief.md`:

| # | TC | file (PNG) | emotion / moment | why it works | text space | crop note |

plus 2–3 title-text ideas per pick (≤ 4 words, from what is said at that moment). Tell the user the folder. If a thumbnail skill such as `youtube-thumbnail-strategist` is installed, offer the brief to it; it's optional.

Mark handled Lemon markers `claude:done:thumbnail-frames:<date>`. Restore the track states and report them restored.

## Never

- Leave titles or subtitle tracks disabled.
- Pick a frame you haven't looked at, or one with closed or half-closed eyes.
- Write stills into the media folders.
