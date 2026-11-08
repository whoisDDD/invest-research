"""Index/sector research: explicit universes, independent PE and revenue series."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import zipfile
from urllib.parse import urlparse
from .core import DataError

FIELDS = ['series_id', 'label', 'date', 'metric', 'value', 'unit', 'basis',
          'universe_id', 'available_at', 'source_url', 'evidence_locator', 'missing_reason']
METRICS = {'revenue': ('CNY', 'ttm'), 'market_cap': ('CNY', 'total'), 'pe': ('multiple', 'provider_ttm')}


def decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise DataError('非法数字: ' + str(value)) from None
    if not result.is_finite():
        raise DataError('数值必须有限')
    return result


def load_rows(path, as_of):
    rows, seen, excluded = [], set(), 0
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS) <= set(reader.fieldnames or []):
            raise DataError('研究CSV缺少列: ' + ', '.join(sorted(set(FIELDS) - set(reader.fieldnames or []))))
        for number, original in enumerate(reader, 2):
            row = {key: (original.get(key) or '').strip() for key in FIELDS}
            try:
                d, available = date.fromisoformat(row['date']), date.fromisoformat(row['available_at'])
            except ValueError:
                raise DataError(f'第{number}行日期无效') from None
            if d > as_of or available > as_of:
                excluded += 1
                continue
            if not all(row[k] for k in ('series_id', 'label', 'universe_id', 'source_url', 'evidence_locator')):
                raise DataError(f'第{number}行缺少研究对象、样本口径或证据')
            if row['metric'] not in METRICS or (row['unit'], row['basis']) != METRICS[row['metric']]:
                raise DataError(f'第{number}行指标/单位/口径无效；收入只接收明确的TTM，PE独立导入')
            parsed = urlparse(row['source_url'])
            if parsed.scheme not in ('https', 'http') or not parsed.netloc or parsed.username or parsed.password:
                raise DataError(f'第{number}行来源必须为无凭据的HTTP(S)链接')
            if row['value'] == '':
                row['value'] = None
                if not row['missing_reason']:
                    raise DataError(f'第{number}行空值须说明原因')
            else:
                value = decimal(row['value'])
                if value < 0 or (row['metric'] == 'pe' and value <= 0):
                    raise DataError(f'第{number}行金额不可为负，PE须为正；不适用时填空并说明')
                row['value'] = str(value)
            key = row['series_id'], row['date'], row['metric']
            if key in seen:
                raise DataError(f'第{number}行重复指标/日期；先解决来源冲突')
            seen.add(key)
            row['ref'] = 'fact:' + hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:24]
            rows.append(row)
    if not rows:
        raise DataError('截至该日没有可用研究数据')
    rows.sort(key=lambda row: (row['series_id'], row['date'], row['metric']))
    # A source/basket switch must create another series, not silently splice history.
    for sid in {r['series_id'] for r in rows}:
        group = [r for r in rows if r['series_id'] == sid]
        for metric in METRICS:
            points = [r for r in group if r['metric'] == metric]
            if len({r['universe_id'] for r in points}) > 1 or len({r['label'] for r in group}) > 1:
                raise DataError('同一序列存在样本口径或名称切换，请拆分series_id')
    return rows, excluded


def summarize(rows):
    """Only describe measured changes. A dual-axis crossing is never a signal."""
    observations, gaps = [], []
    for sid in sorted({r['series_id'] for r in rows}):
        group = [r for r in rows if r['series_id'] == sid]
        label = group[0]['label']
        for metric in METRICS:
            valid = [r for r in group if r['metric'] == metric and r['value'] is not None]
            if not valid:
                gaps.append({'series_id': sid, 'metric': metric, 'reason': '无有效数据'})
                continue
            if len(valid) == 1:
                gaps.append({'series_id': sid, 'metric': metric, 'reason': '仅一个真实观测点，不能形成趋势'})
            if metric == 'pe':
                values = [decimal(r['value']) for r in valid]
                latest = values[-1]
                # Empirical CDF, ties included, on the exact imported interval.
                percentile = Decimal(sum(v <= latest for v in values)) / len(values) * 100
                observations.append({'kind': 'fact', 'series_id': sid,
                    'text': f'{label}：{valid[-1]["date"]}来源报告PE为{latest}倍；'
                            f'在{valid[0]["date"]}至{valid[-1]["date"]}共{len(values)}个有效观测中，'
                            f'不高于该值的占比为{percentile:.2f}%。',
                    'refs': [r['ref'] for r in valid], 'formula': 'count(PE <= latest) / N * 100；并列计入；非回测信号'})
        rev = {r['date']: r for r in group if r['metric'] == 'revenue' and r['value'] is not None}
        cap = {r['date']: r for r in group if r['metric'] == 'market_cap' and r['value'] is not None}
        common = sorted(d for d in rev.keys() & cap.keys() if rev[d]['universe_id'] == cap[d]['universe_id'])
        if len(common) < 2:
            gaps.append({'series_id': sid, 'metric': 'comparison', 'reason': '少于两个同日、同样本的营收/总市值配对点；不推导背离或市销率'})
        else:
            first, last = common[0], common[-1]
            r0, c0 = decimal(rev[first]['value']), decimal(cap[first]['value'])
            if r0 > 0 and c0 > 0:
                rg = (decimal(rev[last]['value']) / r0 - 1) * 100
                cg = (decimal(cap[last]['value']) / c0 - 1) * 100
                observations.append({'kind': 'fact', 'series_id': sid,
                    'text': f'{label}：{first}至{last}同样本营收TTM变化{rg:.2f}%，总市值变化{cg:.2f}%，差额{cg-rg:.2f}个百分点。',
                    'refs': [rev[first]['ref'], rev[last]['ref'], cap[first]['ref'], cap[last]['ref']],
                    'formula': '(end/start - 1)*100；两者增速差仅为描述，不是高低估结论'})
    return observations, gaps


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def run_research(path, as_of, out, demo=False, audit_path=None):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise DataError('研究输出目录非空，请使用新目录，避免混入上次报告')
    audit = None
    if audit_path:
        audit = json.loads(Path(audit_path).read_text(encoding='utf-8'))
        if audit.get('as_of') != as_of.isoformat():
            raise DataError('采集审计与研究截至日不一致')
    rows, excluded = load_rows(path, as_of)
    observations, gaps = summarize(rows)
    out.mkdir(parents=True, exist_ok=True)
    methods = json.loads((Path(__file__).parent / 'ui' / 'video-methods.json').read_text(encoding='utf-8'))
    payload = {'schema_version': 1, 'as_of': as_of.isoformat(), 'demo': demo,
               'rows': rows, 'observations': observations, 'gaps': gaps,
               'excluded_future_rows': excluded, 'video': methods,
               'replication_status': 'partial_reference_implementation'}
    (out / 'research.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(out / 'research.csv', rows)
    shell = (Path(__file__).parent / 'ui' / 'research.html').read_text(encoding='utf-8')
    serialized = json.dumps(payload, ensure_ascii=False).replace('&', r'\u0026').replace('<', r'\u003c').replace('>', r'\u003e')
    (out / 'report.html').write_text(shell.replace('__PAYLOAD__', serialized), encoding='utf-8')
    analysis = '# 初步研究\n\n' + ('合成演示，不能用于投资判断。\n\n' if demo else '来源返回未逐家公司核对财报原文。\n\n')
    analysis += '## 数据事实\n\n' + '\n'.join('- ' + x['text'] for x in observations)
    analysis += '\n\n## 数据缺口\n\n' + '\n'.join('- ' + x['reason'] for x in gaps)
    analysis += '\n\n## 待验证解释\n\n核对盈利、样本调整、股本变动、估值方法后再解释差异。\n\n## 人工判断\n\n由研究者补充判断、反证与跟踪条件。\n'
    (out / 'analysis.md').write_text(analysis, encoding='utf-8')
    if audit is not None:
        (out / 'collection-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    methodology = '# 方法与复现边界\n\n' + methods['implementation'] + '\n\n原视频：' + methods['url'] + '\n\n待核实：\n\n' + '\n'.join('- ' + x for x in methods['unconfirmed'])
    (out / 'methodology.md').write_text(methodology, encoding='utf-8')
    source = out / 'source' / 'invest_research'
    (source / 'ui').mkdir(parents=True)
    for name in ('research.py', 'core.py', '__init__.py'):
        (source / name).write_bytes((Path(__file__).parent / name).read_bytes())
    for name in ('research.html', 'video-methods.json'):
        (source / 'ui' / name).write_bytes((Path(__file__).parent / 'ui' / name).read_bytes())
    (out / 'recompute.py').write_text('''from pathlib import Path
import hashlib,json,sys
from datetime import date
root=Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
for name,digest in manifest['files'].items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise SystemExit('Hash mismatch: '+name)
sys.path.insert(0,str(root/'source'))
from invest_research.research import load_rows,summarize
payload=json.loads((root/'research.json').read_text(encoding='utf-8'))
rows,_=load_rows(root/'research.csv',date.fromisoformat(payload['as_of']))
observations,gaps=summarize(rows)
if rows!=payload['rows'] or observations!=payload['observations'] or gaps!=payload['gaps']:raise SystemExit('Recomputation mismatch')
print('Research recomputation passed; source disclosures still require human review.')
''',encoding='utf-8')
    files = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
    (out / 'manifest.json').write_text(json.dumps({'files': files, 'as_of': as_of.isoformat(), 'demo': demo}, indent=2), encoding='utf-8')
    with zipfile.ZipFile(out / 'review_pack.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(out.rglob('*')):
            if p.is_file() and p.name != 'review_pack.zip':
                archive.write(p, p.relative_to(out).as_posix())
    return {'report': str(out / 'report.html'), 'review_pack': str(out / 'review_pack.zip'),
            'rows': len(rows), 'excluded_future_rows': excluded, 'gaps': len(gaps),
            'replication_status': payload['replication_status']}
