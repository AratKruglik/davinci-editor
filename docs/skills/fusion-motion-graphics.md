# `fusion-motion-graphics`: titles, lower thirds and callouts in Fusion

[← All skills](README.md)

## What it does

Builds the on-screen graphics of a cut timeline with Fusion: lower thirds (name plates), callouts pointing at a spot on screen, kinetic key phrases, number counters and chapter cards. The brief comes from your Cyan markers (name = the text) and Blue chapter markers. Everything is drawn in the brand style from the plugin settings (font, text, accent and plate colors), with eased timing and reading-time holds computed by a script, placed on the `Titles` track and checked on exported stills. When a marker names an installed MotionVFX title, that template is used instead.

Principle: graphics serve the viewer's attention, not decoration. A tutorial needs few graphics, each readable at a glance, all in one style.

## When it triggers

Automatically when you ask for titles, name plates, lower thirds, callouts, captions for key ideas, animated numbers or chapter cards on a cut timeline, or when you have Cyan markers. Ukrainian trigger phrases: «додай титри», «плашка з іменем», «лоуер терд», «виноска», «покажи цифру анімовано», «кінетична типографіка», «заставка розділу», «анімація тексту», «анімований текст». In `edit-episode` it is stage D, step 1.

Explicit call:

```
/davinci-editor:fusion-motion-graphics [timeline] [markers|<kind> <text>]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | timeline to work on | the current timeline |
| `request` | `markers` to build from the Cyan and Blue markers, or one graphic as `<kind> <text>`, e.g. `lower-third Олексій Круглик / автор каналу` | the Cyan and Blue markers |

## Before you start

- A cut timeline with a `Titles` track (`track-layout`). If another title is still visible at a marker, the skill uses `Titles 2`.
- Optional: Cyan and Blue markers on the timeline or its items (below).
- Optional: words on the cut (`<work>/words-<timeline>.json`); with them the skill can suggest graphics from the transcript.
- For a MotionVFX title: the template catalog. If there is none yet, the skill runs `motionvfx-catalog` first.
- The length of every inserted graphic is your *Standard generator duration* preference (Preferences → User → Editing); the API can't trim items. Set it at least as long as your longest title hold.

## Markers it reads

Colors come from the marker color system. Markers whose `customData` is `claude:done:*` are skipped.

| Color | Task | Name | Note | Duration |
|---|---|---|---|---|
| **Cyan** | title on screen | the text, used exactly as written | kind (`lower-third`, `callout`, `kinetic`, `counter`), a MotionVFX template name, or the spot for a callout | how long it stays; a point marker gets reading time |
| **Blue** | chapter start | chapter name | — | — |

Blue markers become chapter cards (kind `kinetic`, the chapter name) only if you want cards; the skill asks once per episode.

How to write a Cyan marker so the skill gets the best brief:

| Name | Note | Result |
|---|---|---|
| `Олексій Круглик` | `плашка, друга лінія: автор каналу` | lower third with a second line (the way the skill's own test case writes it) |
| `Натисни Save` | `виноска на кнопку Save` | callout whose dot sits on the Save button, read off a still |
| `40 %` | `counter` | number counting up in the accent color |
| `Не вимикайте роутер під час оновлення` | (empty) | kinetic phrase, centered low |

Name the spot in the note ("кнопка Save", "праворуч угорі") for a callout. When the note doesn't state the kind, the skill picks `lower-third` for names, `callout` when the note names a spot, `kinetic` otherwise. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## Graphic kinds

| Kind | What | Where |
|---|---|---|
| `lower-third` | name / role plate | lower left, inside the action-safe area |
| `callout` | short label plus an accent dot at a point on screen | label above or below its point, never on it; the dot sits exactly on the point |
| `kinetic` | a key phrase | centered low |
| `counter` | a number counting up | accent color |

Text keeps your wording. Only obvious typography is fixed: Ukrainian apostrophe `ʼ`, quotes «», dash —, no full stop at the end of a title. A suspected typo is a question, never a silent fix.

Besides your markers and request, the skill may **suggest** graphics from the transcript: the speaker's name on first appearance, a number worth a counter ("на 40 відсотків"), a term defined on screen. Suggestions are shown, never placed unasked.

## Motion rules

| Rule | Value |
|---|---|
| Easing | ease-out on the way in, ease-in on the way out |
| In / out | about 0.4 s / 0.3 s for `slide` (other animations below); slide about 3 % of the frame |
| Hold | reading time: 0.5 s + characters / 14 per second; at least 3 s for a name plate, at most 7 s |
| Second line | enters 0.12 s after the first |
| On screen | never more than one graphic at a time, except a callout on a screen recording |
| Consistency | same kind = same position, size and motion all video long |

## Animations

The intro comes from `brand_text_anim`; a marker note can override it for one graphic (`kinetic scramble`, or just `pop` to keep the usual kind).

| Animation | Looks like |
|---|---|
| `slide` | slides about 3 %, scales up and fades in (default) |
| `swipe-down` | drops into place in 4 frames with motion blur |
| `pop` | shrinks from 125 % into place with an S-curve and motion blur |
| `flicker` | blinks on and off, then stays |
| `fade-reveal` | a soft-edged mask rises from below and reveals the text |
| `spin` | each line spins a full turn around Y |
| `scramble` | random letters settle into the phrase |
| `word-grow` | words grow in one after another, left to right |

`scramble` and `word-grow` don't apply to counters.

## Settings

| Key | Default | Effect |
|---|---|---|
| `brand_font` | `Montserrat` | font family of all graphics; must have Cyrillic |
| `brand_font_style` | `Bold` | font style of the main line; second lines are `Regular` unless you ask for the brand style |
| `brand_text_color` | `#FFFFFF` | main text color |
| `brand_accent_color` | `#FFD400` | accent: second lines, callout dots, counters |
| `brand_plate_color` | `#000000` | box behind lower thirds and callouts |
| `brand_plate_opacity` | `0.7` | opacity of that box |
| `brand_text_anim` | `slide` | intro animation of every title (see Animations) |
| `work_dir` | `resolve-work` | where the MotionVFX catalog, specs and stills live |

