"""Offline report: explicit provenance, readable values and dated chart segments."""
from collections import Counter
from datetime import date
from decimal import Decimal
import hashlib
import html

FLOW_NAMES = {"revenue":"营业收入", "parent_net_profit":"归母净利润",
              "operating_cashflow":"经营现金流", "capex":"购建长期资产现金支出"}
STATUSES = {"available":"可计算", "positive_base":"正基数同比", "missing_field":"缺少该字段",
            "missing_periods":"缺少所需期间", "missing_value":"输入值为空", "missing_prior_year":"缺少上年可比数据",
            "missing_dependencies":"依赖指标缺失", "zero_revenue":"营收为零",
            "zero_base":"上年基数为零", "turnaround":"扭亏", "turn_to_loss":"转亏",
            "loss_widening":"增亏", "loss_narrowing":"减亏"}
QUALITY_NAMES = {"unclassified":"来源类别未标注", "disclosure":"披露文件",
                 "supplier_evidence":"供应商证据", "tool_description":"工具介绍页，非财报原文"}


def metric_label(name):
    if name == "parent_net_margin_ttm":
        return "归母净利率 · TTM"
    if name == "free_cashflow_ttm":
        return "自由现金流 · TTM"
    yoy = name.endswith("_yoy")
    stem = name[:-4] if yoy else name
    for mode, label in (("_quarter","单季"),("_ytd","年内累计"),("_ttm","TTM")):
        if stem.endswith(mode):
            return FLOW_NAMES.get(stem[:-len(mode)],stem)+" · "+label+("同比" if yoy else "")
    return name


def money_unit(currency):
    return {"CNY":"亿元人民币", "USD":"亿美元", "HKD":"亿港元"}.get(currency,"亿 "+currency)


def formatted_value(item):
    if item["value"] is None:
        return "—", "%" if item["unit"] == "ratio" else money_unit(item["unit"])
    value = Decimal(item["value"])
    if item["unit"] == "ratio":
        return f"{value*100:,.2f}", "%"
    return f"{value/Decimal('100000000'):,.2f}", money_unit(item["unit"])


def source_anchor(ref):
    return "source-"+hashlib.sha256(ref.encode()).hexdigest()[:16]


def verification_summary(facts):
    checked = sum(f.verification == "checked_against_disclosure" for f in facts)
    return {"selected_facts":len(facts), "input_marked_checked_facts":checked,
            "unverified_facts":len(facts)-checked,
            "status":"input_marked_checked" if checked == len(facts) and facts else (
                "partially_input_marked_checked" if checked else "unverified"),
            "basis":"input_metadata_only_not_independent_authentication"}


def next_quarter(end):
    return date(end.year+1,3,31) if end.month == 12 else date(end.year, {3:6,6:9,9:12}[end.month], {3:30,6:30,9:31}[end.month])


def date_ticks(start, end, minimum_days=1):
    """Keep endpoints and evenly spaced calendar-quarter labels, capped for readability."""
    if start == end:
        return [start]
    candidates=[]
    d=next_quarter(start)
    while d < end:
        candidates.append(d)
        d=next_quarter(d)
    # About four interior labels across a 610px plot, even for long histories.
    gap=max(minimum_days,(end-start).days/5)
    ticks=[start]
    for d in candidates:
        if (d-ticks[-1]).days >= gap and (end-d).days >= gap:
            ticks.append(d)
    return ticks+[end]


