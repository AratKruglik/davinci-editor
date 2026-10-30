---
name: fusion-motion-graphics
description: Builds on-screen graphics in DaVinci Resolve Studio 21+ with Fusion - lower thirds (name plates), callouts pointing at a spot on screen, kinetic key phrases, number counters and chapter cards - from the user's Cyan markers (name = text) and Blue chapter markers, in the brand style from the plugin config (font, text, accent and plate colors), with eased timing and reading-time holds computed by a script, placed on the Titles track and checked on an exported still. Uses an installed MotionVFX title instead when the marker names one.
when_to_use: User wants titles, name plates, lower thirds, callouts, captions for key ideas, animated numbers or chapter cards on a cut timeline, or has Cyan markers; the graphics step of edit-episode stage D. Triggers - "додай титри", "плашка з іменем", "лоуер терд", "виноска", "покажи цифру анімовано", "кінетична типографіка", "заставка розділу", "motion graphics", "lower third".
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

Brand (plugin config): font `${user_config.brand_font}` `${user_config.brand_font_style}`, text `${user_config.brand_text_color}`, accent `${user_config.brand_accent_color}`, plate `${user_config.brand_plate_color}` at `${user_config.brand_plate_opacity}`.

Script: `${CLAUDE_SKILL_DIR}/scripts/motion.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/motion.py selftest`).

Principle: graphics serve the viewer's attention, not decoration. A tutorial needs few graphics, each readable at a glance, all in one style; ten different animations look amateur even when each is pretty.

## 1. What to build

Sources, in this order:
- **Cyan** markers (timeline and timeline items, `marker-edit` rules; skip `claude:done:*`): name = the text, exactly as the user wrote it; note = kind or a MotionVFX template name; marker duration = how long it stays (point marker: reading time).
- **Blue** markers = chapter starts → a chapter card (kind `kinetic`, the chapter name) only if the user wants cards; ask once per episode.
- The request in `$request` (e.g. `lower-third Олексій Круглик / автор каналу`).
- Proposals from the transcript (`<work>/words-<timeline>.json`, see `resolve-core` §4): the speaker's name on first appearance, a number worth a counter ("на 40 відсотків"), a term defined on screen. These are **suggestions** only: show them, place nothing unasked.

Kinds: `lower-third` (name / role, lower left), `callout` (short label + accent dot at a point on screen), `kinetic` (a key phrase, centered low), `counter` (number counting up, accent color). The note decides; no note → `lower-third` for names, `callout` when the note names a spot ("кнопка Save", "праворуч угорі"), `kinetic` otherwise.

Text: keep the user's wording. Fix only obvious typography: Ukrainian apostrophe `ʼ`, quotes «», dash —, no full stop at the end of a title. A typo you suspect → ask, don't fix silently.

Show the plan before building: `# | TC | kind | text | duration | route (Fusion / MotionVFX name) | track`. Wait for the yes.

## 2. Route

- **MotionVFX / installed template** when the note names one: look it up with `python3 ${CLAUDE_SKILL_DIR}/../motionvfx-catalog/scripts/catalog.py search "${user_config.work_dir}/motionvfx-catalog.json" --category Titles <words>` (no catalog → run `motionvfx-catalog`). Insert with `tl.InsertFusionTitleIntoTimeline(name)` and fill its `StyledText` inputs (`text_inputs` from the catalog says how many) through `item.GetFusionCompByIndex(1)`.
- **Built here** otherwise: brand-styled Fusion composition from a spec.

## 3. Build (Fusion route)

