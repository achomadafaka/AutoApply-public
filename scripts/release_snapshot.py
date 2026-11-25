"""Export reviewed source candidates without including the checkout's Git history."""
import argparse
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIRS = {".git", ".logs", ".review-handoff", ".venv", ".svelte-kit",
                "artifacts", "data", "node_modules", "output", "__pycache__"}
PRIVATE_SUFFIXES = {".pdf", ".docx", ".db", ".sqlite", ".log", ".pem", ".key", ".p12"}
TOKEN = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|"
                   rb"AKIA[A-Z0-9]{16}|sk-(?:proj-)?[A-Za-z0-9_-]{24,}|"
                   rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="New .zip destination outside this checkout")
    args = parser.parse_args()
    archive = args.archive.resolve()
    if archive.is_relative_to(ROOT) or archive.suffix != ".zip" or archive.exists():
        parser.error("Choose a new .zip path outside this checkout.")
    raw = subprocess.check_output(["git", "ls-files", "-z", "--cached",
                                   "--others", "--exclude-standard"], cwd=ROOT)
    files = sorted({Path(item.decode()) for item in raw.split(b"\0") if item})
    included = []
    rejected = []
    for rel in files:
        full = ROOT / rel
        if not full.exists() and not full.is_symlink():
            continue  # tracked deletion in working tree
        private = (bool(set(rel.parts) & PRIVATE_DIRS) or rel.suffix.lower() in PRIVATE_SUFFIXES
                   or (rel.name.startswith(".env") and rel.name != ".env.example"))
        if private or full.is_symlink() or not full.is_file() or not full.resolve().is_relative_to(ROOT):
            rejected.append(str(rel))
            continue
        content = full.read_bytes()
        if b"\0" in content or TOKEN.search(content) or len(content) > 2_000_000:
            rejected.append(str(rel))
        else:
            included.append((rel, full))
    if rejected:
        parser.error("Review these files before exporting: " + ", ".join(rejected))
    if not included:
        parser.error("No source files found.")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as out:
        for rel, path in included:
            out.write(path, Path("AutoApply") / rel)
    print(f"Exported {len(included)} source files; manual privacy and licensing review is still required.")


if __name__ == "__main__":
    main()
