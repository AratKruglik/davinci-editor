---
name: fusion-motion-graphics
description: Builds on-screen graphics in DaVinci Resolve Studio 21+ with Fusion - lower thirds (name plates), callouts pointing at a spot on screen, kinetic key phrases, number counters and chapter cards - from the user's Cyan markers (name = text) and Blue chapter markers, in the brand style from the plugin config (font, text, accent and plate colors), with eased timing and reading-time holds computed by a script, placed on the Titles track and checked on an exported still. Uses an installed MotionVFX title instead when the marker names one.
when_to_use: User wants titles, name plates, lower thirds, callouts, captions for key ideas, animated numbers or chapter cards on a cut timeline, or has Cyan markers; the graphics step of edit-episode stage D. Triggers - "додай титри", "плашка з іменем", "лоуер терд", "виноска", "покажи цифру анімовано", "кінетична типографіка", "заставка розділу", "анімація тексту", "анімований текст", "motion graphics", "lower third", "text animation", "text scramble", "pop-in".
argument-hint: "[timeline] [markers|<kind> <text>]"
arguments: [timeline, request]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *motion.py *)"
  - "Bash(python3 *catalog.py *)"
  - "Bash(python3 *tc.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Fusion motion graphics

Follow `resolve-core` first. Timeline: `$timeline` (default current). Request: `$request` (default: the Cyan and Blue markers).

Brand (plugin config): font `${user_config.brand_font}` `${user_config.brand_font_style}`, text `${user_config.brand_text_color}`, accent `${user_config.brand_accent_color}`, plate `${user_config.brand_plate_color}` at `${user_config.brand_plate_opacity}`, animation `${user_config.brand_text_anim}`.

Script: `${CLAUDE_SKILL_DIR}/scripts/motion.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/motion.py selftest`).

Principle: graphics serve the viewer's attention, not decoration. A tutorial needs few graphics, each readable at a glance, all in one style; ten different animations look amateur even when each is pretty.

## 1. What to build

Sources, in this order:
- **Cyan** markers (timeline and timeline items, `marker-edit` rules; skip `claude:done:*`): name = the text, exactly as the user wrote it; note = kind or a MotionVFX template name, optionally followed by an animation from §4 (`kinetic scramble`). Match animation names first: a note that is only an animation (`pop`) sets the animation and leaves the kind to the default rule below, never a MotionVFX search; marker duration = how long it stays (point marker: reading time).
- **Blue** markers = chapter starts → a chapter card (kind `kinetic`, the chapter name) only if the user wants cards; ask once per episode.
- The request in `$request` (e.g. `lower-third Олексій Круглик / автор каналу`).
- Proposals from the transcript (`<work>/words-<timeline>.json`, see `resolve-core` §4): the speaker's name on first appearance, a number worth a counter ("на 40 відсотків"), a term defined on screen. These are **suggestions** only: show them, place nothing unasked.

Kinds: `lower-third` (name / role, lower left), `callout` (short label + accent dot at a point on screen), `kinetic` (a key phrase, centered low), `counter` (number counting up, accent color). The note decides; no note → `lower-third` for names, `callout` when the note names a spot ("кнопка Save", "праворуч угорі"), `kinetic` otherwise.

Text: keep the user's wording. Fix only obvious typography: Ukrainian apostrophe `ʼ`, quotes «», dash —, no full stop at the end of a title. A typo you suspect → ask, don't fix silently.

Show the plan before building: `# | TC | kind | anim | text | duration | route (Fusion / MotionVFX name) | track`. Wait for the yes.

## 2. Route

- **MotionVFX / installed template** when the note names one: look it up with `python3 ${CLAUDE_SKILL_DIR}/../motionvfx-catalog/scripts/catalog.py search "${user_config.work_dir}/motionvfx-catalog.json" --category Titles <words>` (no catalog → run `motionvfx-catalog`). Backup as in §3 step 1, then insert with `item = tl.InsertFusionTitleIntoTimeline(name)` by the route and checks of §3 step 4 (it *inserts with ripple* like the composition, `resolve-core` §10). Fill its `StyledText` inputs (`text_inputs` from the catalog says how many) through `item.GetFusionCompByIndex(1)`.
- **Built here** otherwise: brand-styled Fusion composition from a spec.