def chart_svg(items, currency):
    """True date spacing, zero baseline, and no line across an absent quarter."""
    esc = html.escape
    ordered = sorted(items,key=lambda x:x["period_end"])
    valid = [x for x in ordered if x["value"] is not None]
    if not valid:
        return '<p>无可计算的TTM营收数据。</p>'
    start,end = date.fromisoformat(ordered[0]["period_end"]),date.fromisoformat(ordered[-1]["period_end"])
    high = max(Decimal(x["value"]) for x in valid) or Decimal(1)
    high *= Decimal('1.1')
    span = max((end-start).days,1)
    parts = ['<svg viewBox="0 0 760 280" role="img" aria-label="TTM营收趋势：日期横轴，纵轴从零开始">']
    for i in range(5):
        y = 210-i*42.5
        tick = high*Decimal(i)/4/Decimal('100000000')
        parts.append(f'<line x1="90" y1="{y}" x2="700" y2="{y}" stroke="#d9e1ee"/><text x="80" y="{y+5}" text-anchor="end">{tick:,.2f}</text>')
    parts.append(f'<text x="90" y="22">{esc(money_unit(currency))}</text>')
    segments,segment,previous = [],[],None
    for item in ordered:
        d = date.fromisoformat(item["period_end"])
        if item["value"] is None or (previous is not None and d != next_quarter(previous)):
            if segment:
                segments.append(segment)
            segment = []
        if item["value"] is None:
            previous = None
            continue
        x = 90+(d-start).days*610/span
        y = 210-float(Decimal(item["value"])/high)*170
        point = f'{x:.2f},{y:.2f}'
        segment.append(point)
        v,u = formatted_value(item)
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#2563eb" data-date="{d}" data-x="{x:.2f}"><title>{d}: {esc(v)} {esc(u)}</title></circle>')
        previous = d
    if segment:
        segments.append(segment)
    for segment in segments:
        if len(segment)>1:
            parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="#2563eb" stroke-width="2.5"/>')
    labels = date_ticks(start,end)
    for d in labels:
        x = 90+(d-start).days*610/span
        parts.append(f'<line x1="{x:.2f}" y1="210" x2="{x:.2f}" y2="216" stroke="#64748b"/><text class="date-tick" x="{x:.2f}" y="242" text-anchor="middle">{d}</text>')
    parts.append('</svg><p>横轴按实际日期间隔；纵轴从零开始；缺失季度断线。悬停数据点查看日期和数值。</p>')
    return ''.join(parts)


