"""Every core module has a guide: H1 file name, a one-line summary, then exactly five bullets."""

from pathlib import Path

PACKAGES = ("data", "evaluation", "llm", "routing", "agents/common", "agents/telemetry",
            "agents/service", "agents/production", "agents/quality", "agents/knowledge")
SOURCE_ROOT = Path(__file__).parents[1] / "src" / "contoso_aero"
NOT_CORE = {"__init__", "__main__"}


def test_given_core_modules_when_guides_are_read_then_each_has_five_bullets() -> None:
    for package_name in PACKAGES:
        package_root = SOURCE_ROOT / package_name
        modules = {path.stem for path in package_root.glob("*.py")} - NOT_CORE
        guide_root = package_root / "guide"
        assert {path.stem for path in guide_root.glob("*.md")} == modules, package_name

        for module_name in modules:
            lines = (guide_root / f"{module_name}.md").read_text().splitlines()
            assert lines[0] == f"# {module_name}.py"
            assert lines[1] == ""
            assert lines[2].endswith(".")
            assert lines[3] == ""
            assert len(lines[4:]) == 5
            assert all(line.startswith("* ") for line in lines[4:])