## 3. Build (Fusion route)

1. Backup the timeline (`resolve-core` §3). Lock `A-roll`, `B-roll`, `Voice` for the stage (`track-layout lock graphics`).
2. Still for placement: `tl.ExportFrame(marker_frame - tl.GetStartFrame(), {"outputType": "file", "filePath": "<work>/stills/title-<n>.png", "maxDimension": 1920})` (Resolve 21.1.2+, `resolve-core` §10; no playhead move; Mac path, `resolve-core` §8). Older: playhead to the marker (`tl.SetCurrentTimecode(tc)`), `project.ExportCurrentFrameAsStill("<work>/stills/title-<n>.tif")`. Read it. Move a lower third or callout away from the face and from the UI the viewer must see; for a callout read the point (`--at x y`, 0..1 from the top-left) off this still.
3. Spec:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/motion.py build --kind <kind> --text "<text>" [--sub "<line 2>"] [--at X Y] [--count FROM TO] \
     --fps <fps> --width <w> --height <h> [--hold-s <marker duration s>] --comp-start <comp frame of the item start> --anim <anim> \
     --font "${user_config.brand_font}" --style "${user_config.brand_font_style}" --text-color "${user_config.brand_text_color}" \
     --accent "${user_config.brand_accent_color}" --plate "${user_config.brand_plate_color}" --plate-opacity ${user_config.brand_plate_opacity} \
     --out "<work>/graphics/<n>.json"
   ```
   It prints `timing_frames` (in / hold / out) and `visible` (first and last comp frame). It places a lower third inside the action-safe area from an estimate of the text width, and puts a callout label above or below its point (never on it), shifted inward so it stays inside the safe area; the dot sits exactly on `--at`. Second lines use `--sub-style` (default `Regular`; pass the brand style to keep them bold). Placement is an estimate: the stills in step 7 decide, and a correction goes into the spec, then re-apply.
4. Insert on the `Titles` track. Resolve 21.1.2+ (gate in `resolve-core` §10): the insert *ripples* at the playhead on a track the API can't choose and returns `None` when that track is locked, so never insert at the marker and never lock tracks to steer it. Read `tl.GetEndFrame()` and turn it into a timecode with `python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/tc.py to-tc <frame> --fps <fps> [--drop]`. Then in one script (the inserted item doesn't survive between calls):
   1. Check `tl.GetEndFrame()` is still that frame. Record each video track's `GetIsTrackLocked` (keep it in the result) and unlock them all. Record `(GetStart(), GetEnd())` of every item on every video and audio track.
   2. `tl.SetCurrentTimecode(<end tc>)`, re-read `GetCurrentTimecode()`; `item = tl.InsertFusionCompositionIntoTimeline()`. `None` → restore the locks, stop and report. Past the end of every track there is nothing to ripple.
   3. Target track: `Titles`, unless any item on it overlaps `[marker_frame, marker_frame + item.GetDuration())` (another title still visible counts): then `Titles 2` (`track_index(..., create=True)` from `track-layout`). Check the whole range, not just the marker frame: `SetPosition` onto an occupied range returns `True` and silently cuts the item already there.
   4. `item.SetPosition({"trackIndex": <target>, "startFrame": marker_frame}, False)`; re-read `GetTrackTypeAndIndex()` and `GetStart()`.
   5. Set each video track back to its recorded lock value, not simply unlocked. Re-read `(start, end)` of every recorded item: any change → stop and tell the user (Undo in Resolve, or the backup timeline).

   Older Resolve (no `SetPosition`): playhead to the marker, temporarily lock every video track except `Titles` (recorded and restored as above), insert, check `item.GetTrackTypeAndIndex()` is `Titles`, `item.GetStart()` the marker frame and the recorded items unchanged. Unverified there; say so.
5. Item length is the user's *Standard generator duration* preference. Fusion compositions and titles have no handles, so `SetRightOffset` returns `False` on them (only media items can be trimmed). The animation fades out at `visible[1]`, so a longer item is just transparent. If the hold needs more than the item length, tell the user to raise the preference (Preferences → User → Editing) or trim by hand; never shorten the hold to fit.
6. Apply the spec with the builder in `resolve-core/reference.md` (Fusion builds from a spec). First build of the session: discover the comp's start frame and the Text+ / Transform / Merge input ids (`tool.GetInputList()`), as listed under runtime discovery there, and pass `--comp-start` accordingly; the Text+ box behind the text uses shading element 3 (`Enabled3`, `Alpha3`, `ExtendHorizontal3`…), check those ids exist. A different id → adjust the spec and say so.
7. Verify every graphic: export stills at `visible[0] + in` (fully in) and `visible[1]` (gone), Read them. Use `tl.ExportFrame` (it renders all tracks and Fusion titles; `item.ExportFrame` only works on media items) at timeline offset `item.GetStart() + (comp_frame - comp_start) - tl.GetStartFrame()`; older Resolve: playhead there + `ExportCurrentFrameAsStill`. For any `--anim` but `slide` also export `visible[0] + in // 2` (mid-intro), which must show the effect working: `scramble` different letters, `word-grow` later words smaller, `fade-reveal` the lower part of the text hidden, `spin` a line turned toward edge-on, `pop` the text larger, `swipe-down` the text higher; for `flicker` compare two frames one step apart (one with text, one without). `scramble` can also be read without a still: the modifier's `ScrambledText` output (`txt.StyledText.GetConnectedOutput().GetTool().GetOutputList()`, `.GetValue(frame)`) differs from the phrase mid-intro and equals it at the hold. Check: Cyrillic glyphs render in the brand font (no boxes, no fallback font), text inside the action-safe area, plate behind the whole text, nothing covers the face or the demo, alpha 0 at the end.

