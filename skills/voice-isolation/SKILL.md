---
name: voice-isolation
description: Turns on DaVinci Resolve 21+ AI Voice Isolation for dialogue on chosen timeline clips or whole audio tracks with a set strength (0-100), verifies the state, and keeps music, SFX and room-tone tracks untouched.
when_to_use: User wants to clean dialogue from noise, hum, room echo or background sounds, or asks for voice isolation / noise removal on voice. Also for Rose markers about noise on the voice. Triggers - "прибери шум", "почисти голос", "voice isolation", "ізоляція голосу", "шумодав на голос".
argument-hint: "[track number | selected] [amount 0-100]"
arguments: [target, amount]
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

# AI Voice Isolation

Follow `resolve-core` first. Target: `$target` (default: the Voice track, plus Voice 2 if present). Strength: `$amount` (default `${user_config.voice_isolation_amount}`).

## Choosing the strength

| Material | Amount |
|---|---|
| Quiet room, lav or close mic | 30–50 |
| Typical home studio, fan or street noise | 50–70 |
| Loud background, reverberant room | 70–90 |
| 100 | only for rescue; voice gets thin and "underwater" |

Too much isolation removes breaths and the room, and the cut sounds unnatural. Start moderate; raise only if the user hears residual noise.

## Steps

1. Find the voice tracks by role with `track_index(tl, "audio", "Voice")` (and `"Voice 2"`) from `track-layout`. No track named Voice → show the audio tracks (index, name, items) and ask which carry dialogue, or offer to run `track-layout`. Never apply isolation to Music, SFX or Ambience: it would eat the music.
2. Track level is the default: it is one switch, survives re-cuts and new clips on the track. Use clip level only for specific problem spots — clips the user selected (`tl.GetSelectedClips()`) or under Rose markers (audio problem) on the Voice track; read the note for what the problem is.
3. Apply:
   - track: `tl.SetVoiceIsolationState(i, {"isEnabled": True, "amount": A})`, verify `tl.GetVoiceIsolationState(i)`;
   - clip: `item.SetVoiceIsolationState({"isEnabled": True, "amount": A})`, verify `item.GetVoiceIsolationState()`.
   Don't stack both on the same audio. Record the previous state of everything you change so it can be restored; it's a reversible toggle, so no timeline copy is needed (save the project first).
4. Ask the user to listen to 10–20 s of the noisiest part (Resolve is the only place to hear it). Offer ±15 steps.
5. Mark handled Rose markers `claude:done:voice-isolation:<date>` in `customData` if they're solved by isolation (hum, hiss, room noise); leave clipping/distortion ones for `audio-finish`.
6. Save the project. Report: track/clip → state → amount (re-read values).

## Notes

- Voice isolation is real-time and non-destructive; turning it off restores the original.
- Heavy isolation before `audio-finish` loudness normalization can raise the noise floor of what's left; normalize after isolation, not before.
