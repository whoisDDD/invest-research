import argparse
from datetime import date
from pathlib import Path
import json
from .core import DataError
from .pipeline import run
from .doctor import inventory


def main():
    parser = argparse.ArgumentParser(description="Source-backed investment research")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Read-only discovery; no account/network verification")
    doctor.add_argument("--skill-dir", action="append", default=[], help="Additional installed skill directory or SKILL.md")
    demo = commands.add_parser("demo")
    demo.add_argument("--out", default="runs/demo")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--input", required=True)
    analyze.add_argument("--as-of", required=True, type=date.fromisoformat)
    analyze.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps(inventory(args.skill_dir),ensure_ascii=False,indent=2))
        return
    try:
        if args.command == "demo":
            root = Path(__file__).resolve().parents[1]
            result = run(root/"examples"/"dashboard-demo.csv", date(2026,11,5),args.out,demo=True)
        else:
            result = run(args.input,args.as_of,args.out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (DataError,OSError) as exc:
        parser.exit(2, str(exc)+"\n")


if __name__ == "__main__":
    main()

