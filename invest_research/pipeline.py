"""CSV -> deterministic metrics -> offline HTML and reproducible review pack."""
import csv
import hashlib
import html
import json
from datetime import datetime, timezone, date
from pathlib import Path
import zipfile
from .core import load_facts, calculate, as_of_facts


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_report(metrics, as_of, demo):
    esc = html.escape
    rows = []
    for item in metrics:
        value = item["value"] if item["value"] is not None else "缺数据"
        rows.append("<tr>" + "".join("<td>" + esc(str(x)) + "</td>" for x in
                    (item["entity_id"], item["period_end"], item["metric"], value, item["unit"])) + "</tr>")
    charts = []
    for entity, currency in sorted({(x["entity_id"], x["unit"]) for x in metrics if x["metric"]=="revenue_ttm"}):
        points = [(x["period_end"], float(x["value"])) for x in metrics
                  if x["entity_id"]==entity and x["unit"]==currency and x["metric"]=="revenue_ttm" and x["value"] is not None]
        if len(points) < 2:
            continue
        low, high = min(v for _,v in points), max(v for _,v in points)
        coords = " ".join(f"{20+i*580/(len(points)-1):.2f},{180-(v-low)*140/(high-low or 1):.2f}" for i,(_,v) in enumerate(points))
        charts.append(f'<h2>{esc(entity)} · TTM营收 · {esc(currency)}</h2><svg viewBox="0 0 640 220" role="img" aria-label="TTM营收趋势"><polyline points="{coords}" fill="none" stroke="#2563eb" stroke-width="3"/></svg><p>范围 {low:g}—{high:g}；{esc(points[0][0])} 至 {esc(points[-1][0])}。原始值见下表。</p>')
    title = "合成样例 · 非真实市场数据" if demo else "投资研究数据预览"
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title><style>body{{font:16px/1.65 system-ui;max-width:1100px;margin:32px auto;padding:0 18px;color:#17212f}}table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}svg{{max-width:640px;width:100%;background:#f5f7fc}}.badge{{background:#fff1c9;padding:12px}}code{{background:#eef2f6}}</style>
<h1>{title}</h1><p class="badge">截至 {as_of}；本预览由固定程序计算，未自动生成投资结论。查 quality.json 了解缺失；公式与来源随研究包提供。</p>
{''.join(charts)}<h2>计算结果</h2><table><thead><tr><th>对象</th><th>报告期</th><th>指标</th><th>数值</th><th>单位</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>来源及证据见 sources.csv，指标口径见 definitions.md。趋势仅表示所示样本，不代表指数历史成分序列。</p></html>'''


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
        writer.writerow(["source_id","source_url","published_at"])
        for row in sorted({(f.source_id,f.source_url,f.published_at.isoformat()) for f in selected}):
            writer.writerow(row)
    root = Path(__file__).resolve().parents[1]
    (out / "definitions.md").write_text((root/"docs"/"metrics.md").read_text(encoding="utf-8"),encoding="utf-8")
    (out / "report.html").write_text(make_report(metrics, as_of, demo),encoding="utf-8")
    (out / "analysis.md").write_text("# 待AI解释与人工判断\n\n先核对quality.json；按framework.md解释事实、原因与假设。\n",encoding="utf-8")
    (out / "framework.md").write_text((root/"docs"/"framework.md").read_text(encoding="utf-8"),encoding="utf-8")
    for name in ("core.py",):
        (out/name).write_bytes((Path(__file__).parent/name).read_bytes())
    (out/"recompute.py").write_text('from datetime import date\nfrom core import load_facts, calculate\nimport json\nfrom pathlib import Path\nroot=Path(__file__).resolve().parent\nm=json.loads((root/"manifest.json").read_text(encoding="utf-8"))\nresult,quality=calculate(load_facts(root/"financials.csv"), date.fromisoformat(m["as_of"]))\nexpected=json.loads((root/"metrics.json").read_text(encoding="utf-8"))\nassert result == expected, "Metrics mismatch"\nprint("Recomputation passed:", len(result), "metrics")\n',encoding="utf-8")
    names = ["financials.csv","metrics.json","quality.json","sources.csv","definitions.md","report.html","analysis.md","framework.md","core.py","recompute.py"]
    hashes = {name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in names}
    manifest = {"schema_version":"0.1.0", "as_of":as_of.isoformat(), "generated_at":datetime.now(timezone.utc).isoformat(),
                "data_kind":"synthetic_demo" if demo else "user_supplied_unverified",
                "run_id":hashlib.sha256((str(as_of)+hashes["financials.csv"]).encode()).hexdigest()[:16],
                "calculation_version":"0.1.0", "time_basis":"date_only_end_of_day", "files":hashes}
    write_json(out/"manifest.json",manifest)
    with zipfile.ZipFile(out/"review_pack.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for name in names+["manifest.json"]:
            archive.write(out/name, name)
    return {"out":str(out.resolve()), "metrics":len(metrics), "quality":quality["status"], "data_kind":manifest["data_kind"]}