Counter: the number is driven by a Fusion expression on `StyledText`; read `GetInput("StyledText", t)` at the start and end of the count to confirm it runs.

## 4. Motion rules (why the script does what it does)

- Ease-out on the way in (fast start, soft landing), ease-in on the way out. Linear motion looks mechanical.
- In ≈ 0.4 s (for `slide`; other animations in the table below), out ≈ 0.3 s; slide distance ≈ 3 % of the frame. Bigger, longer moves pull attention from the speaker.
- Hold = reading time: 0.5 s + characters / 14 per second, at least 3 s for a name plate, at most 7 s. Viewers read a title about twice before it may go.
- A second line enters 0.12 s after the first. Never more than one graphic on screen, except a callout on a screen recording.
- Same kind = same position, size and motion all video long.

Animations (`--anim`; default `${user_config.brand_text_anim}`, a marker note may override it for one graphic, but warn when that breaks the one-motion-per-kind rule):

| anim | intro | how |
|---|---|---|
| `slide` | 0.4 s | slide ~3 %, scale up, fade in (the default) |
| `swipe-down` | 4 frames @25 | drops 5 % into place, motion blur |
| `pop` | 4 frames @25 | from 125 % down to 100 %, S-curve, motion blur |
| `flicker` | 0.6 s | on/off every ~2 frames, then on |
| `fade-reveal` | 1 s | soft-edged rectangle mask rises from below the text |
| `spin` | 1 s | each line spins 360° around Y, motion blur |
| `scramble` | 1 s | Text Scramble modifier, randomness 1.2 → 0, substitutes only the phrase's own letters |
| `word-grow` | 0.4 s + 2 frames per character | Follower modifier, words grow 0 → 100 % left to right |

`scramble` and `word-grow` take over the text input, so they don't apply to a `counter`; the dot of a callout always uses `slide`. Spin, scramble, word-grow and fade-reveal act on the Text+ itself (the plate moves with it), check them on the step 7 stills: a reveal mask that clips the plate, or a follower that jitters inside words → report and fall back to `slide` for that graphic.

## 5. Finish

`track-layout recolor`, restore the locks, save. Mark handled Cyan / Blue markers `claude:done:fusion-motion-graphics:<date>`. Report the table with the final TCs, any graphic that needs a longer generator duration, and the stills to look at. Suggest `sound-design` for whooshes on titles (2–4 frames before they appear).

## Never

- Change the user's title text beyond typography, or place proposals that weren't approved.
- Put graphics on A-roll, B-roll or Screen tracks, or move/trim the user's clips.
- Copy MotionVFX `.drfx` files anywhere.
