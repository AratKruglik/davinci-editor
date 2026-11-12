# `split-edits`: J-cuts and L-cuts where the picture source changes

[← All skills](README.md)

## What it does

Finds joins where the picture source really changes and proposes a J-cut or L-cut with a shift in frames:

- another clip or take on A-roll;
- camera / screen / PiP switches;
- B-roll with live sound.

After your approval it builds them without touching video items. The audio is laid with the split while assembling, or trimmed (Resolve 21.1.2+) or relaid on a copy of the cut timeline. It also handles your Cocoa markers whose note says `J`, `L` or `split`.

- **J-cut:** the next shot's sound starts before its picture, so the change feels expected.
- **L-cut:** the picture has changed and the previous sound runs on under it, so a thought ends without being chopped.

Same mechanics, opposite direction: one skill.

Principle: only where the picture source changes. Shift the sound at a jump cut inside one clip and words that `text-based-cut` removed come back, the first word of the next segment gets clipped, or the same face moves its mouth with no sound. Every proposal passes hard checks first. A proposal that fails is rejected, and you see why.

Design note: [split-edits.md](../split-edits.md) (in Ukrainian).

## When it triggers

Automatically when you want J/L cuts, split edits, sound leading or trailing the picture, smoother joins between takes or between camera and screen, or the live sound of B-roll before or after the insert. Cocoa markers whose note says J, L or split trigger it too. Ukrainian trigger phrases: «зроби J-кати», «L-кат», «розділені склейки», «хай звук іде раніше картинки», «звук наступного плану заходить раніше», «згладь склейки між дублями». English ones: "split edit", "J/L cuts". In `edit-episode` it is stage B, step 7, after `text-based-cut` and `dual-video-sync-pip`.

Explicit call:

```
/davinci-editor:split-edits [timeline] [auto|markers]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the cut timeline to work on | the current timeline |
| `scope` | `auto`: automatic candidates plus your markers. `markers`: only your Cocoa J / L / split markers; every automatic proposal is set to `keep` without asking | `auto` |

## Before you start

- A cut timeline (normally the rough cut from `text-based-cut`).
- Transcripts in `<work_dir>/<project>/transcripts/`. Missing, the skill runs `uk-transcribe` first.
- `cuts.json` from `text-based-cut`, if it exists: it lets the checks see which words were cut.
- Optional: your Cocoa markers on joins (below).

## Markers it reads

Split edits have no color of their own (all 16 are taken), so they use **Cocoa** (`transition` in `marker_colors`) with a note:

| Note | Meaning |
|---|---|
| `J` / `L` | that type, default shift |
| `J 10`, `L 20` | type and shift in frames |
| `split` | Claude picks type and shift and explains |

The note is only that: `J`, `L` or `split`, optionally followed by frames (`J10` and `J 10` are the same). Anything else ("Light leak", "L-подібний шторка") is a transition name.

Cocoa without these words stays a MotionVFX transition (`marker-edit`). The marker belongs on a join. One more than 1 s from any A-roll join comes back as a question: Claude asks, doesn't guess.

A marker overrides the automatic choice at its join, but **not** the hard checks. If it fails one, Claude explains why and offers the other type or a shorter shift. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## Where it splits

| Join | What moves | Usually | Built by |
|---|---|---|---|
| A-roll: another clip / take | Voice boundary between the two clips | J (new take's room tone leads in) | this skill, or `text-based-cut` while assembling |
| Camera ↔ Screen / PiP (tutorials) | the moment the picture switches, relative to the phrase | L into the screen, J back to camera | `dual-video-sync-pip`, before it places the Screen items |
| B-roll with live sound | its own sound on the `Ambience` track before / after the picture | J in, L out | this skill, only adding to Ambience |
| Chapter boundary (Blue) | music or ambience of the next chapter starts earlier | J | handed to `sound-design` as a Sky cue a few frames before the chapter |

Never split a join inside one clip from one camera. A punch-in does not change the source, so it is still a jump cut; those joins belong to [`jump-cuts`](jump-cuts.md).

Out of scope (Claude says so if asked):

- two speakers on two cameras with crossfaded overlapping voices (Voice / Voice 2);
- volume keyframes;
- nested timelines and multicam.

## Hard checks

Run on every proposal, again after you change one, and at the end:

1. **Nothing cut is heard:** the extra sound has no transcript words and doesn't overlap a cut from `cuts.json`.
2. **No silent picture:** where a speaker's picture plays over the other clip's sound, that speaker says nothing.
3. **Media exists:** the shift fits in the media handle.
4. **Not mid-word:** the shortened side keeps at least 0.15 s between the new boundary and the nearest word.
5. **Sync:** after the build, every Voice item sits exactly under the A-roll item of its clip.

Craft rules. Claude follows them by default; if you ask to break one, it does and says what it costs:

- J fits the start of a new thought or chapter, L the end of a thought or a reaction.
- Voice shifts stay shorter than ambience or music shifts: a voice detached from its face shows.
- No split within 1 s of a transition (Cocoa) or a zoom (Pink): the viewer would get two changes at once. Automatic candidates there are rejected. Your marker there is kept with a warning.
- At most `split_max_in_row` split edits in a row without a plain cut.

## Two ways to build

- **Mode 1, while placing (preferred, nothing is deleted).**
  - `text-based-cut` asks for J/L at clip changes before it appends, and lays Voice with the split.
  - `dual-video-sync-pip` shifts its camera ↔ screen sections before placing Screen.
  - B-roll live sound is only ever added on Ambience.
- **Mode 2, on a cut timeline** (what this skill does when you call it):
  - It works on a duplicate; the original stays as it was.
  - On Resolve 21.1.2 and later, each split is one trim on the Voice item whose sound is extended: its edge moves into the neighbour's audio, in place, and overwrites that edge. Nothing is deleted, so there is no permission prompt, and volume, voice isolation, color and links stay as they were.
  - On older Resolve the API can't trim an edge, so the changed Voice items are unlinked and only those audio items are deleted (no ripple), then appended again with the new ranges. Then they are relinked and their volume, voice isolation, color and fades are restored.
  - **Video items are never relaid or trimmed:** relaying would erase zooms, Fusion comps, PiP transforms and grades.
  - So camera ↔ screen splits on a timeline whose Screen items are already placed are **reported, not built.** Claude offers to re-run `dual-video-sync-pip` on a copy with the shifted sections, or you move those edits by hand.

## Settings

| Key | Default | Effect |
|---|---|---|
| `split_j_lead_frames` | `12` | how many frames the next shot's sound starts before its picture |
| `split_l_tail_frames` | `12` | how many frames the previous shot's sound runs on under the new picture |
| `split_max_frames` | `50` | largest shift; more is a scene overlap, not a cut |
| `split_fade_frames` | `4` | audio fade on the moved end |
| `split_max_in_row` | `3` | most split edits in a row without a plain cut |
| `marker_colors` | `…,Cocoa=transition,…` | which color carries the J / L / split notes |
| `work_dir` | `resolve-work` | where the dump and plans are written |

These are starting values: tune them after a few episodes. Any setting can be overridden in the prompt: "J lead 8 frames", "L tail 20".

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `transcripts/*.json`, `cuts.json` | input from `uk-transcribe` and `text-based-cut` |
| `timeline-<name>.json` | timeline dump (items, media handles, timeline markers); a fresh one for the copy before verifying |
| `split-plan.json` | every proposal with its checks, reason and your `split` / `keep` decision; a later run reuses it so decided joins aren't asked again |
| `split-audio.json` | the new Voice and Ambience ranges built from the decisions |

## Workflow and approval stops

1. Says the project and timeline names, saves the project, runs the append calibration once per session, and dumps the timeline.
2. Computes candidates and runs the hard checks (`split_edits.py joins`). When relevant, it also prepares shifted sections for a tutorial whose Screen isn't placed yet (handed to `dual-video-sync-pip`). For B-roll inserts it proposes Ambience sound: only for clips with audio that you want heard. With scope `markers`, automatic proposals are kept as plain cuts.
3. **Approval: the plan.** One table in time order: #, timecode, join (clip → clip), type, frames, words around the join (which sound moves), why. Then the rejected proposals with reasons, then questions. Answer in one message: "all except 3; 5 as L 8". If you change a shift and it no longer passes the checks, Claude refuses it and tells you; it doesn't force it.
4. **Builds on a copy** named `<name> - split <date>`.
   On Resolve 21.1.2 and later:
   - one trim per split on the extended Voice item, with the video left where it is;
   - after the first trim it re-reads both Voice items and both A-roll neighbours. If a video edge moved, it stops and builds everything the older way on a fresh copy;
   - it sets fades on the moved ends and adds Ambience items, if any (only adding).

   On older Resolve it relays only the changed Voice items:
   - it records each item's volume, fades, voice isolation, color, linked video and any audio crossfade at its ends;
   - it deletes all changed audio items in one call. That is a permission prompt (the `guard.py` hook); Claude says which audio items go and that they come back at once with the new ranges. Nothing is appended until every changed item is gone, because an L reaches into the space the next item still occupies;
   - it re-checks that A-roll is unchanged. If video went with the audio, it stops and reports;
   - it appends every item with its new range, relinks it to its video, restores volume, voice isolation and color, sets fades on the moved ends and re-adds the crossfades at unmoved ends;
   - it adds Ambience items, if any (only adding).
5. **Verifies** on a fresh dump: Voice sits under its A-roll item, item counts per track are as before (plus Ambience), the timeline end is unchanged, and every A-roll / Voice pair is linked. Anything off is reported with the item and timecode, never nudged silently.
6. **Marks:**
   - each split gets a **Cream** timeline marker named `J` or `L`, with the shift and reason in the note;
   - your handled Cocoa markers get `customData` only; their color, name and note stay as they are.
   Then it recolors clips by role and saves.
7. Reports the copy's name, splits by type with timecodes, rejected ones with reasons, camera ↔ screen splits not built and why, Ambience inserts, and what to listen to (the first J and the first L).

## What it never does

- Change or delete the original timeline, or relay or trim a video item.
- Build a split that failed a hard check, even when a marker asks for it.
- Split a join inside one clip.
- Leave the copy with unlinked or out-of-sync A-roll / Voice pairs.
- Change the color, name or note of your markers.

## Place in the workflow

`uk-transcribe` → `track-layout` → `text-based-cut` → `dual-video-sync-pip` → `marker-edit` (Fuchsia, Cocoa) → **`split-edits`**

Clip changes were already offered in `text-based-cut` and camera ↔ screen switches in `dual-video-sync-pip` (mode 1); this step does the rest on a copy. Run it before sound: `sound-design` and `audio-finish` build on the final audio boundaries.

## Example prompts

**Minimal:**

> Make J and L cuts on the rough cut where it makes sense.

**With arguments, one per scope:**

```
/davinci-editor:split-edits "Router - rough cut 2026-11-02" auto
/davinci-editor:split-edits "Router - rough cut 2026-11-02" markers
```

**Overriding a setting:**

> J/L cuts on the current timeline, but J lead 8 frames and at most 2 splits in a row: this lesson is fast and I don't want the sound floating.

**Professional brief:**

> J and L cuts on "Router - rough cut 2026-11-02", scope auto. Three takes, IMG_4140 to 4142; the joins inside IMG_4140 are jump cuts, leave them alone. I put a Cocoa marker with "J 10" on one join: if it fails a check, tell me why and what you'd do instead. Leave the joins next to my Pink zoom markers alone. Show the plan with the words around each join before building, and build only on a copy. At the end list the splits with timecodes, the rejected ones with reasons, and which J and L to listen to first.

**Scope `markers`:**

> Only my Cocoa J/L markers on the current timeline, no automatic suggestions.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Smooth out the cuts" | "Make J and L cuts on the rough cut where it makes sense. I also put a Cocoa marker on one join: if you can't build it, tell me why." |

The strong prompt names the timeline, says where your own instruction is, and asks for the reason when a check fails. You get a plan, not a silent skip.

## What to check afterwards

- Listen to the first J and the first L on headphones: does the sound lead or trail naturally, with no clipped word and no cut word coming back?
- Step through the Cream `J` / `L` markers on the copy; all Cream markers can be removed at once.
- A-roll and Voice are still linked and in sync on the copy.
- Fades on the moved ends survived (on older Resolve: whether they survive relinking is unverified).
- A 2-frame crossfade from `text-based-cut` at a moved join: how it behaves under a trim is unverified, so listen to it.
- Camera ↔ screen splits the report lists as not built: re-run `dual-video-sync-pip` on a copy, or move them by hand.
