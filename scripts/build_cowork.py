"""Build the Cowork variant of the plugin as an uploadable zip.

The Cowork variant ships the same skills but bundles Resolve's own MCP server (.mcp.json), because Cowork
officially runs local MCP servers only when a plugin brings them. Tool names change with that, so the
skills' and agents' tool names are rewritten to the plugin-scoped names.

python3 scripts/build_cowork.py [--resolve-mcp PATH] [--out dist]
"""
import argparse
import json
import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "davinci-editor-cowork"
SERVER = "DaVinci_Resolve"
DEFAULT_MCP = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP"
TOOL_PREFIX_FROM = f"mcp__{SERVER}__"
TOOL_PREFIX_TO = f"mcp__plugin_{NAME}_{SERVER}__"


def build(resolve_mcp, out):
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    version = manifest["version"]
    stage = os.path.join(out, NAME)
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "skills"), os.path.join(stage, "skills"),
                    ignore=shutil.ignore_patterns("evals", "__pycache__", "*.pyc"))
    shutil.copytree(os.path.join(ROOT, "agents"), os.path.join(stage, "agents"))
    shutil.copy(os.path.join(ROOT, "README.md"), stage)
    shutil.copy(os.path.join(ROOT, "LICENSE"), stage)

    for top in ("skills", "agents"):
        for folder, _, files in os.walk(os.path.join(stage, top)):
            for name in files:
                if name.endswith(".md"):
                    path = os.path.join(folder, name)
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text.replace(TOOL_PREFIX_FROM, TOOL_PREFIX_TO))

    manifest |= {"name": NAME, "displayName": "DaVinci Editor (Cowork)",
                 "description": manifest["description"] + " Cowork build: bundles Resolve's MCP server."}
    os.makedirs(os.path.join(stage, ".claude-plugin"))
    with open(os.path.join(stage, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    with open(os.path.join(stage, ".mcp.json"), "w", encoding="utf-8") as f:
        json.dump({"mcpServers": {SERVER: {"command": resolve_mcp, "args": []}}}, f, indent=2)

    archive = os.path.join(out, f"{NAME}-{version}.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(stage):
            for name in files:
                path = os.path.join(folder, name)
                z.write(path, os.path.relpath(path, stage))
    check(archive)
    return archive


def check(archive):
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        assert names.count(".claude-plugin/plugin.json") == 1 and ".mcp.json" in names, names[:5]
        assert not any("/evals/" in n for n in names), "eval fixtures leaked into the archive"
        skills = [n for n in names if n.endswith("SKILL.md")]
        agents = [n for n in names if n.startswith("agents/") and n.endswith(".md")]
        assert skills, "no skills in the archive"
        assert "agents/edit-judge.md" in agents, "edit-judge agent missing from the archive"
        assert TOOL_PREFIX_TO in z.read("agents/edit-judge.md").decode("utf-8"), "edit-judge agent tools not rewritten"
        for n in skills + agents:
            text = z.read(n).decode("utf-8")
            assert TOOL_PREFIX_FROM not in text, f"{n}: tool names not rewritten"
        manifest = json.loads(z.read(".claude-plugin/plugin.json"))
        assert manifest["name"] == NAME
        assert len(manifest["description"]) <= 500, "Cowork rejects descriptions over 500 characters"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--resolve-mcp", default=DEFAULT_MCP, help="path to ResolveMCP if Resolve is not in /Applications")
    p.add_argument("--out", default=os.path.join(ROOT, "dist"))
    args = p.parse_args()
    print(build(args.resolve_mcp, args.out))
