# davinci-editor

A Claude Code and Claude Desktop (Cowork) plugin that edits in DaVinci Resolve Studio 21+ through Resolve's MCP server: project bootstrap, Apple Log → Rec.709, ColorChecker chart match, natural skin grade, background blur, Ukrainian transcription, text-based rough cut, camera + screen sync with PiP, editing by colored markers, role-based tracks, sound design, AI Voice Isolation and loudness finish for YouTube.

Plan and roadmap: [docs/davinci-plugin-skills.md](docs/davinci-plugin-skills.md) · markers: [docs/marker-color-system.md](docs/marker-color-system.md) · tracks: [docs/track-layout.md](docs/track-layout.md) (in Ukrainian).

Quick install in Claude Code (2.1.275+), once Resolve's MCP server is connected (for Cowork, see [Step 2B](#step-2b-claude-desktop-and-cowork)):

```bash
/plugin install davinci-editor --marketplace AratKruglik/davinci-editor
```

Full instructions below.

## Contents

- [Requirements](#requirements)
- [Step 1. Prepare DaVinci Resolve](#step-1-prepare-davinci-resolve)
- [Step 2A. Claude Code](#step-2a-claude-code)
- [Step 2B. Claude Desktop and Cowork](#step-2b-claude-desktop-and-cowork)
- [Step 3. Plugin settings](#step-3-plugin-settings)
- [Step 4. First run](#step-4-first-run)
- [Skills](#skills)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Requirements

| What | Why |
|---|---|
| **macOS** (tested on Apple Silicon) | paths and the MCP server below are for Mac; Windows is untested |
| **DaVinci Resolve Studio 21.0+** (not the free version) | scripting, AI Voice Isolation, transcription with speaker detection, the built-in `ResolveMCP` server |
| **Claude Code** 2.1.275+ *or* **Claude Desktop** with Cowork access (paid Pro/Max/Team/Enterprise plan) | where the skills run |
| **Python 3.10+** as `python3` | skill scripts (timecode math, transcript analysis, chart match); standard library only, nothing to install |
| Resolve extended language models | Ukrainian transcription (see step 1) |

Check Python with `python3 --version`. If the command is missing, install the Xcode Command Line Tools (`xcode-select --install`) or Python from python.org.

## Step 1. Prepare DaVinci Resolve

1. **Version.** DaVinci Resolve → About DaVinci Resolve must show **Studio 21.0 or later**.
2. **Scripting.** DaVinci Resolve → Preferences → System → General → **External scripting using** = **Local**. Save and restart Resolve. Without it, the MCP server can't control the app.
3. **Ukrainian transcription.** DaVinci Resolve menu → **Extras Download Manager** → download the extended transcription language models. Without them Resolve silently falls back to a built-in model, and Ukrainian speech can come out as English gibberish. The `uk-transcribe` skill checks for this, but install them up front.
4. **Resolve's MCP server** ships inside the app:

   ```
   /Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP
   ```

   Check that the file exists:

   ```bash
   ls "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP"
   ```

   If Resolve is installed outside `/Applications`, use your path in every command below.

## Step 2A. Claude Code

### 2A.1. Connect Resolve's MCP server

Add the server at **user scope** (available in every folder) and **named exactly `DaVinci_Resolve`**: the skills pre-approve the `mcp__DaVinci_Resolve__*` tools, so under another name Claude will ask for permission even on read-only calls.

```bash
claude mcp add --scope user DaVinci_Resolve -- "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP"
```

Check it:

```bash
claude mcp list
```

`DaVinci_Resolve` should be listed as `✓ Connected`. Inside a session, `/mcp` shows the same.

Resolve doesn't need to be running beforehand: the server works without it, and Claude offers to start Resolve itself (the `launch_resolve` tool), asking your permission first.

### 2A.2. Install the plugin

**Option 1: one command** (Claude Code 2.1.275+). In a terminal:

```bash
claude plugin install davinci-editor --marketplace AratKruglik/davinci-editor
```

or the same inside a Claude Code session:

```
/plugin install davinci-editor --marketplace AratKruglik/davinci-editor
```

**Option 2: two steps** (any version with plugin support):

```
/plugin marketplace add AratKruglik/davinci-editor
/plugin install davinci-editor@davinci-editor
```

**Option 3: the menu.** Type `/plugin` → **Marketplaces** tab → **Add marketplace** → `AratKruglik/davinci-editor` → **Discover** tab → `davinci-editor` → **Enter** → choose a scope:

| Scope | When to choose it |
|---|---|
| **User** (default) | you want the plugin in all your projects (recommended) |
| **Project** | everyone working in this folder should get it (written to `.claude/settings.json`) |
| **Local** | only you, only in this folder |

In a session that is already open, run `/reload-plugins` after installing (or restart Claude Code).

> If the repository is private, Claude Code uses your git access to GitHub (SSH key or `gh auth login`).

> A plugin installed from the Claude Code command line stays on this machine and is **not** added to your Claude account, so it won't appear in Cowork. To use the plugin in both, install it once from Claude Desktop (step 2B.1); Claude Code then gets it automatically.

### 2A.3. Verify

1. `/plugin` → **Installed** tab: `davinci-editor` is enabled.
2. Type `/davinci-editor:` and the skill list appears (`edit-episode`, `text-based-cut`, `marker-edit`…).
3. Ask: "Check the connection to DaVinci Resolve and tell me the version." Claude should call `get_resolve_status` and report version 21.x.

### 2A.4. Update or remove

```bash
claude plugin marketplace update davinci-editor   # refresh the marketplace catalog
claude plugin update davinci-editor               # install the new plugin version
claude plugin disable davinci-editor              # turn it off for now
claude plugin uninstall davinci-editor            # remove it
```

The same actions are in the `/plugin` menu.

## Step 2B. Claude Desktop and Cowork

Cowork runs in Claude Desktop: Claude works on a task inside a folder you choose. A plugin added in Desktop is saved to your Claude account and is then available in Cowork, in chat and in Claude Code under the same account (Claude Code picks it up on its next start).

There are two builds of the plugin:

| Build | Resolve's MCP server | Use it for |
|---|---|---|
| **`davinci-editor-cowork`** (zip from Releases) | bundled: the plugin starts `ResolveMCP` itself | **Cowork (recommended)**; also works in Claude Code through account sync |
| `davinci-editor` (marketplace) | you connect it yourself (step 2A.1 / 2B.3) | Claude Code; Cowork only if Desktop bridges your manually configured server |

Cowork officially runs a local MCP server on your Mac only when a plugin bundles it (a connector marked **Runs in each session**). That is why the Cowork build exists. Install **one** build per account, not both, or every skill shows up twice.

### 2B.1. Install the Cowork build (recommended)

1. Open the [latest release](https://github.com/AratKruglik/davinci-editor/releases/latest) and download `davinci-editor-cowork-<version>.zip`. Don't unzip it.
2. In the Claude Desktop sidebar, open **Customize** → **Plugins**.
3. Click **Add** → **Upload plugin** and choose the downloaded zip.
4. Open the installed **davinci-editor-cowork** plugin:
   - the **Skills** tab lists `edit-episode`, `text-based-cut`, `marker-edit` and the rest;
   - the **Connectors** tab shows **DaVinci_Resolve** marked **Runs in each session**. If it shows **Not added** or **Not connected**, add or connect it there.
5. Run the check in [2B.4](#2b4-verify-in-cowork).

Resolve installed outside `/Applications`? The zip points to the standard `ResolveMCP` path. Build your own zip with your path:

```bash
git clone https://github.com/AratKruglik/davinci-editor.git
cd davinci-editor
python3 scripts/build_cowork.py --resolve-mcp "/path/to/DaVinci Resolve.app/Contents/Applications/ResolveMCP"
# → dist/davinci-editor-cowork-<version>.zip
```

**Updating.** An uploaded plugin doesn't update itself. When a new release comes out, open the plugin in **Customize → Plugins**, select **Remove** from its menu, then upload the new zip.

**Using it in Claude Code too.** The Cowork build reaches Claude Code through your account and starts its own `DaVinci_Resolve` server there. If you also added the server by hand (step 2A.1), remove the manual one so Claude doesn't see two copies of every tool: `claude mcp remove DaVinci_Resolve`. Skills are then invoked as `/davinci-editor-cowork:<skill>`.

### 2B.2. Alternative: the marketplace build

Use this if you prefer automatic updates from GitHub and are fine with configuring the MCP server by hand (2B.3).

1. In the Claude Desktop sidebar, open **Customize** → **Plugins**.
2. Click **Add** → **Add marketplace**.
3. Enter `AratKruglik/davinci-editor` (or `https://github.com/AratKruglik/davinci-editor`) and confirm.
   - For a private repository the dialog asks you to **Connect GitHub** or **Install the Claude GitHub App**; give the app access to this repository.
4. Open **Discover**, find **davinci-editor** and click **Add** / **Install**.
5. To get updates automatically, turn on **Sync automatically** on the marketplace page, or click **Check for updates** when you want them.

> On Team and Enterprise plans, adding your own marketplaces may be limited to the organization Owner. In that case ask them to add the repository in organization settings.

### 2B.3. Connect Resolve's MCP server by hand (marketplace build only)

Skip this with the Cowork build: it brings the server itself.

1. Open Claude Desktop → **Settings** (`⌘,`) → **Developer** → **Edit Config**. This opens

   ```
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

2. Add the server under `mcpServers` (create the section if it's missing; keep any servers already there):

   ```json
   {
     "mcpServers": {
       "DaVinci_Resolve": {
         "command": "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP",
         "args": []
       }
     }
   }
   ```

   If the file already has other keys (for example `preferences`), add only the `"DaVinci_Resolve": {...}` block inside the existing `mcpServers`, keeping the commas between entries.

3. Save the file, **quit** Claude Desktop completely (`⌘Q`) and open it again.
4. Check in a regular chat: open the tools menu in the message box → **DaVinci_Resolve** should be listed with `get_resolve_status`, `run_script` and other tools. If the server is missing, **Settings → Developer** shows the startup error.

> Anthropic's documentation doesn't say whether Cowork sees servers from `claude_desktop_config.json`. Users report that Desktop bridges them into Cowork, but this is undocumented. If the check in 2B.4 finds no Resolve tools, switch to the Cowork build (2B.1).

### 2B.4. Verify in Cowork

1. Start Resolve (or let Claude start it).
2. Open **Cowork**, create a new task and **choose a working folder**, for example the episode folder where transcripts and reports will go (not the footage folder).
3. Ask: "Check the connection to DaVinci Resolve and tell me the version."
   - A reply with version 21.x means everything works.
   - If Claude says there are no Resolve tools: with the Cowork build, check the plugin's **Connectors** tab (2B.1, step 4); with the marketplace build, switch to the Cowork build.
4. Type `/davinci-editor-cowork:` (or `/davinci-editor:` for the marketplace build) and the skill list should appear.

**Cowork specifics:**

- Cowork only sees the chosen folder. Keep the plugin's work folder (`work_dir`) inside it, so transcripts, stills and reports written by Resolve are also reachable by the skill scripts.
- Cowork may not ask for the plugin settings (step 3). The skills then use the defaults and say which ones they used; to change one, just say it in the task ("transcription language: en", "footage bin: Footage/Cam A").
- The plugin never writes to the media folder or changes source timelines, but Cowork still asks permission for actions that change the Resolve project. Read what you approve.

## Step 3. Plugin settings

Claude Code asks for the settings when the plugin is enabled. To change them later: `/plugin` → **Installed** → `davinci-editor` → **Configure**, or in a terminal:

```bash
claude plugin configure davinci-editor        # show current values and unset options
echo '{"transcription_language": "uk", "pause_threshold_ms": "600"}' \
  | claude plugin configure davinci-editor --values-stdin   # change only these values
```

The defaults suit Ukrainian-language YouTube tutorials; change only what differs for you.

| Key | Default | Meaning |
|---|---|---|
| `footage_bin` | `01_Footage/A-Roll` | Media Pool bin with the main footage |
| `templates_dir` | — | folder with DRX grade templates (the base node tree); if empty, Claude asks on the first color skill |
| `work_dir` | `resolve-work` | where transcripts, cut lists, stills and reports go (relative to the working folder) |
| `output_gamma` | `Gamma 2.4` | Rec.709 output gamma (`Gamma 2.2` only if you grade for computer screens) |
| `transcription_language` | `uk` | Resolve transcription language |
| `speaker_detection` | `false` | detect speakers (interviews, podcasts) |
| `filler_words` | `е,ее,еее,ем,…` | hard filler sounds, always proposed for cutting |
| `soft_filler_words` | `ну,типу,коротше,…` | soft fillers, only flagged; you decide |
| `pause_threshold_ms` | `700` | pauses longer than this are proposed for tightening |
| `cut_handle_ms` | `120` | silence kept on each side of a cut so words aren't clipped |
| `voice_isolation_amount` | `60` | AI Voice Isolation strength, 0–100 |
| `marker_colors` | `Red=cut,Green=keep,Yellow=doubt,Sand=chart,…` | what each marker color means |
| `video_tracks` | `Backgrounds:Tan,A-roll:Blue,B-roll:Teal,Effects:Orange,Titles:Pink` | video tracks bottom to top and the clip color of each role |
| `audio_tracks` | `Voice:Green,SFX:Yellow,Music:Purple` | audio tracks |
| `protected_tracks` | `A-roll,Voice` | tracks never deleted, even when empty |
| `track_template` | — | `.drt` template of an empty timeline with track names and header colors |
| `timeline_format` | `horizontal` | new projects: `horizontal` or `vertical` |
| `timeline_resolution` | `3840x2160` | new projects, horizontal size (vertical swaps it) |
| `timeline_fps` | `25` | new projects' frame rate |
| `skin_strength` | `0.6` | share of the skin hue error `natural-skin-grade` corrects |
| `skin_max_saturation` | `0.35` | skin saturation cap (chroma/luma) |
| `depth_strength` | `medium` | background blur: `medium` = template node; `light`/`strong` = group DRX |
| `pip_layout` | `corner-br` | PiP corner for the camera |
| `pip_size` | `0.28` | PiP width as a share of the frame |
| `sfx_library_dir` | — | your sound effects folder (indexed by `sound-design`) |
| `music_library_dir` | — | your licensed music folder |
| `music_bed_lufs` | `-30` | music under speech |
| `music_solo_lufs` | `-20` | music without speech |
| `sfx_peak_db` | `-12` | SFX peak level |
| `loudness_target_lufs` | `-14` | final mix loudness (YouTube) |
| `true_peak_db` | `-1` | final mix peak ceiling |
| `fairlight_preset` | — | optional Fairlight preset (bus limiter, music ducking) |

## Step 4. First run

1. **Node template (once).** The Resolve API can't create nodes, so on its first run `log-to-rec709` asks you to build 6 serial nodes on one clip, labeled `CHART` → `CST` → `PRIMARY` → `SKIN` → `DEPTH` → `LOOK`: set up the CST, a skin-hue qualifier on `SKIN`, AI CineFocus (or Depth Map + Lens Blur) on `DEPTH` and disable `DEPTH`, then say "done". It saves that as a DRX template in `templates_dir` and applies it by itself from then on. Apple Log and Apple Log 2 get separate templates. A stage-1 template without `SKIN`/`DEPTH` is upgraded in place, keeping the chart correction.
2. **Markers.** While reviewing footage, place markers (`M` in Resolve) in the colors from `marker_colors`: Red = cut, Green = keep / best take, Yellow = doubt, Sand = ColorChecker frame, Purple = camera / screen / PiP, Fuchsia = B-roll, Cocoa = transition, Lavender = SFX, Sky = music, Rose = audio problem. Details: [docs/marker-color-system.md](docs/marker-color-system.md).
3. **Sound library (once).** Set `sfx_library_dir` and `music_library_dir`; `sound-design` indexes them and asks once per music source whether it's cleared for your channel (YouTube Content ID).
4. **Full workflow:** `/davinci-editor:edit-episode Episode name` runs project and color before the cut → transcript, tracks, rough cut, PiP → sound. After each step Claude stops and waits for your go-ahead; progress is kept in `episode.md`, so `/davinci-editor:edit-episode` in a new session resumes where you stopped.
5. Or single steps in plain language: "convert A-Roll from Apple Log to 709", "make a rough cut of these clips", "clean up the voice, the air conditioner hums".

What Claude never does without confirmation: delete clips, timelines, grades, LUTs or markers (a hook in every editing skill turns any delete/reset script into a permission prompt); change the source timeline (the rough cut goes to a new one); change project-wide color management; touch your markers (it only writes the hidden `customData` field and uses Cream for its own markers).

## Skills

| Skill | How to invoke | What it does |
|---|---|---|
| `resolve-core` | automatic (hidden) | shared rules: safe scripting, backups, timecodes, tracks by role, markers, node labels, remote grade versions, delete guard hook |
| `project-bootstrap` | auto or `/davinci-editor:project-bootstrap [name] [folder] [horizontal\|vertical]` | new project with settings, bins and import; or sorts an open project's media pool |
| `log-to-rec709` | auto or `/davinci-editor:log-to-rec709 [bin] [gamma]` | Apple Log / Apple Log 2 → Rec.709 via a CST node from a DRX template, as a remote version |
| `chart-match` | auto or `/davinci-editor:chart-match [scene]` | ColorChecker 24 match in linear light → DCTL on the `CHART` node, ΔE00 report |
| `natural-skin-grade` | auto or `/davinci-editor:natural-skin-grade [scene] [strength]` | measured neutral balance on `PRIMARY` and skin toward the skin tone line on `SKIN`, verified on a still |
| `depth-background-blur` | auto or `/davinci-editor:depth-background-blur [scene] [light\|medium\|strong\|off]` | background blur with AI CineFocus or Depth Map, per clip or per scene |
| `motionvfx-catalog` | auto or `/davinci-editor:motionvfx-catalog [scan\|search words]` | catalog of installed MotionVFX / Fusion templates with exact names and text fields (runs as a forked helper) |
| `voice-isolation` | auto or `/davinci-editor:voice-isolation [track\|selected] [amount]` | AI Voice Isolation on the Voice track or clips |
| `uk-transcribe` | auto or `/davinci-editor:uk-transcribe [bin]` | Resolve transcription with a language check, exports JSON/SRT/TXT |
| `text-based-cut` | auto or `/davinci-editor:text-based-cut [bin] [gentle\|normal\|tight]` | cut list from transcript and markers → approval → new timeline on A-roll + Voice |
| `dual-video-sync-pip` | auto or `/davinci-editor:dual-video-sync-pip [timeline] [corner] [size]` | camera + screen recording synced by sound, Screen and PiP tracks switched by Purple markers |
| `marker-edit` | auto or `/davinci-editor:marker-edit [stage] [timeline]` | acts on your colored markers: plan → approval → the matching skills; B-roll inserts and transitions itself |
| `track-layout` | auto or `/davinci-editor:track-layout [setup\|add\|recolor\|lock\|cleanup]` | role-based tracks, clip colors, cleanup of empty tracks |
| `sound-design` | auto or `/davinci-editor:sound-design [timeline] [subtle\|normal\|rich]` | cue sheet from transcript and markers → approval → SFX, music and ambience from your library with levels and fades |
| `audio-finish` | auto or `/davinci-editor:audio-finish [timeline] [LUFS]` | dialogue leveling, Rose fixes, measured loudness to -14 LUFS without clipping |
| `edit-episode` | only `/davinci-editor:edit-episode [name] [stage]` | the whole workflow with approval stops, resumable |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Every skill appears twice | both builds are installed; keep one (2B) |
| `claude mcp list` shows `DaVinci_Resolve` as **Failed** | check the `ResolveMCP` path (step 1.4); if Resolve isn't in `/Applications`, run `claude mcp remove DaVinci_Resolve` and add it again with the right path |
| Claude says Resolve isn't running or doesn't respond | start Resolve; check **External scripting using = Local** (step 1.2); close modal dialogs in Resolve, they block scripts |
| Claude asks permission for every Resolve call | the server is connected under another name; reconnect it as `DaVinci_Resolve` (step 2A.1 / 2B.3) |
| Skills don't show up under `/` | in Claude Code run `/reload-plugins`; in Desktop check the plugin isn't disabled in **Customize → Plugins** |
| Transcript is English gibberish | extended models aren't installed (step 1.3) or Project Settings has another transcription language |
| Cowork has no Resolve tools | install the Cowork build (2B.1) and check its **Connectors** tab |
| `python3: command not found` | `xcode-select --install` or Python from python.org |
| `chart-match` reports "unsupported TIFF" | Resolve exported a compressed TIFF; tell Claude and it will try another still format |

## Development

```bash
python3 skills/resolve-core/scripts/tc.py selftest
python3 skills/chart-match/scripts/test_chart_match.py
python3 skills/text-based-cut/scripts/test_cut_candidates.py
python3 skills/resolve-core/scripts/guard.py selftest
python3 skills/natural-skin-grade/scripts/test_skin_grade.py
python3 skills/motionvfx-catalog/scripts/test_catalog.py
python3 skills/dual-video-sync-pip/scripts/pip_plan.py selftest
python3 skills/sound-design/scripts/test_sound_library.py
python3 skills/audio-finish/scripts/loudness.py selftest
claude plugin validate .
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold   # eval cases in skills/*/evals (real, billed model runs)
```

Skill eval cases live in `skills/<skill>/evals/`; the offline fixtures don't need a running Resolve.

### Releasing

The Cowork zip is built from the same `skills/` by `scripts/build_cowork.py`: it renames the plugin to `davinci-editor-cowork`, bundles `.mcp.json` with Resolve's server, rewrites the skills' pre-approved tool names to the plugin-scoped ones (`mcp__plugin_davinci-editor-cowork_DaVinci_Resolve__*`) and leaves out the eval fixtures.

1. Bump `version` in `.claude-plugin/plugin.json`.
2. Commit, then tag and push: `git tag v0.3.0 && git push origin v0.3.0` (the tag must match the version).
3. The `release` workflow runs the self-tests, builds `davinci-editor-cowork-<version>.zip` and publishes it on the GitHub release.

Local build: `python3 scripts/build_cowork.py` → `dist/`.
