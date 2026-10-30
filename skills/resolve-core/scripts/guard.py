"""PreToolUse hook for Resolve run_script calls: escalates destructive API calls to the user.

Reads the hook event JSON on stdin. If the script deletes or resets the user's work, prints a PreToolUse
"ask" decision so Claude Code shows a permission prompt with the reason, even when the tool is pre-approved.

python3 guard.py            (hook mode, stdin = event JSON)
python3 guard.py selftest
"""
import json
import re
import sys

# Any reference counts, not only a call: `f = mp.DeleteTimelines; f(x)` must still prompt.
DESTRUCTIVE = re.compile(r"\b(Delete\w*|Clear\w*|Reset\w*|ReplaceClip|UnlinkProxyMedia)\b")
# Names built at run time can't be checked statically, so they always prompt.
DYNAMIC = re.compile(r"\b(getattr|setattr|delattr|eval|exec|compile|__getattribute__|__dict__)\b")
# Claude's own scratch work, created in the same session: never worth a prompt. Only the exact literal call is exempt.
SAFE = [
    re.compile(r"\.DeleteMarkersByColor\s*\(\s*['\"]Cream['\"]\s*\)"),
    re.compile(r"\.DeleteVersionByName\s*\(\s*['\"]claude-measure['\"]\s*,\s*0\s*\)"),
]


def findings(script):
    for safe in SAFE:
        script = safe.sub("", script)
    hits = {m.group(1) for m in DESTRUCTIVE.finditer(script)}
    hits |= {f"{m.group(1)} (dynamic call)" for m in DYNAMIC.finditer(script)}
    return sorted(hits)


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
    for bypass in ['tl.DeleteMarkersByColor("Cream" if False else "Red")', 'getattr(mp, "Delete" + "Timelines")([tl])',
                   "f = mp.DeleteTimelines; f([tl])", "project.DeleteAllRenderJobs()", "gal.DeleteGalleryStillAlbum(a)",
                   "item.DeleteVersionByName('claude-measure', 1)"]:
        assert decide({"tool_input": {"script": bypass}}), bypass
    print("guard selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
    else:
        result = decide(json.load(sys.stdin))
        if result:
            print(json.dumps(result))
