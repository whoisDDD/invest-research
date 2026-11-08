import copy
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from invest_research.core import DataError
from invest_research.research import load_rows, write_csv, summarize, run_research
from invest_research.collect import pe_rows, strict_ttm

ROOT=Path(__file__).resolve().parents[1]
ASOF=date(2026,11,5)

def row(metric='pe',value='12',d='2026-10-30',universe='PIT'):
    return dict(series_id='TEST',label='测试指数',date=d,metric=metric,value=value,
        unit='multiple' if metric=='pe' else 'CNY',basis={'pe':'provider_ttm','revenue':'ttm','market_cap':'total'}[metric],
        universe_id=universe,available_at='2026-11-01',source_url='https://example.com/data',evidence_locator='row1',missing_reason='')

class ResearchTests(unittest.TestCase):
    def load(self,rows):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.csv';write_csv(p,rows);return load_rows(p,ASOF)

    def test_future_availability_filtered(self):
        future=row(d='2026-10-01');future['available_at']='2026-11-06'
        rows,n=self.load([row(),future]);self.assertEqual(n,1);self.assertEqual(len(rows),1)

    def test_duplicate_or_universe_switch_rejected(self):
        for data in ([row(),row()], [row(),row(d='2026-10-01',universe='FIXED')]):
            with self.assertRaises(DataError):self.load(data)

    def test_units_basis_url_and_nonfinite_rejected(self):
        for key,value in [('value','NaN'),('value','Infinity'),('value','-1'),('value','0'),('unit','CNY'),('basis','lyr'),('source_url','javascript:alert(1)'),('source_url','https://user:pass@example.com')]:
            r=row();r[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(DataError):self.load([r])

    def test_null_not_zero_and_needs_reason(self):
        r=row(value='')
        with self.assertRaises(DataError):self.load([r])
        r['missing_reason']='source_missing';loaded,_=self.load([r]);self.assertIsNone(loaded[0]['value'])
        obs,gaps=summarize(loaded);self.assertFalse(obs);self.assertTrue(gaps)

    def test_pe_ties_and_exact_window(self):
        data,_=self.load([row(value='10',d='2026-10-01'),row(value='12',d='2026-10-02'),row(value='12',d='2026-10-03'),row(value='14',d='2026-10-04'),row(value='12')])
        obs,_=summarize(data);self.assertIn('80.00%',obs[0]['text']);self.assertEqual(len(obs[0]['refs']),5)

    def test_comparison_requires_same_date_and_same_universe(self):
        data=[row('revenue','100',d='2026-10-01',universe='FIXED'),row('revenue','110',universe='FIXED'),row('market_cap','100',d='2026-10-01'),row('market_cap','150')]
        rows,_=self.load(data);obs,gaps=summarize(rows);self.assertFalse(obs);self.assertTrue(any(x['metric']=='comparison' for x in gaps))
        for r in data:r['universe_id']='FIXED'
        obs,_=summarize(self.load(data)[0]);self.assertIn('40.00个百分点',obs[0]['text'])

    def test_pe_api_schema_and_missing(self):
        doc={'code':'200','data':[{'tradeDate':'20261030','indexCode':'000300','peg':None},{'tradeDate':'20261102','indexCode':'000300','peg':12.4}]}
        rows=pe_rows(doc,'https://example.com',ASOF);self.assertEqual(rows[0]['value'],'');self.assertEqual(rows[1]['value'],'12.4')
        doc['data'][0]['indexCode']='WRONG'
        with self.assertRaises(DataError):pe_rows(doc,'https://example.com',ASOF)

    def test_ttm_full_coverage_or_null(self):
        reports={p:{'000001':{'TOTAL_OPERATE_INCOME':v,'NOTICE_DATE':'2026-10-30','UPDATE_DATE':'2026-10-30'}} for p,v in [('2026-09-30',120),('2025-12-31',150),('2025-09-30',100)]}
        value,missing,audit=strict_ttm({'000001'},reports,ASOF);self.assertEqual(value,Decimal(170));self.assertEqual(len(audit),1);self.assertFalse(missing)
        reports['2025-09-30']['000001']['TOTAL_OPERATE_INCOME']=None
        value,missing,_=strict_ttm({'000001'},reports,ASOF);self.assertIsNone(value);self.assertTrue(missing)

    def test_ttm_future_revision_not_used(self):
        reports={p:{'000001':{'TOTAL_OPERATE_INCOME':100,'NOTICE_DATE':'2026-10-30','UPDATE_DATE':'2026-11-06'}} for p in ['2026-09-30','2025-12-31','2025-09-30']}
        value,missing,_=strict_ttm({'000001'},reports,ASOF);self.assertIsNone(value);self.assertEqual(len(missing),3)

    def test_pack_and_embedded_data_safe_and_output_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.csv';r=row();r['label']='</script><script>alert(1)</script>';write_csv(p,[r]);out=Path(td)/'result'
            run_research(p,ASOF,out)
            html=(out/'report.html').read_text();self.assertNotIn(r['label'],html);self.assertIn(r'\u003c/script',html)
            manifest=json.loads((out/'manifest.json').read_text())
            for name,digest in manifest['files'].items():self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),digest)
            with zipfile.ZipFile(out/'review_pack.zip') as z:self.assertIn('research.csv',z.namelist());self.assertNotIn('data/raw',str(z.namelist()))
            with self.assertRaises(DataError):run_research(p,ASOF,out)

    def test_method_map_has_14_pages_and_does_not_invent_formula(self):
        m=json.loads((ROOT/'invest_research/ui/video-methods.json').read_text())
        self.assertEqual([p['page'] for p in m['pages']],list(range(1,15)))
        self.assertEqual(m['pages'][3]['references'],[11.17,12.52,13.87])
        self.assertTrue(any('公式' in x for x in m['unconfirmed']))
