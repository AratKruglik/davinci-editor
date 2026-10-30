---
name: marker-edit
description: Edits by the user's own colored markers in DaVinci Resolve 21+ - reads markers on media pool clips, the timeline and timeline items, maps each color to a task (Red cut, Green keep/best take, Yellow doubt, Sand ColorChecker frame, Purple camera/screen/PiP, Fuchsia B-roll insert, Cocoa transition, Lavender SFX, Sky music, Rose audio problem, Blue chapter, Cyan title, Pink zoom, Mint Shorts candidate, Lemon thumbnail frame), builds an action plan for approval, dispatches tasks to the matching skills and records progress in marker customData without ever changing the user's markers.
when_to_use: User put markers on footage or a timeline and wants Claude to act on them, or asks what the markers say. Triggers - "зроби по маркерах", "пройдись по моїх маркерах", "що там у маркерах", "виконай маркери", "монтаж за маркерами", "marker edit".
argument-hint: "[stage A|B|C|D] [timeline name]"
arguments: [stage, timeline]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *catalog.py *)"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Edit by markers

Follow `resolve-core` first. Stage filter: `$stage` (empty = all active colors). Timeline: `$timeline` (default current).

The user marks material while watching; a marker's **color is the task type**, its **name is the content** (title text, chapter name), its **note is a free instruction in Ukrainian**. Read them as a human assistant editor would: no strict syntax, ask when a note is unclear.

## Color map

Configured in `${user_config.marker_colors}` (`Color=task` pairs). Defaults and the skill that does the work:

| Color | Task | Point marker | Marker with duration | Skill | Status |
|---|---|---|---|---|---|
| Red | cut | the phrase / take around it (bounds from transcript) | exactly this range | `text-based-cut` | active |
| Green | keep / best take | protects the phrase around it; among repeats this take wins | protects this range | `text-based-cut` | active |
| Yellow | doubt | Claude proposes options and asks, never decides | same | `text-based-cut` | active |
| Sand | ColorChecker frame | frame to measure | — | `chart-match` | active |
| Purple | camera / screen / PiP switch | until next Purple | this range | `dual-video-sync-pip` | active |
| Fuchsia | insert B-roll (note: what) | Claude picks duration | insert duration | `marker-edit` (§3) | active |
| Cocoa | transition (note: type / MotionVFX name) | — | — | `marker-edit` (§3) + `motionvfx-catalog` | active |
| Blue | chapter start (name = chapter title) | — | — | `chapters-markers` | active |
| Cyan | title on screen (name = text) | default duration | title duration | `fusion-motion-graphics`, `motionvfx-catalog` | active |
| Pink | zoom (note: area, strength) | short zoom | zoom duration | `tutorial-zooms` | active |
| Lavender | SFX (note: which sound) | sound moment | long sound | `sound-design` | active |
| Sky | music start / mood change / end | change point | music range | `sound-design` | active |
| Rose | audio problem (note: what) | Claude finds bounds | this range | `audio-finish`, `voice-isolation` | active |
| Mint | Shorts candidate | Claude picks 30–60 s | exactly this range | `shorts-cutdown` | active |
| Lemon | thumbnail frame | this frame | — | `thumbnail-frames` | active |
| Cream | **Claude's own markers only** (suggestions, problems, questions) | | | | always |

Stages (for `edit-episode`): A — Sand; B — Red, Green, Yellow, Purple, Fuchsia, Cocoa; C — Lavender, Sky, Rose; D — Cyan, Pink, Blue, Mint, Lemon.

## Rules that protect the user's work

1. Never change color, name, note, position or duration of a user marker, and never delete one. The only field Claude writes on a user marker is `customData`, and only when it is empty or already starts with `claude:`.
2. Progress goes to `customData` as `claude:done:<skill>:<YYYY-MM-DD>` (or `claude:skipped:<reason>`). Markers already `claude:done:*` are skipped, so a re-run never does a task twice.
3. Claude's own markers are only Cream, with `customData` starting `claude:`; the user can remove all of them with `DeleteMarkersByColor("Cream")`. Never put Cream markers in places that hide user markers at the same frame — offset by one frame if needed.
4. User markers beat automatic suggestions: Green ranges are never cut; Red ranges are cut even if the transcript analysis would keep them (still shown in the plan).
5. Unclear note → a question, not a guess.

