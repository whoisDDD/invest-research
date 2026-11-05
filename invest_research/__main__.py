import argparse
from datetime import date
from pathlib import Path
import importlib.util
import json
import shutil
from .core import DataError
from .pipeline import run


def main():
    parser = argparse.ArgumentParser(description="Source-backed investment research")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Local capability inventory; no account/network verification")
    demo = commands.add_parser("demo")
    demo.add_argument("--out", default="runs/demo")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--input", required=True)
    analyze.add_argument("--as-of", required=True, type=date.fromisoformat)
    analyze.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps({"python_required":"3.10+", "westock_cli_installed":bool(shutil.which("westock")),
                          "mcp_sdk_installed":importlib.util.find_spec("mcp") is not None,
                          "supplier_access":"not_tested", "network":"not_tested",
                          "note":"Use official vendor/client authorization and a real query before marking connected."},indent=2))
        return
    try:
        if args.command == "demo":
            root = Path(__file__).resolve().parents[1]
            result = run(root/"examples"/"demo.csv", date(2026,11,5),args.out,demo=True)
        else:
            result = run(args.input,args.as_of,args.out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (DataError,OSError) as exc:
        parser.exit(2, str(exc)+"\n")


if __name__ == "__main__":
    main()

