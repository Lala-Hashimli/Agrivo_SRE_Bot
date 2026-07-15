from pathlib import Path


def test_source_and_locale_files_have_no_mojibake(project_root: Path) -> None:
    bad_markers = ("Ã", "Â", "â€", "ðŸ")
    files = [
        *project_root.glob("app/**/*.py"),
        *project_root.glob("app/**/*.json"),
    ]
    offenders = [
        str(path.relative_to(project_root))
        for path in files
        if any(marker in path.read_text(encoding="utf-8") for marker in bad_markers)
    ]
    assert offenders == []
