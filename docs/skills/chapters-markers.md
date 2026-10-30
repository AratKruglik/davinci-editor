# `chapters-markers`: YouTube chapters from Blue markers

[← All skills](README.md)

## What it does

Builds the YouTube chapter list of a cut timeline. It takes your Blue chapter markers (name = chapter title) and, where they are missing, proposes chapter starts from the topics of the transcript. Every start is snapped to the beginning of a sentence on the cut, YouTube's rules are checked by a script, and the result is the block for the video description plus a JSON hand-off for timestamp and SEO tools.

Why the rules matter: YouTube silently ignores the whole chapter list if one rule is broken. A good list also helps search and retention: titles say what the viewer gets, not "Частина 2".

## When it triggers

Automatically when you ask for YouTube chapters, timestamps for the description, a table of contents of the video, or have Blue markers to turn into chapters. Ukrainian trigger phrases: «зроби розділи», «таймкоди для опису», «таймстемпи», «розбий на розділи», «глави для ютуба». In `edit-episode` it is stage D, step 4.

Explicit call:

```
/davinci-editor:chapters-markers [timeline]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | timeline to build chapters for | the current timeline, which should be the final cut |

## Before you start

- Run it on the final cut: chapters on a timeline that will still change go stale.
- Transcripts from `uk-transcribe`: the skill needs the words on the cut to snap starts to sentences and to propose titles.
- Optional: Blue markers (below). Without them, the skill proposes the whole list.

## Markers it reads

| Color | Task | Name |
|---|---|---|
| **Blue** | chapter start | the chapter title, used exactly as written |

- Blue markers on the timeline are the main source; markers whose `customData` is `claude:done:*` are skipped.
- A Blue marker without a name gets a proposed title from what is said right after it.
- Blue markers left on media pool clips from before the cut are mapped onto the cut. A marker whose moment was cut out is reported, never moved silently.
- Put the marker just before the new topic begins; the skill snaps it to the sentence start (below).

Claude's own proposals are **Cream** markers with `customData` `claude:chapters` and the proposed title as the name. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

How to name a Blue marker:

| Weak name | Strong name |
|---|---|
| `Частина 2` | `Підключаємо роутер до мережі` |
| `1. Налаштування — 02:15` | `Змінюємо пароль Wi-Fi` |

2–6 words, what the viewer learns or does, Ukrainian, no numbering, no timestamps, no clickbait.

## YouTube chapter rules

| Rule | What the skill does |
|---|---|
| First chapter at 0:00 | adds `Вступ` at 0 (or your own first title) if the first chapter starts later |
| At least 3 chapters | proposes more where the topic changes |
| Each chapter 10 s or longer | flags short ones; you merge or move them together |
| Starts on a sentence | a marker in the first half of a sentence snaps to that sentence's start, otherwise to the next sentence's start; moves are listed, and a move over 3 s is a question |
| Proposals | where the topic changes (a new step, a new question, "тепер перейдемо до…"), about every 1–4 min for a tutorial |

`chapters.py check` floors times to whole seconds and must pass before anything is written.

## Settings

This skill has no settings of its own.

## Files

Under `<work_dir>/<project>/` (the work folder from `resolve-core`):

| File | Contents |
|---|---|
| `chapters-sentences.json` | sentences on the cut, for snapping |
| `chapters.json` | the chapter list: frame from the timeline start, title, source (marker / Claude) |
| `chapters.txt` | the block for the YouTube description |

`chapters.txt` looks like this:

```
0:00 Вступ
0:40 Підключаємо роутер до мережі
```

## Workflow and approval stops

1. Dumps the timeline, maps the words onto the cut and splits them into sentences.
2. Reads the Blue markers, snaps each to a sentence start, adds the intro chapter if needed, proposes titles for nameless markers and new chapters where markers are missing (as Cream markers).
3. **Approval: the chapter table.** `# | TC | title | source (marker / Claude) | length`, with the markers that moved and by how much.
4. Writes `chapters.json` and runs `chapters.py check`. Errors are fixed with you (merge a short chapter into its neighbour, add the 0:00 one) and checked again.
5. Writes `chapters.txt`, tells you its path and pastes its content in the reply.
6. Offers optional hand-offs: `chapters.json` and the transcript to `youtube-timestamps` or `youtube-seo-architect` if they are installed; chapter cards on screen through `fusion-motion-graphics` if you want them.
7. Marks handled Blue markers in `customData`.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Write a chapter list that fails the check.
- Reuse a stale `chapters.txt` after the cut changed (it re-dumps and re-checks).
- Change your titles beyond trimming spaces; it suggests edits instead.
- Add Blue markers itself or rename yours.

## Place in the workflow

Stage D: `fusion-motion-graphics` → `tutorial-zooms` → `subtitles-uk` → **`chapters-markers`** → `shorts-cutdown` → `thumbnail-frames` → `pre-delivery-qc` → `deliver`

Chapter cards (`fusion-motion-graphics`, kind `kinetic`) are built from its titles, after this step. `chapters.txt` goes into the upload package.

## Example prompts

**Minimal:**

> Make YouTube chapters from my Blue markers.

**With arguments:**

```
/davinci-editor:chapters-markers "Router - final"
```

**Professional brief:**

> Chapters for the description of "Router - final" from my Blue markers. Keep my titles as they are; if one is weak, suggest a better one but don't change it. One Blue marker has no name: propose a title from what I say after it. Between my markers the section on the admin panel runs 6 minutes, propose one chapter inside it. If any chapter is under 10 s, ask me before merging. Paste the final block in the reply and offer the JSON for youtube-seo-architect.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Add timestamps" | "Chapters from my Blue markers on the final cut, my titles as written, propose the missing ones every 2–3 minutes, ask before merging short chapters." |

The strong prompt says where the titles come from, how dense the list should be and what needs your decision, so the table comes back ready to approve.

## What to check afterwards

- Click through the chapter starts in the rendered video: each one begins on the first word of the new topic.
- Titles: what the viewer gets, no "Частина 2".
- Paste `chapters.txt` into the YouTube description as is; YouTube drops the whole list if the first line isn't `0:00`.
- Remove the Cream `claude:chapters` proposal markers when you're done with them.
- Re-run the skill after any change to the cut.