## 1. Read markers on all three levels

With `run_script` (batch per bin / track if large):
- media pool clips in `${user_config.footage_bin}` (and the bins the user names): `clip.GetMarkers()` → `{frame: {color, name, note, duration, customData}}`, frame relative to clip start — used before the cut (stages A/B);
- timeline: `tl.GetMarkers()`, frame relative to `tl.GetStartFrame()` — used after the cut;
- timeline items: `item.GetMarkers()` for video and audio items, frame relative to the item's media (verify on the first marker by comparing with the viewer timecode the user sees).

Normalize each to `{level, owner (clip/timeline/item name + unique id), frame, tc, color, name, note, duration, customData}`. Convert frames to timecode with the `resolve-core` helper so the user can find them.

## 2. Build the plan

Drop markers already done, Cream markers, and colors whose skill is not available yet (list them separately as "чекають свого скіла"). For the rest produce one table, grouped by skill, in time order:

| # | Where (clip/timeline @ TC) | Color | Name / note | What Claude will do | Skill |

Resolve point-marker bounds now when they depend on the transcript (Red/Green: the sentence or take containing the frame; show the words). Flag conflicts: Red inside Green, two Greens on different takes of the same phrase, a Sand marker on a clip that isn't Apple Log.

Ask for approval of the whole table (allow excluding rows by number).

## 3. Dispatch

Hand approved rows to the skills, each with its marker list:
- Red/Green/Yellow → `text-based-cut` as user decisions (Red = forced cut, Green = protected keep / preferred take, Yellow = must ask). Run it once for all of them, not per marker.
- Sand → `chart-match` with the clip and frame of the marker as the chart frame.
- Purple → `dual-video-sync-pip` (name = mode: камера / екран / pip).
- Lavender, Sky → `sound-design` as fixed cues; Rose → `audio-finish` (noise-type notes go to `voice-isolation` first).
- Cyan → `fusion-motion-graphics` (name = text, note = kind or MotionVFX template); Pink → `tutorial-zooms` (note = area, strength); Blue → `chapters-markers` (name = chapter title); Mint → `shorts-cutdown`; Lemon → `thumbnail-frames`. These work on the cut timeline; Blue / Mint / Lemon markers left on media pool clips before the cut are mapped through the timeline dump (`resolve-core/reference.md#timeline-dump`), and a marker whose moment was cut out is reported, not moved.
- Fuchsia and Cocoa are done here, after the rough cut, on the cut timeline (back it up first, `resolve-core` §3):
  - **Fuchsia** (B-roll insert): find the clip from the note in `01_Footage/B-Roll` (file name, or match the description against clip names and, if transcribed, their transcripts); several candidates or none → ask. Append it with `mediaType: 1` on the `B-roll` track at the marker frame (second overlapping insert → `B-roll 2`), duration = marker duration, or 3–5 s for a point marker, ending in a pause of the speech if possible. Video only: the voice continues underneath.
  - **Cocoa** (transition): the cut nearest the marker on A-roll/B-roll/Screen. Transition name from the note, matched in the catalog (`python3 ${CLAUDE_SKILL_DIR}/../motionvfx-catalog/scripts/catalog.py search "<catalog>" --category Transitions <words>`; no catalog → run `motionvfx-catalog`); no name → `Cross Dissolve` (category `simple`). `item.AddTransition({"type": name, "category": "fusion" or "simple", "position": "end", "alignment": "center", "duration": 10–20 frames})` on the outgoing item; `None` back means too little handle: say so, don't trim clips to make room.
- Everything happens on a copy / new timeline per those skills; the original timeline stays untouched.

## 4. Mark done and report

After each skill reports success, write `claude:done:<skill>:<date>` to `customData` of the handled markers (`obj.UpdateMarkerCustomData(frame, value)`; re-read with `GetMarkerCustomData`). Put Cream markers for anything that needs the user's eye (with the reason in the note).

Report: handled per color, skipped (and why), waiting for future skills, questions.
