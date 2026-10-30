"""PreToolUse hook for Resolve run_script calls: escalates destructive API calls to the user.

Reads the hook event JSON on stdin. If the script deletes or resets the user's work, prints a PreToolUse
"ask" decision so Claude Code shows a permission prompt with the reason, even when the tool is pre-approved.

python3 guard.py            (hook mode, stdin = event JSON)
python3 guard.py selftest
"""
import json
import re
import sys

DESTRUCTIVE = re.compile(
    r"\b(DeleteClips|DeleteTimelines|DeleteTrack|DeleteFolders|DeleteProject|DeleteMedia|DeleteStills|DeleteClipMattes"
    r"|DeleteMarkerAtFrame|DeleteMarkersByColor|DeleteMarkerByCustomData|ResetAllGrades|ClearTranscription"
    r"|ClearAudioClassification|DeleteVersionByName|DeleteTakeByIndex|UnlinkProxyMedia|ReplaceClip)\s*\(")
# Claude's own scratch work, created in the same session: never worth a prompt.
SAFE = [
    re.compile(r"DeleteMarkersByColor\s*\(\s*['\"]Cream['\"]"),
    re.compile(r"DeleteVersionByName\s*\(\s*['\"]claude-measure['\"]"),
]


def findings(script):
    for safe in SAFE:
        script = safe.sub("", script)
    return sorted({m.group(1) for m in DESTRUCTIVE.finditer(script)})


def decide(event):
    tool_input = event.get("tool_input") or {}
    script = "\n".join(v for v in tool_input.values() if isinstance(v, str))
    hits = findings(script)
    if not hits:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": "davinci-editor: this Resolve script calls " + ", ".join(hits)
        + ". It removes or resets work in the project. Approve only if you asked for exactly this.",
    }}


def selftest():
    assert decide({"tool_input": {"script": "tl.GetItemListInTrack('video', 1)"}}) is None
    assert decide({"tool_input": {"script": "tl.DeleteMarkersByColor('Cream')"}}) is None
    assert decide({"tool_input": {"script": "item.DeleteVersionByName('claude-measure', 0)"}}) is None
    out = decide({"tool_input": {"script": "mp.DeleteTimelines([tl])\ntl.DeleteMarkersByColor('Red')"}})
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "DeleteTimelines" in reason and "DeleteMarkersByColor" in reason, reason
    assert decide({"tool_input": {"script": "g.ResetAllGrades ()"}})
    print("guard selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
    else:
        result = decide(json.load(sys.stdin))
        if result:
            print(json.dumps(result))
