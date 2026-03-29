"""Import a tab-separated people directory into data/memory/.

Usage:
  python scripts/import_people.py path/to/people.tsv

Expected TSV columns (first row = header):
  First Name, Last Name, Full Name, Street Address, Town, State,
  Zip Code, Mobile #, Title, Team, Email, Group

Group values:
  Active      → data/memory/people/
  Contractor  → data/memory/people/
  Board       → data/memory/people/
  Exit        → data/memory/exits/

If your TSV has no Group column, all rows go to people/.
"""

import csv
import re
import sys
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent / "data" / "memory"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def make_path(dest_dir: Path, slug: str) -> Path:
    path = dest_dir / f"{slug}.md"
    n = 2
    while path.exists():
        path = dest_dir / f"{slug}-{n}.md"
        n += 1
    return path


def run(tsv_path: str) -> None:
    people_dir = MEMORY_DIR / "people"
    exits_dir = MEMORY_DIR / "exits"
    people_dir.mkdir(parents=True, exist_ok=True)
    exits_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0

    with open(tsv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            full = row.get("Full Name", "").strip()
            if not full:
                skipped += 1
                continue

            group = row.get("Group", "Active").strip()
            dest = exits_dir if group.lower() == "exit" else people_dir

            slug = slugify(full)
            path = make_path(dest, slug)

            location = ", ".join(
                part for part in [
                    row.get("Town", "").strip(),
                    row.get("State", "").strip(),
                ]
                if part
            )

            lines = [
                f"# {full}",
                "",
                f"**Title:** {row.get('Title', '').strip()}",
                f"**Team:** {row.get('Team', '').strip()}",
                f"**Email:** {row.get('Email', '').strip()}",
                f"**Mobile:** {row.get('Mobile #', '').strip()}",
                f"**Location:** {location}",
                f"**Group:** {group}",
                "",
            ]
            path.write_text("\n".join(lines), encoding="utf-8")
            created += 1
            print(f"  {path.relative_to(MEMORY_DIR.parent.parent)}")

    print(f"\nDone: {created} files created, {skipped} skipped")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_people.py path/to/people.tsv")
        sys.exit(1)
    run(sys.argv[1])
