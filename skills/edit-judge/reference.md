# edit-judge rubric

The channel this is tuned for: programming tutorials in Ukrainian. A lesson is built from slides, a screen recording (editor, terminal, browser) and the speaker, either full frame or as a round facecam bubble over the screen. The viewer came to learn one concrete thing and leaves when the video stops giving it.

Every score needs evidence: at least one timecode (or `start-end` range) where the reason for the score can be seen or heard. A level is reached only when all of its points hold; when a video sits between two levels, take the lower one. Numbers in brackets are the `youtube` value, then the `shorts` one.

## Hook

Is it clear from the start what the viewer will get? Look at `hook_words` (words in the first 30 s / 3 s) and `get_image` of the first frames.

| Score | What you see and hear |
|---|---|
| 1 | No topic in the window: greetings, channel talk, "let's start" or silence; the picture is a static facecam or an empty slide. |
| 2 | The topic is named ("today: lists") but not the result; nothing on screen shows what the viewer will be able to do. |
| 3 | The result is said ("you'll learn to add and remove items") but late in the window, after warm-up talk, or only in words while the picture stays generic. |
| 4 | The result is said in the first half of the window and backed by the picture: the finished program, its output or the slide with the goal. |
| 5 | The first sentence states the concrete result or the problem it solves, and the picture shows it at once (the working code or output, the error it fixes); no greeting before it. |

## Pace

Pauses, stretched and static parts. Inputs: `pauses` (gaps over `pause_threshold_ms` between words), `static` (no cut, zoom or title for more than 20 s / 4 s) and `get_thumbnails` over each static span.

A static span is confirmed only when its thumbnails show the same picture. Scrolling, typing, a new terminal line, a slide build or a cursor that moves to what is being explained is a change of picture: that span is not static, and it doesn't count against pace. Talking over the same picture is still static.

| Score | What you see and hear |
|---|---|
| 1 | Several confirmed static spans, or one longer than twice the limit (40 s / 8 s), and pauses left in the speech. |
| 2 | One confirmed static span longer than the limit, or three or more leftover pauses. |
| 3 | No confirmed static span, but one or two leftover pauses or a part that explains the same thing twice. |
| 4 | No confirmed static span and no leftover pause; one place where the picture holds longer than the explanation needs. |
| 5 | Every stretch of the same picture is short or changes as the speaker explains it (typing, scrolling, zoom to the line being talked about); no pause or repeat. |

## Graphics

Are the titles, callouts and zooms in the right places, and is their density right? Inputs: `graphics_per_min`, `per_kind`, the ledger and `get_image` at each element.

| Score | What you see |
|---|---|
| 1 | Graphics hide what is being explained (code, output, the facecam), or they repeat what the screen already says, about every few seconds. |
| 2 | More than about 4 graphics per minute, or key moments (the line being explained, the output that proves the point) have none while minor ones do. |
| 3 | Density is acceptable; some elements add nothing (a callout on an obvious button), or a key line is explained without a zoom or a callout. |
| 4 | Each element points at something the speaker is talking about at that moment; only one or two optional ones. |
| 5 | The graphics carry the lesson: zooms on the line being explained, a callout where the viewer would look away, a lower third at the speaker's first appearance; nothing extra. |

A video with no graphics at all scores 3 when nothing needed one (a short slide talk), and 2 when code is explained at a size the viewer can't read.

## Consistency

Do elements of one `kind` share one style? `get_thumbnails` across all elements of a kind.

| Score | What you see |
|---|---|
| 1 | Elements of one kind look like different templates: other fonts, colors or plates. |
| 2 | Same template, but position or size jumps between elements of one kind (a lower third once bottom left, once bottom right). |
| 3 | Position and size match; motion or timing differs (one fades, one slides; zooms of very different speed or scale). |
| 4 | One style for each kind; one small difference (a line break, a slightly longer hold). |
| 5 | Every element of a kind looks and moves the same; the facecam bubble keeps its corner and size through the whole video. |

Fewer than two elements of every kind: score 5, with the note "one element per kind", evidence the elements' timecodes.

## Rules

Each approved rule from `memory.py rules` separately: is it followed where it applies? Name every rule (id and text) in the note.

| Score | What you see |
|---|---|
| 1 | Most rules are broken in most places they apply. |
| 2 | One rule is broken everywhere it applies, or several rules are broken more than once. |
| 3 | Every rule is followed in most places; one or two exceptions without a reason (no user request or marker note explains them). |
| 4 | All rules followed; one exception explained by a user request or marker note. |
| 5 | Every rule followed everywhere it applies. |

No approved rules for this format: score 5, the note "no approved rules", evidence the timeline's start timecode.

## Ending

Does the video stop after the last thought? Inputs: `tail_s` (last word to the timeline end) and `get_image` / `get_thumbnails` of the last 20 s.

| Score | What you see and hear |
|---|---|
| 1 | More than 10 s after the last word, or the lesson ends and a second unrelated topic starts. |
| 2 | The point is made, then a long goodbye, channel talk or a repeat of the summary (over 15 s / 3 s after the last useful sentence), or a silent tail over 5 s. |
| 3 | A short summary and goodbye after the point, a tail of 2–5 s. |
| 4 | The video ends within a few seconds of the last useful sentence; the goodbye is one line. |
| 5 | The last useful sentence or the final result on screen is the end; at most 2 s of tail. |

## Pick criteria

What "better" means in `pick` mode, by the `<kind>` in `candidates-<kind>.json`. Judge every pair on the same list, in this order of weight.

**`shorts`** (moments for a Short):
1. The first 1–3 s grab: a question, a surprising result or an error on screen, not a greeting.
2. It makes sense on its own, without the lesson around it.
3. It ends on a payoff (the result, the answer), not mid-thought.
4. The picture works vertical: the code or the face can be cropped to 9:16 and stay readable.

**`thumbnails`** (stills):
1. The topic is clear from the frame alone (the code, the error, the result on screen).
2. Readable when small: one subject, strong contrast, no fine text that disappears at thumbnail size.
3. Emotion: an expressive face beats a neutral one, and eyes open beats a blink.

Any other kind: the caller names the criteria in the request; without them, stop and ask the caller.