1. Backup the timeline (`resolve-core` §3). Lock `A-roll`, `B-roll`, `Voice` for the stage (`track-layout lock`).
2. Still for placement: playhead to the marker (`tl.SetCurrentTimecode(tc)`), `project.ExportCurrentFrameAsStill("<work>/stills/title-<n>.tif")`, Read it. Move a lower third or callout away from the face and from the UI the viewer must see; for a callout read the point (`--at x y`, 0..1 from the top-left) off this still.
3. Spec:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/motion.py build --kind <kind> --text "<text>" [--sub "<line 2>"] [--at X Y] [--count FROM TO] \
     --fps <fps> --width <w> --height <h> [--hold-s <marker duration s>] --comp-start <comp frame of the item start> \
     --font "${user_config.brand_font}" --style "${user_config.brand_font_style}" --text-color "${user_config.brand_text_color}" \
     --accent "${user_config.brand_accent_color}" --plate "${user_config.brand_plate_color}" --plate-opacity ${user_config.brand_plate_opacity} \
     --out "<work>/graphics/<n>.json"
   ```
   It prints `timing_frames` (in / hold / out) and `visible` (first and last comp frame). It places a lower third inside the action-safe area from an estimate of the text width, and puts a callout label above or below its point (never on it), shifted inward so it stays inside the safe area; the dot sits exactly on `--at`. Second lines use `--sub-style` (default `Regular`; pass the brand style to keep them bold). Placement is an estimate: the stills in step 7 decide, and a correction goes into the spec, then re-apply.
4. Insert on the `Titles` track: playhead to the marker, temporarily lock every other video track so the insert can only land on `Titles` (read each track's `GetIsTrackLocked` first and keep it in the script's result; afterwards set each track back to that recorded value, not simply unlocked), `item = tl.InsertFusionCompositionIntoTimeline()`. Check `item.GetTrackTypeAndIndex()` is the Titles track, `item.GetStart()` is the marker frame. Another title still visible at that frame → use `Titles 2` (`track_index(..., create=True)` from `track-layout`).
5. Item length is the user's *Standard generator duration* preference; the API can't trim items. The animation fades out at `visible[1]`, so a longer item is just transparent. If the hold needs more than the item length, tell the user to raise the preference (Preferences → User → Editing) or trim by hand; never shorten the hold to fit.
6. Apply the spec with the builder in `resolve-core/reference.md` (Fusion builds from a spec). First build of the session: discover the comp's start frame and the Text+ / Transform / Merge input ids (`tool.GetInputList()`), as listed under runtime discovery there, and pass `--comp-start` accordingly; the Text+ box behind the text uses shading element 3 (`Enabled3`, `Alpha3`, `ExtendHorizontal3`…), check those ids exist. A different id → adjust the spec and say so.
7. Verify every graphic: export stills at `visible[0] + in` (fully in) and `visible[1]` (gone), Read them. Check: Cyrillic glyphs render in the brand font (no boxes, no fallback font), text inside the action-safe area, plate behind the whole text, nothing covers the face or the demo, alpha 0 at the end.

Counter: the number is driven by a Fusion expression on `StyledText`; read `GetInput("StyledText", t)` at the start and end of the count to confirm it runs.

## 4. Motion rules (why the script does what it does)

- Ease-out on the way in (fast start, soft landing), ease-in on the way out. Linear motion looks mechanical.
- In ≈ 0.4 s, out ≈ 0.3 s; slide distance ≈ 3 % of the frame. Bigger, longer moves pull attention from the speaker.
- Hold = reading time: 0.5 s + characters / 14 per second, at least 3 s for a name plate, at most 7 s. Viewers read a title about twice before it may go.
- A second line enters 0.12 s after the first. Never more than one graphic on screen, except a callout on a screen recording.
- Same kind = same position, size and motion all video long.

## 5. Finish

`track-layout recolor`, restore the locks, save. Mark handled Cyan / Blue markers `claude:done:fusion-motion-graphics:<date>`. Report the table with the final TCs, any graphic that needs a longer generator duration, and the stills to look at. Suggest `sound-design` for whooshes on titles (2–4 frames before they appear).

## Never

- Change the user's title text beyond typography, or place proposals that weren't approved.
- Put graphics on A-roll, B-roll or Screen tracks, or move/trim the user's clips.
- Copy MotionVFX `.drfx` files anywhere.
