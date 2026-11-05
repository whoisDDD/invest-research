"""Embed reviewed metrics and local UI assets in a portable, offline HTML report."""
from dataclasses import asdict
import json
from pathlib import Path
from . import __version__


def make_dashboard(metrics, as_of, demo, facts, quality):
    payload={"metrics":metrics,"as_of":as_of.isoformat(),"demo":bool(demo),
             "data_kind":"synthetic_demo" if demo else "user_supplied_unverified",
             "version":__version__,"quality":quality,"facts":[]}
    for fact in facts:
        row=asdict(fact)
        for name in ("period_end","published_at"):
            row[name]=row[name].isoformat()
        row["value"]=str(row["value"]) if row["value"] is not None else None
        row["ref"]=fact.ref
        payload["facts"].append(row)
    serialized=json.dumps(payload,ensure_ascii=False,separators=(",",":"))
    # User-controlled labels and evidence cannot terminate the JSON script block.
    for before,after in (("&",r"\u0026"),("<",r"\u003c"),(">",r"\u003e"),("\u2028",r"\u2028"),("\u2029",r"\u2029")):
        serialized=serialized.replace(before,after)
    root=Path(__file__).parent/"ui"
    shell=(root/"shell.html").read_text(encoding="utf-8")
    # Substitute data last, without treating user data as a template.
    return shell.replace("__STYLES__",(root/"dashboard.css").read_text(encoding="utf-8")).replace(
        "__SCRIPT__",(root/"dashboard.js").read_text(encoding="utf-8")).replace("__PAYLOAD__",serialized)
