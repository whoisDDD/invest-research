"""Offline dashboard contracts; no browser or optional Node dependency required."""
import json
from datetime import date
from dataclasses import replace
from pathlib import Path
import re
import tempfile
import unittest
import zipfile
from invest_research.core import Fact, calculate, load_facts
from invest_research.dashboard import make_dashboard
from invest_research.pipeline import run

ROOT=Path(__file__).resolve().parents[1]


def payload(html):
    match=re.search(r'<script type="application/json" id="research-data">(.*?)</script>',html,re.S)
    return json.loads(match.group(1))


class DashboardTests(unittest.TestCase):
    def test_payload_preserves_metrics_nulls_provenance_and_original_precision(self):
        facts=load_facts(ROOT/'examples/demo.csv')
        metrics,q=calculate(facts,date(2026,11,5))
        p=payload(make_dashboard(metrics,date(2026,11,5),True,facts,q))
        self.assertEqual(p['metrics'],metrics)
        self.assertEqual(p['quality'],q)
        self.assertEqual(len(p['facts']),len(facts))
        self.assertEqual({f['ref'] for f in p['facts']},{f.ref for f in facts})
        self.assertTrue(any(m['value'] is None for m in p['metrics']))
        self.assertEqual(p['data_kind'],'synthetic_demo')

    def test_user_metadata_cannot_terminate_script_and_remains_plain_data(self):
        from decimal import Decimal
        dangerous='</script><script>alert("x")</script>__SCRIPT__&'
        f=Fact(dangerous,date(2025,12,31),date(2026,3,30),'revenue',Decimal('1.123456789'),'CNY',dangerous,'https://example.com',evidence_locator=dangerous)
        metrics,q=calculate([f],date(2026,11,5))
        html=make_dashboard(metrics,date(2026,11,5),False,[f],q)
        self.assertNotIn('<script>alert',html)
        self.assertEqual(payload(html)['facts'][0]['entity_id'],dangerous)
        self.assertEqual(payload(html)['facts'][0]['value'],'1.123456789')
        self.assertIn('static_report.html',html)

    def test_generated_report_is_offline_and_pack_contains_static_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out'
            run(ROOT/'examples/demo.csv',date(2026,11,5),out,demo=True)
            html=(out/'report.html').read_text(encoding='utf-8')
            self.assertNotRegex(html,r'<(?:script|link|img)\b[^>]*(?:src|href)="https?://')
            for control in ['entity-select','period-select','mode-control','range-select','inspector','metric-search','export-button','theme-toggle']:
                self.assertIn('id="'+control+'"',html)
            self.assertNotIn('__PAYLOAD__',html)
            self.assertNotIn('__STYLES__',html)
            self.assertNotIn('__SCRIPT__',html)
            with zipfile.ZipFile(out/'review_pack.zip') as z:
                self.assertIn('static_report.html',z.namelist())
                manifest=json.loads(z.read('manifest.json'))
                self.assertIn('static_report.html',manifest['files'])

    def test_rich_demo_is_explicitly_synthetic_with_real_quarter_inputs(self):
        facts=load_facts(ROOT/'examples/dashboard-demo.csv')
        self.assertEqual({f.entity_id for f in facts},{'SYNTHETIC-A','SYNTHETIC-B'})
        self.assertTrue(all('synthetic-not-market-data' in f.source_url for f in facts))
        self.assertEqual(len(facts),152)
        metrics,q=calculate(facts,date(2026,11,5))
        self.assertEqual(len(metrics),988)
        self.assertTrue(all(m['value'] is not None for m in metrics if m['period_end']=='2026-09-30' and m['metric'] in ['revenue_quarter','operating_cashflow_ttm','free_cashflow_ttm']))