Any setting can be overridden in the prompt: "accent #00C2FF for this episode", "second lines bold too".

## Files

Under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `words-<timeline>.json` | words on the cut, the source of transcript suggestions |
| `stills/title-<n>.tif` | stills for placement and verification |
| `graphics/<n>.json` | the build spec of each graphic (timing, positions, keyframes) |

The MotionVFX catalog is machine-wide: `<work_dir>/motionvfx-catalog.json`.

## Workflow and approval stops

1. Collects the graphics: Cyan markers, Blue markers (asks once whether you want chapter cards), your request, and transcript suggestions listed separately.
2. **Approval: the plan.** A table `# | TC | kind | text | duration | route (Fusion / MotionVFX name) | track`. Nothing is built before your yes.
3. MotionVFX route: finds the exact template name in the catalog, inserts the title and fills its text fields.
4. Fusion route: backs up the timeline and locks `A-roll`, `B-roll` and `Voice` for the stage.
5. Exports a still at each marker and places the lower third or callout away from the face and from the UI the viewer must see; a callout's point is read off this still.
6. Computes the spec with `motion.py build` (timing, easing, safe-area placement).
7. Inserts each graphic on `Titles`: every other video track is locked for the moment of the insert, then each one is set back to exactly the lock state it had. Checks the item landed on `Titles` at the marker frame.
8. If a hold needs more than the item length, tells you to raise *Standard generator duration* or trim by hand. It never shortens the hold to fit.
9. Verifies every graphic on two stills (fully in, and gone): Cyrillic renders in the brand font, text inside the action-safe area, plate behind the whole text, nothing over the face or the demo, transparent at the end. A counter is checked at the start and end of its count.
10. Recolors clips by role, restores the locks, saves, and marks handled Cyan / Blue markers in `customData`. Reports the final table, graphics that need a longer generator duration, and the stills to look at.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Change your title text beyond typography.
- Place suggested graphics you didn't approve.
- Put graphics on A-roll, B-roll or Screen tracks, or move or trim your clips.
- Copy MotionVFX `.drfx` files anywhere.
- Change the color, name or note of your markers (it writes only the hidden `customData`).

## Place in the workflow

Stage D: **`fusion-motion-graphics`** → `tutorial-zooms` → `subtitles-uk` → `chapters-markers` → `shorts-cutdown` → `thumbnail-frames` → `pre-delivery-qc` → `deliver`

Chapter cards come after `chapters-markers`, from its titles. Next: `sound-design` for whooshes on titles (2–4 frames before they appear).

## Example prompts

**Minimal:**

> Make the titles from my Cyan markers.

**With arguments:**

```
/davinci-editor:fusion-motion-graphics "Router - rough cut" "lower-third Олексій Круглик / автор каналу"
```

**Overriding a setting:**

> Build the graphics from my Cyan markers, but plate opacity 0.85: the background in this lesson is busy.

**Professional brief:**

> Graphics for the timeline "Router - rough cut" from my Cyan markers. The name plate at the start keeps my name exactly as written, second line "автор каналу". The callout at 00:40 must point at the Save button and must not cover the address bar of the router UI. No chapter cards this time. Show me your transcript suggestions, but place none of them. Brand style from settings. At the end give me the table with final timecodes, any graphic that needs a longer generator duration, and the stills to check.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Add some titles" | "Lower third from the Cyan marker at the start, callout on the Save button from the second one; keep my wording, no chapter cards, nothing over the face." |

The strong prompt says which graphics, where they point and what to protect, so the plan table comes back ready to approve.

## What to check afterwards

- Watch every graphic in context: readable at a glance, not over the face or the part of the screen being demonstrated.
- Cyrillic letters in the brand font, no boxes or fallback font.
- Items that need a longer *Standard generator duration*, or a hand trim.
- The tracks you had locked are locked again, the others unlocked.
