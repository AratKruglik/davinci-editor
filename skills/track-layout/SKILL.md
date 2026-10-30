---
name: track-layout
description: Sets up and maintains role-based tracks on a DaVinci Resolve 21+ timeline - video Backgrounds, A-roll, B-roll, Effects, Titles and audio Voice, SFX, Music (plus Screen, B-roll 2, Voice 2, Ambience, Subtitles UA on demand) - names them, colors clips by role, locks tracks per stage and removes empty tracks after confirmation. Other skills find tracks by role through it, never by number.
when_to_use: New or rough-cut timeline needs the standard track structure, a track for a role is missing, clips need recoloring by role, tracks should be locked for a stage, or empty tracks should be cleaned up before render. Triggers - "розклади доріжки", "структура доріжок", "додай доріжку B-roll", "прибери порожні доріжки", "track layout", "перефарбуй кліпи по ролях".
argument-hint: "[setup|add <role>|recolor|lock <stage>|cleanup]"
arguments: [action, role]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Track layout by role

Follow `resolve-core` first. Action: `$action` (default `setup`).

## Layout (from plugin config)

Video, bottom to top — order matters, higher tracks cover lower ones: `${user_config.video_tracks}`
Audio, top to bottom: `${user_config.audio_tracks}`
Never deleted, even when empty: `${user_config.protected_tracks}`

Each entry is `Name:ClipColor`. On-demand roles and their clip colors: Screen (above A-roll):Navy, PiP (above Screen):Violet, B-roll 2 / Titles 2: same as base role, Voice 2:Lime, Ambience:Olive, Subtitles UA (subtitle track).

Why this order: Backgrounds under everything (PiP plates), A-roll is the base, B-roll covers A-roll, Effects (adjustment clips) affect picture but not titles, Titles always on top.

## API limits and how to live with them

| Need | Possible? | Workaround |
|---|---|---|
| Name a track | `tl.SetTrackName(type, i, name)` | — |
| Color the track header | no API | `.drt` template (below); clip colors via `item.SetClipColor(color)` are kept in sync instead |
| Insert a track at a position | no: `AddTrack(type, subTrackType)` appends on top | plan all tracks before placing clips; for a middle track ask the user to add it (right-click track header → Add Track → position), then name it |
| Move a clip between tracks | no | never delete-and-re-add a clip to move it: that loses effects, grades and keyframes |
| Lock / enable | `SetTrackLock`, `SetTrackEnable` | — |

Audio `subTrackType`: `"mono"`, `"stereo"`, `"5.1"`… — Voice is `mono` when it's a single mic, otherwise match the source.

## Find a track by role (use this in every skill)

```python
def track_index(tl, kind, role, create=False, sub=None):
    names = [tl.GetTrackName(kind, i) for i in range(1, tl.GetTrackCount(kind) + 1)]
    for i, n in enumerate(names, 1):
        if n.strip().lower() == role.lower():
            return i
    if not create:
        return None
    tl.AddTrack(kind, sub) if sub else tl.AddTrack(kind)
    i = tl.GetTrackCount(kind)
    tl.SetTrackName(kind, i, role)
    return i
```

Only `create=True` for roles that belong on top (Titles 2, B-roll 2 when nothing is above it) or on an empty timeline. Re-read names after creating to confirm `AddTrack` really appended on top (unverified in 21.1.1; if not, report where it went).

## setup

1. Timeline template: if `${user_config.track_template}` is set (a `.drt` exported from an empty timeline the user styled once — names, header colors, order), create new timelines with `mp.ImportTimelineFromFile(path)` and rename. Whether `.drt` keeps header colors is unverified — check once and tell the user.
2. Otherwise on an **empty** timeline: add tracks up to the configured count and name them in order. On a timeline that already has clips: only rename tracks whose content clearly matches a role (ask when unsure), add missing roles on top only if their place is on top, and list the rest for the user to add manually.
3. Look ahead before placing content: transcript type and markers tell what this episode needs (Purple → Screen and PiP, overlapping Fuchsia → B-roll 2, two speakers → Voice 2, Lavender/Sky with room tone → Ambience). Create those tracks now, in order.
4. Verify by reading back every track name and report the final layout table (index, type, name, clip count).

## recolor

For every track with a known role, `item.SetClipColor(role_color)` on each item; skip items already that color. Run it after any skill that placed clips.

## lock

Stage locks (ask before changing locks the user set): sound stage → lock Voice and A-roll; graphics stage → lock A-roll, B-roll, Voice. Unlock when the stage ends. Report which tracks are locked.

## cleanup

1. List empty tracks (`GetItemListInTrack` returns no items), excluding protected roles.
2. Show the list and get an explicit yes.
3. Delete **from the highest index down** so lower indices don't shift mid-operation; re-read the layout and report.
Typical moments: after the rough cut and before render.
