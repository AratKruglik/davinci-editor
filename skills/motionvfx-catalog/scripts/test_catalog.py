"""Self-check on a fake .drfx bundle and a loose .setting file."""
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog import scan, search, summary

TITLE = """{
	Tools = ordered() {
		mTutorial_Lower_Third_01 = MacroOperator {
			Inputs = ordered() {
				Input1 = InstanceInput { SourceOp = "BuildInOut", Source = "InCheckbox", Page = "Controls", },
				Label1 = InstanceInput { SourceOp = "CustomLabels", Source = "Label1", Name = "Title Controls", },
				Input2 = InstanceInput {
					SourceOp = "Title",
					Source = "StyledText",
				},
				Input3 = InstanceInput { SourceOp = "Subtitle", Source = "StyledText", Name = "Subtitle", },
				Input4 = InstanceInput { SourceOp = "Title", Source = "Red1Clone", Name = "Color", Default = 1, },
			},
		},
	},
}"""
TRANSITION = "{ Tools = ordered() { Swoosh = GroupOperator { Inputs = ordered() { } } } }"


def main():
    with tempfile.TemporaryDirectory() as d:
        with zipfile.ZipFile(os.path.join(d, "mTutorial.drfx"), "w") as z:
            z.writestr("Edit/Titles/MotionVFX/mTutorial/Lower Thirds/mTutorial Lower Third 01.setting", TITLE)
            z.writestr("__MACOSX/Edit/Titles/MotionVFX/mTutorial/._mTutorial Lower Third 01.setting", "junk")
            z.writestr("Edit/Transitions/MotionVFX/mTutorial/mTutorial Swoosh.setting", TRANSITION)
            z.writestr("Fusion/Other/readme.setting", TITLE)
        os.makedirs(os.path.join(d, "Edit", "Generators", "Mine"))
        with open(os.path.join(d, "Edit", "Generators", "Mine", "Grid BG.setting"), "w") as f:
            f.write(TRANSITION)
        with open(os.path.join(d, "broken.drfx"), "w") as f:
            f.write("not a zip")

        catalog = scan([d, os.path.join(d, "missing")])
        names = sorted(i["name"] for i in catalog["items"])
        assert names == ["Grid BG", "mTutorial Lower Third 01", "mTutorial Swoosh"], names
        title = next(i for i in catalog["items"] if i["category"] == "Titles")
        assert title["vendor"] == "MotionVFX" and title["pack"] == "mTutorial/Lower Thirds", title
        assert title["text_inputs"] == 2 and title["inputs"] == ["Subtitle", "Color"], title
        assert title["macro"] == "mTutorial_Lower_Third_01", title
        assert len(catalog["errors"]) == 1 and summary(catalog)["total"] == 3

        hits = search(catalog, ["lower", "third"], category="Titles", text_inputs=1)
        assert [h["name"] for h in hits] == ["mTutorial Lower Third 01"], hits
        assert search(catalog, ["swoosh"], category="Titles") == []
        assert [h["name"] for h in search(catalog, [], vendor="mine")] == ["Grid BG"]
    print("catalog selftest ok")


if __name__ == "__main__":
    main()
