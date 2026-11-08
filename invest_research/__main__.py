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
    research = commands.add_parser("research", help="指数/行业营收、市值与PE研究")
    research.add_argument("--input", required=True)
    research.add_argument("--as-of", required=True, type=date.fromisoformat)
    research.add_argument("--out", required=True)
    research.add_argument("--audit", help="明确附带同日的collection-audit.json，包含逐股依赖与缺口")
    research_demo = commands.add_parser("research-demo", help="明确合成的研究交互样板")
    research_demo.add_argument("--out", default="runs/research-demo")
    collect = commands.add_parser("collect-csi300", help="只读采集中证历史PE；可选2026Q3固定成分财报快照")
    collect.add_argument("--as-of", required=True, type=date.fromisoformat)
    collect.add_argument("--start", default=date(2018,11,9), type=date.fromisoformat)
    collect.add_argument("--cache", default="data/raw/csi300")
    collect.add_argument("--out", default="data/research-csi300.csv")
    collect.add_argument("--with-finance", action="store_true")
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps(inventory(args.skill_dir),ensure_ascii=False,indent=2))
        return
    try:
        if args.command == "collect-csi300":
            from .collect import collect_csi300
            result = collect_csi300(args.as_of,args.start,args.cache,args.out,args.with_finance)
        elif args.command in ("research", "research-demo"):
            from .research import run_research
            if args.command == "research-demo":
                result = run_research(Path(__file__).parent/"ui"/"research-demo.csv",date(2026,11,5),args.out,demo=True)
            else:
                result = run_research(args.input,args.as_of,args.out,audit_path=args.audit)
        elif args.command == "demo":
            root = Path(__file__).resolve().parents[1]
            result = run(root/"examples"/"dashboard-demo.csv", date(2026,11,5),args.out,demo=True)
        else:
            result = run(args.input,args.as_of,args.out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (DataError,OSError,ValueError,KeyError) as exc:
        parser.exit(2, str(exc)+"\n")


if __name__ == "__main__":
    main()

