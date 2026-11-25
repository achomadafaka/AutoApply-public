"""Optional CLI for installing example records in an empty database."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from app.migrations import init_db  # noqa: E402
from app.settings import get_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(get_settings().database_path))
    parser.add_argument("--seed", type=Path, help="Optional example SQL (empty databases only)")
    args = parser.parse_args()
    init_db(args.db, seed=args.seed)
    print(f"Initialized DB at {args.db}")


if __name__ == "__main__":
    main()
