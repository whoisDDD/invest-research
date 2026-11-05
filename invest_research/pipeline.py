"""CSV -> deterministic metrics -> offline HTML and reproducible review pack."""
import csv
import hashlib
import json
from datetime import datetime, timezone, date
from pathlib import Path
import zipfile
from .core import load_facts, calculate, as_of_facts
from .report import make_report, verification_summary
from .dashboard import make_dashboard
from . import __version__


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(input_path, as_of, out, demo=False):
    input_path, out = Path(input_path), Path(out)
    facts = load_facts(input_path)
    metrics, quality = calculate(facts, as_of)
    out.mkdir(parents=True, exist_ok=True)
    (out / "financials.csv").write_bytes(input_path.read_bytes())
    write_json(out / "metrics.json", metrics)
    write_json(out / "quality.json", quality)
    selected = as_of_facts(facts, as_of)
    with (out / "sources.csv").open("w",encoding="utf-8",newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["fact_ref","source_id","source_url","published_at","entity_id","period_end","metric",
                         "verification","evidence_locator","unit_basis","publication_basis","source_quality"])
        for f in sorted(selected,key=lambda f:f.ref):
            writer.writerow([f.ref,f.source_id,f.source_url,f.published_at.isoformat(),f.entity_id,f.period_end.isoformat(),
                             f.metric,f.verification,f.evidence_locator,f.unit_basis,f.publication_basis,f.source_quality])
    root = Path(__file__).resolve().parents[1]
    (out / "definitions.md").write_text((root/"docs"/"metrics.md").read_text(encoding="utf-8"),encoding="utf-8")
    (out / "static_report.html").write_text(make_report(metrics, as_of, demo, selected, quality),encoding="utf-8")
    (out / "report.html").write_text(make_dashboard(metrics, as_of, demo, selected, quality),encoding="utf-8")
    (out / "analysis.md").write_text("# 待AI解释与人工判断\n\n先核对quality.json；按framework.md解释事实、原因与假设。\n",encoding="utf-8")
    (out / "framework.md").write_text((root/"docs"/"framework.md").read_text(encoding="utf-8"),encoding="utf-8")
    for name in ("core.py",):
        (out/name).write_bytes((Path(__file__).parent/name).read_bytes())
    (out/"recompute.py").write_text('from datetime import date\nfrom core import load_facts, calculate\nimport hashlib\nimport json\nfrom pathlib import Path\nroot=Path(__file__).resolve().parent\nm=json.loads((root/"manifest.json").read_text(encoding="utf-8"))\nfor name,digest in m["files"].items():\n    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, "Hash mismatch: "+name\nresult,quality=calculate(load_facts(root/"financials.csv"), date.fromisoformat(m["as_of"]))\nexpected=json.loads((root/"metrics.json").read_text(encoding="utf-8"))\nassert result == expected, "Metrics mismatch"\nassert quality == json.loads((root/"quality.json").read_text(encoding="utf-8")), "Quality mismatch"\nprint("Recomputation passed:", len(result), "metrics; hashes and quality matched")\n',encoding="utf-8")
    names = ["financials.csv","metrics.json","quality.json","sources.csv","definitions.md","report.html","static_report.html","analysis.md","framework.md","core.py","recompute.py"]
    hashes = {name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in names}
    manifest = {"schema_version":"0.2.0", "as_of":as_of.isoformat(), "generated_at":datetime.now(timezone.utc).isoformat(),
                "data_kind":"synthetic_demo" if demo else "user_supplied_unverified",
                "run_id":hashlib.sha256((__version__+str(as_of)+hashes["financials.csv"]).encode()).hexdigest()[:16],
                "calculation_version":__version__, "verification":verification_summary(selected), "time_basis":"date_only_end_of_day", "files":hashes}
    write_json(out/"manifest.json",manifest)
    with zipfile.ZipFile(out/"review_pack.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for name in names+["manifest.json"]:
            archive.write(out/name, name)
    return {"out":str(out.resolve()), "metrics":len(metrics), "quality":quality["status"], "data_kind":manifest["data_kind"]}

