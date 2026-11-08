"""Read-only public-source probe. Raw responses stay in the ignored local cache."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen
from .core import DataError
from .research import write_csv, decimal

CSI = 'https://www.csindex.com.cn/csindex-home/perf/index-perf'
OSS = 'https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/'
EM = 'https://datacenter-web.eastmoney.com/api/data/v1/get'


class Cache:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        target, meta = self.root / (key + '.raw'), self.root / (key + '.json')
        if target.exists() and meta.exists():
            record = json.loads(meta.read_text(encoding='utf-8'))
            body = target.read_bytes()
            if record.get('url') != url or record.get('sha256') != hashlib.sha256(body).hexdigest():
                raise DataError('缓存校验失败：' + str(target))
            return body
        # No hidden retries, credentials, arbitrary-host input or TLS overrides.
        with urlopen(url, timeout=30) as response:
            body = response.read(25_000_001)
        if len(body) > 25_000_000:
            raise DataError('来源单次响应超过25MB，停止采集')
        target.write_bytes(body)
        record = {'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                  'sha256': hashlib.sha256(body).hexdigest()}
        meta.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        return body


def pe_rows(document, url, as_of):
    data = document.get('data')
    if str(document.get('code')) != '200' or not isinstance(data, list) or not data:
        raise DataError('中证历史接口未返回有效数据')
    result = []
    for record in data:
        if record.get('indexCode') != '000300':
            raise DataError('中证接口返回了其他指数')
        d = datetime.strptime(record['tradeDate'], '%Y%m%d').date()
        if d > as_of:
            continue
        pe = record.get('peg')
        valid = pe is not None and decimal(pe) > 0
        result.append({'series_id': 'csi300-official', 'label': '沪深300 · 中证历史样本',
            'date': d.isoformat(), 'metric': 'pe', 'value': str(pe) if valid else '',
            'unit': 'multiple', 'basis': 'provider_ttm', 'universe_id': 'CSI:000300:PIT',
            # Conservative: downloaded histories can be revised. Not a PIT backtest database.
            'available_at': as_of.isoformat(), 'source_url': url,
            'evidence_locator': f'data[tradeDate={record["tradeDate"]}].peg；AKShare映射为滚动市盈率；来源预计算，非自算PEG',
            'missing_reason': '' if valid else '来源PE缺失或非正数'})
    if not result:
        raise DataError('指定期间无沪深300数据')
    return result


def strict_ttm(members, reports, as_of):
    """2026Q3 TTM; require all three YTD observations for every declared member."""
    total, missing, audit = Decimal(0), [], []
    for code in sorted(members):
        values, dependencies = [], []
        for period in ('2026-09-30', '2025-12-31', '2025-09-30'):
            record = reports[period].get(code)
            if not record or record.get('TOTAL_OPERATE_INCOME') is None:
                missing.append(f'{code}:{period}:缺营收')
                continue
            announced = record.get('NOTICE_DATE', '')[:10]
            updated = record.get('UPDATE_DATE', '')[:10]
            # Current summaries overwrite revisions. Both dates must be known by as_of.
            if not announced or not updated or max(announced, updated) > as_of.isoformat():
                missing.append(f'{code}:{period}:公告或修订时点不可用')
                continue
            values.append(decimal(record['TOTAL_OPERATE_INCOME']))
            dependencies.append({'period': period, 'value': str(values[-1]), 'notice_date': announced, 'update_date': updated})
        if len(values) == 3:
            value = values[0] + values[1] - values[2]
            if value < 0:
                missing.append(f'{code}:负TTM营收，需人工核对')
            else:
                total += value
                audit.append({'code': code, 'ttm_revenue': str(value), 'dependencies': dependencies})
    return (None if missing else total), missing, audit


def collect_csi300(as_of, start, cache_dir, output, with_finance=False):
    if start > as_of:
        raise DataError('开始日晚于截至日')
    if as_of != date.today():
        raise DataError('在线采集仅支持当前采集日；历史查询不能伪装为当时可见数据，请用research筛选已有快照')
    cache = Cache(Path(cache_dir) / as_of.isoformat())
    url = CSI + '?' + urlencode({'indexCode': '000300', 'startDate': start.strftime('%Y%m%d'), 'endDate': as_of.strftime('%Y%m%d')})
    rows = pe_rows(json.loads(cache.get(url)), url, as_of)
    diagnostics = {'as_of': as_of.isoformat(), 'pe_count': len(rows),
        'finance_status': 'requested_not_completed' if with_finance else '未请求（加 --with-finance）',
        'limits': ['原视频数据商/PE算法/参考线公式尚未确认', '历史PE当前下载快照，不能声称为历史当时可见数据库', '八年同口径营收及总市值历史未取得']}
    # Preserve the successful PE result even when an optional finance request fails.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(output, rows)
    output.with_name('collection-audit.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding='utf-8')
    if with_finance:
        if as_of < date(2026, 11, 1):
            raise DataError('当前财报样板固定为2026Q3，不能用于更早的截至日')
        try:
            import pandas as pd
            from pypdf import PdfReader
        except ImportError:
            raise DataError('财报采集需可选依赖：python -m pip install -e ".[research-data]"；PE采集不需要') from None
        member_url = OSS + 'file/autofile/closeweight/000300closeweight.xls'
        frame = pd.read_excel(io.BytesIO(cache.get(member_url)), dtype=str)
        if frame.shape[1] != 10:
            raise DataError('中证成分权重文件列结构已改变')
        dates = set(frame.iloc[:, 0].str.replace(r'\.0$', '', regex=True))
        members = set(frame.iloc[:, 4].str.replace(r'\.0$', '', regex=True).str.zfill(6))
        if len(dates) != 1 or len(members) != 300 or len(frame) != 300:
            raise DataError('成分文件必须含同日300个唯一代码')
        basket_date = datetime.strptime(next(iter(dates)), '%Y%m%d').date()
        if basket_date > as_of:
            raise DataError('当前成分快照晚于截至日，不能回填历史样本')
        reports = {}
        for period in ('2026-09-30', '2025-12-31', '2025-09-30'):
            def page(n):
                u = EM + '?' + urlencode({'sortColumns': 'UPDATE_DATE,SECURITY_CODE', 'sortTypes': '-1,-1',
                    'pageSize': '500', 'pageNumber': str(n), 'reportName': 'RPT_LICO_FN_CPD',
                    'columns': 'ALL', 'filter': f"(REPORTDATE='{period}')"})
                doc = json.loads(cache.get(u))
                if not doc.get('success') or not doc.get('result'):
                    raise DataError('东方财富未返回业绩报表：' + str(doc.get('message')))
                return doc['result']
            first = page(1)
            if not 1 <= int(first['pages']) <= 50:
                raise DataError('来源分页范围异常')
            records = first['data']
            with ThreadPoolExecutor(max_workers=3) as pool:
                for result in pool.map(page, range(2, int(first['pages']) + 1)):
                    records += result['data']
            if len(records) != first['count']:
                raise DataError('分页条数与来源count不一致，停止聚合')
            selected = {}
            for r in records:
                code = r['SECURITY_CODE']
                if code not in members:
                    continue
                if code in selected or r.get('REPORTDATE', '')[:10] != period:
                    raise DataError('财报样本有重复代码或报告期冲突')
                selected[code] = r
            reports[period] = selected
        value, missing, audit = strict_ttm(members, reports, as_of)
        sid = 'csi300-fixed-' + basket_date.isoformat()
        universe = 'CSI:000300:fixed:' + basket_date.isoformat()
        rows.append({'series_id': sid, 'label': '沪深300 · 固定样本快照', 'date': basket_date.isoformat(),
            'metric': 'revenue', 'value': '' if value is None else str(value), 'unit': 'CNY', 'basis': 'ttm',
            'universe_id': universe, 'available_at': as_of.isoformat(), 'source_url': EM,
            'evidence_locator': f'RPT_LICO_FN_CPD.TOTAL_OPERATE_INCOME；{basket_date}成分300只；2026Q3+2025FY-2025Q3；逐股依赖见collection-audit.json',
            'missing_reason': f'{len(missing)}项依赖未通过，详见collection-audit.json' if missing else ''})
        sheet_url = OSS + 'indices/detail/files/zh_CN/000300factsheet.pdf'
        sheet = PdfReader(io.BytesIO(cache.get(sheet_url))).pages[0].extract_text()
        date_match = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', sheet)
        cap_match = re.search(r'^总市值\s+([\d,]+)\s*$', sheet, re.M)
        sheet_date = date(*(int(x) for x in date_match.groups())) if date_match else None
        if sheet_date == basket_date and cap_match and '市值(亿元)' in sheet:
            rows.append({'series_id': sid, 'label': '沪深300 · 固定样本快照', 'date': basket_date.isoformat(),
                'metric': 'market_cap', 'value': str(decimal(cap_match[1].replace(',', '')) * 100_000_000),
                'unit': 'CNY', 'basis': 'total', 'universe_id': universe, 'available_at': as_of.isoformat(),
                'source_url': sheet_url, 'evidence_locator': f'第1页；{sheet_date}；市值(亿元)→成分股总市值；不是指数市值/自由流通市值', 'missing_reason': ''})
        else:
            diagnostics['limits'].append('概况PDF与成分日期/字段不匹配，未导入总市值')
        diagnostics.update({'finance_status': 'complete_snapshot' if value is not None else 'incomplete_snapshot',
            'basket_date': basket_date.isoformat(), 'member_count': len(members), 'matched_ttm_count': len(audit),
            'missing_dependencies': missing, 'members_source': member_url, 'members': sorted(members),
            'ttm_dependencies': audit, 'ttm_formula': 'sum(each member 2026Q3 YTD + 2025FY - 2025Q3 YTD)',
            'warning': '固定样本快照仅一个观测点，不能代替原视频的八年营收/总市值趋势'})
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(output, rows)
    audit_path = output.with_name('collection-audit.json')
    audit_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'input': str(output), 'audit': str(audit_path), 'pe_count': len([r for r in rows if r['metric'] == 'pe']), 'finance_status': diagnostics['finance_status']}
