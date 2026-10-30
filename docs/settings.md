# Plugin settings

[← README](../README.md) · [Install](install.md)

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
| `split_j_lead_frames` / `split_l_tail_frames` | `12` / `12` | J-cut lead and L-cut tail, frames |
| `split_max_frames` | `50` | largest J/L shift, frames |
| `split_fade_frames` | `4` | audio fade on a moved split-edit boundary, frames |
| `split_max_in_row` | `3` | most split edits in a row without a plain cut |
| `sfx_library_dir` | — | your sound effects folder (indexed by `sound-design`) |
| `music_library_dir` | — | your licensed music folder |
| `music_bed_lufs` | `-30` | music under speech |
| `music_solo_lufs` | `-20` | music without speech |
| `sfx_peak_db` | `-12` | SFX peak level |
| `loudness_target_lufs` | `-14` | final mix loudness (YouTube) |
| `true_peak_db` | `-1` | final mix peak ceiling |
| `fairlight_preset` | — | optional Fairlight preset (bus limiter, music ducking) |
| `brand_font` / `brand_font_style` | `Montserrat` / `Bold` | font of titles and Shorts captions (needs Cyrillic) |
| `brand_text_color` / `brand_accent_color` | `#FFFFFF` / `#FFD400` | title text and accent (second line, counters, spoken word in captions) |
| `brand_plate_color` / `brand_plate_opacity` | `#000000` / `0.7` | box behind lower thirds and callouts |
| `brand_text_anim` | `slide` | title intro: `slide`, `swipe-down`, `pop`, `flicker`, `fade-reveal`, `spin`, `scramble`, `word-grow` |
| `zoom_default_scale` / `zoom_max_scale` | `1.6` / `2.5` | screen zoom strength and its limit |
| `zoom_ease_s` | `0.5` | zoom move duration, seconds |
| `punch_in_scale` | `1.12` | punch-in on alternate A-roll segments (hides jump cuts) |
| `subtitle_max_chars` / `subtitle_max_cps` | `42` / `17` | subtitle line length and reading speed |
| `shorts_min_s` / `shorts_max_s` | `30` / `60` | Shorts length |
| `shorts_resolution` | `1080x1920` | Shorts frame |
| `shorts_caption_words` | `3` | words per animated Shorts caption |
| `render_dir` | — | render folder (empty = `<work_dir>/<project>/renders`) |
| `render_preset_youtube` / `render_preset_shorts` | — | your own Resolve render presets; empty = H.265 settings built by `deliver` |
| `youtube_bitrate_mbps` / `shorts_bitrate_mbps` | `60` / `20` | render bitrates |