def make_report(metrics, as_of, demo, facts=(), quality=None):
    esc = html.escape
    by_ref = {f.ref:f for f in facts}
    summary = verification_summary(facts)
    title = "合成样例 · 非真实市场数据" if demo else "外部输入数据 · 核验范围见下方"
    verification_text = (f'输入标记已对照原文 {summary["input_marked_checked_facts"]}/{len(facts)} 条；'
                         '这是输入提供的核验记录，程序未自动验证数据真实性。')
    if demo:
        verification_text = '所有示例数字为合成数据，不代表真实证券。'

    def links(refs):
        return ''.join(f'<span class="evidence-link"><a href="#{source_anchor(ref)}" title="{esc(by_ref[ref].source_id,quote=True)}">{by_ref[ref].period_end} · {esc(FLOW_NAMES.get(by_ref[ref].metric,by_ref[ref].metric))}</a></span>'
                        for ref in dict.fromkeys(refs) if ref in by_ref) or '无可用来源'

    def rows(items):
        result=[]
        for item in items:
            value,unit=formatted_value(item)
            evidence=[by_ref[r] for r in item.get('fact_refs',[]) if r in by_ref]
            checked=sum(f.verification=='checked_against_disclosure' for f in evidence)
            verification='合成样例' if demo else (f'输入核对 {checked}/{len(evidence)} 条' if evidence else '无可用证据')
            status=STATUSES.get(item.get('status','available'),item.get('status','available'))
            if item.get('missing_periods'):
                status+='：'+', '.join(item['missing_periods'])
            cells=(item['entity_id'],item['period_end'],metric_label(item['metric']),value,unit,status,verification)
            result.append('<tr>'+''.join('<td class="'+cls+'">'+esc(str(x))+'</td>' for cls,x in zip(
                ('identifier','date','metric','number','unit','status','verification'),cells))+
                '<td>'+links(item.get('fact_refs',[]))+'</td></tr>')
        return ''.join(result)

    headers='<tr>'+''.join('<th>'+x+'</th>' for x in ('对象','报告期','指标','数值','单位','状态','核验记录','来源'))+'</tr>'
    columns='<colgroup>'+''.join(f'<col style="width:{width}px">' for width in (95,110,190,110,115,190,155,280))+'</colgroup>'
    latest={}
    for item in metrics:
        currency=item['currency']
        key=(item['entity_id'],currency)
        latest[key]=max(latest.get(key,''),item['period_end'])
    latest_rows=[]
    for item in metrics:
        currency=item['currency']
        if item['period_end']==latest[(item['entity_id'],currency)]:
            latest_rows.append(item)
    charts=[]
    for entity,currency in sorted({(x['entity_id'],x['unit']) for x in metrics if x['metric']=='revenue_ttm'}):
        items=[x for x in metrics if (x['entity_id'],x['unit'],x['metric'])==(entity,currency,'revenue_ttm')]
        refs=list(dict.fromkeys(r for x in items if x['value'] is not None for r in x.get('fact_refs',[]) if r in by_ref))
        charts.append(f'<h2>{esc(entity)} · TTM营收 · {esc(currency)}</h2>'+chart_svg(items,currency)+
                      f'<p>截至 {as_of}</p><details class="chart-sources"><summary>图表来源（{len(refs)}条证据，仅包含入图数值的计算依据）</summary>{links(refs)}</details>')
    sources=[]
    for f in sorted(facts,key=lambda f:f.ref):
        state='输入标记已对照原文' if f.verification=='checked_against_disclosure' else '未核对'
        sources.append(f'<tr id="{source_anchor(f.ref)}">'+''.join('<td>'+esc(str(x))+'</td>' for x in (
            f.source_id,f.entity_id,f.period_end,f.metric,f.published_at,f.publication_basis,
            QUALITY_NAMES.get(f.source_quality,f.source_quality),state,f.evidence_locator or '未记录',f.unit_basis))+
            f'<td><a href="{esc(f.source_url,quote=True)}">查看来源</a></td></tr>')
    q=quality or {}
    counts=Counter(STATUSES.get(i['status'],i['status']) for i in q.get('issues',[]))
    missing='；'.join(f'{name} {count}项' for name,count in sorted(counts.items())) or '无缺失或特殊基数'
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title><style>body{{font:16px/1.65 system-ui;max-width:1250px;margin:32px auto;padding:0 18px;color:#17212f}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:9px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}.metrics-table{{table-layout:fixed;min-width:1245px}}.metrics-table th,.identifier,.date,.number,.unit,.verification{{white-space:nowrap}}.number{{font-variant-numeric:tabular-nums}}.status,.evidence-link{{overflow-wrap:anywhere}}.evidence-link{{display:block;margin:2px 0}}.chart-sources{{margin-bottom:24px}}svg{{max-width:760px;width:100%;background:#f5f7fc}}svg text{{font:13px system-ui;fill:#475569}}.badge{{background:#fff1c9;padding:12px}}.scroll{{overflow-x:auto}}summary{{cursor:pointer;font-weight:bold}}a{{color:#1d4ed8}}</style>
<h1>{title}</h1><p class="badge">截至 {as_of}；{verification_text}</p>
<p>所选输入 {len(facts)}条；计算质量：{'存在缺口' if q.get('status')=='partial' else '见质检记录'}。{esc(missing)}</p>
<p>报告为固定程序计算结果；完整数值保存在 metrics.json，显示数值统一四舍五入至两位。缺失不填零。</p>
{''.join(charts)}<h2>最新报告期指标</h2><div class="scroll"><table class="metrics-table">{columns}<thead>{headers}</thead><tbody>{rows(latest_rows)}</tbody></table></div>
<details><summary>全部历史指标（{len(metrics)}项）</summary><div class="scroll"><table class="metrics-table">{columns}<thead>{headers}</thead><tbody>{rows(metrics)}</tbody></table></div></details>
<details open><summary>来源与逐条核验记录（{len(facts)}条）</summary><div class="scroll"><table><thead><tr><th>来源ID</th><th>对象</th><th>报告期</th><th>输入字段</th><th>披露日期</th><th>日期依据</th><th>来源类别</th><th>核验状态</th><th>原文位置</th><th>单位依据</th><th>链接</th></tr></thead><tbody>{''.join(sources)}</tbody></table></div></details>
<p>sources.csv 包含同样的逐条记录，指标口径见 definitions.md。日期按输入口径使用，不自动增减一天。</p></html>'''
