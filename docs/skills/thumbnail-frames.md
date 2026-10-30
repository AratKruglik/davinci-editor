# `thumbnail-frames`: thumbnail candidate stills and a brief

[← All skills](README.md)

## What it does

Finds frames for a YouTube thumbnail in a graded, cut timeline: your Lemon markers plus strong moments from the transcript (a result, a reveal, an emotion). Around each moment it exports a short burst of clean stills with titles and subtitles hidden, so a blink or motion blur doesn't cost the moment. A script ranks the stills by sharpness and exposure, Claude looks at the best ones for eyes, expression and room for text, and writes a thumbnail brief with full-resolution PNGs.

What makes a frame work at 160 px wide: one readable face, eyes open and looking at the lens or the subject, a clear emotion (surprise, joy, focus), sharp, well exposed, and empty space on one side for the title text. Everything else is secondary.

## When it triggers

Automatically when you ask for frames for a YouTube thumbnail or cover, the best shot of the face, or when you have Lemon markers. Ukrainian trigger phrases: «кадри для обкладинки», «знайди кадр для превʼю», «кадр для мініатюри», «обкладинка», «найкращий кадр». In `edit-episode` it is stage D, step 6.

Explicit call:

```
/davinci-editor:thumbnail-frames [timeline] [count]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the timeline to take stills from; graded, because the still is taken through the grade | the current timeline |
| `count` | how many frames to pick | `5` |

## Before you start

- A cut and graded timeline.
- The transcript words mapped onto the cut (`timeline_map.py words`), so the transcripts from `uk-transcribe` must exist.
- Optional: Lemon markers on the frames you like (below).

## Markers it reads

| Color | Task | Effect |
|---|---|---|
| **Lemon** | `thumbnail` | the exact frame; always included. The note is the emotion or idea. A note can also ask for a B-roll or screen frame (e.g. the finished product); otherwise only talking-head frames are used |

Lemon markers are read from the timeline and its items by the `marker-edit` rules; markers whose `customData` is `claude:done:*` are skipped. Handled Lemon markers get `claude:done:thumbnail-frames:<date>`. Claude marks its picks with **Cream**, never Lemon. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## How candidates are found and scored

1. **Moments.** All Lemon markers, plus moments from the words on the cut: the result or "after" moment ("and there it is, it works!"), a reveal, a surprise or a laugh, the strongest claim of the hook. Up to 2× `count` moments in total, spread over the video.
2. **Clean stills.** The `Titles`, `Subtitles UA` and subtitle tracks are disabled, and the `Effects` track if it holds text. Each track's state is recorded first and set back to **that recorded value** at the end, even if an export fails: a track you had disabled stays disabled.
3. **Burst.** Per moment, 5 stills at offsets −6, −3, 0, +3, +6 frames (a blink lasts about 4 frames at 25 fps).
4. **Script ranking** (`thumbs.py score`): flags soft frames (motion blur), under/over-exposed and clipped frames. It can't see faces.
5. **Visual pass.** Claude looks at the two best-scored stills of every moment (more if they are close) and judges: eyes open and sharp, expression readable, mouth not mid-word in an awkward shape, face size (about ⅓ of frame height or more is best), head not cut, space for text in the left or right third, background not busy. Frames that fail on eyes or sharpness are discarded whatever their score.

## Settings

The skill has no settings of its own. Stills and the brief go under `work_dir` (default `resolve-work`), the shared work folder from `resolve-core`.

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `thumbnails/<n>_<offset>.tif` | the burst stills of every moment |
| `thumbnails/scores.json` | sharpness and exposure ranking from `thumbs.py` |
| `thumbnails/*.png` | full-resolution PNG of every pick, next to its TIFF, for the designer |
| `thumbnail-brief.md` | the brief: `# | TC | file (PNG) | emotion / moment | why it works | text space | crop note`, plus 2–3 title-text ideas per pick (≤ 4 words, from what is said at that moment) |

## Workflow and approval stops

1. Collects the moments (Lemon markers and transcript moments).
2. Records and disables the title and subtitle tracks, exports the bursts, checks each file exists.
3. Ranks the stills with `thumbs.py score`.
4. Looks at the best stills and picks `count` frames; exports a PNG of each and puts a Cream marker at each pick (`customData` `claude:thumbnail`, name = short description).
5. Writes `thumbnail-brief.md` and tells you the folder. If a thumbnail skill such as `youtube-thumbnail-strategist` is installed, offers the brief to it (optional).
6. Marks the Lemon markers done, restores the track states and reports them restored.

There is no approval stop inside the skill: the picks are a proposal in the brief. In `edit-episode` you pick the thumbnail before rendering.

## What it never does

- Leave the titles or subtitle tracks disabled.
- Pick a frame it hasn't looked at, or one with closed or half-closed eyes.
- Write stills into the media folders.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`chapters-markers` → `shorts-cutdown` → **`thumbnail-frames`** → `pre-delivery-qc` → `deliver`

Next: `deliver` copies `thumbnail-brief.md` and the picked PNGs into the upload package.

## Example prompts

**Minimal:**

> Find frames for the thumbnail.

**With arguments:**

```
/davinci-editor:thumbnail-frames "Router Setup - final" 3
```

**Overriding a default:**

> Thumbnail frames from the current timeline, give me 8 picks instead of 5: the designer wants more to choose from.

**Using your Lemon marker:**

> Pick frames for the cover, I put a Lemon marker on the moment with the result.

**Professional brief:**

> Thumbnail frames from "Router Setup - final", 4 picks. My two Lemon markers are on the speed test result and on the moment I unbox the router; the unboxing one has a note asking for the B-roll close-up of the router, include it. Add your own picks from the strongest moments: the reveal when the speed jumps and my reaction to it. I need eyes open and looking into the lens, and empty space on the right for the title. Reject anything soft or mid-word. In the brief give me the timecode, the PNG file, why it works and 2–3 short title ideas per pick.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Find a good frame" | "Thumbnail frames from the graded final cut: my Lemon marker on the result plus your three strongest emotional moments, eyes to the lens, space for text on the left." |

The strong prompt names the timeline, the moments and the composition you need, so the visual pass judges against your thumbnail, not a generic one.

## What to check afterwards

- Open the PNGs at full size: eyes sharp, no motion blur, expression what you want.
- Make sure `Titles` and the subtitle tracks are enabled again as they were (Claude reports it).
- The Cream `claude:thumbnail` markers stay on the timeline until you remove them.
