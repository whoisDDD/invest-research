"""Regression coverage for issues found during the first Windows acceptance run."""
import csv
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from invest_research.core import Fact, DataError, calculate, growth, load_facts
from invest_research.doctor import inventory
from invest_research.pipeline import run
from invest_research.report import chart_svg, make_report

ROOT=Path(__file__).resolve().parents[1]


def fact(end, value, metric='revenue', source=None, **kwargs):
    return Fact('TEST',date.fromisoformat(end),date(2026,10,31),metric,D(value),'CNY',
                source or end,'https://example.com/disclosure',**kwargs)


def pick(metrics, name, end='2026-09-30'):
    return next(x for x in metrics if x['metric']==name and x['period_end']==end)


class MetricRegressionTests(unittest.TestCase):
    def test_quarter_ytd_ttm_and_yoy_are_exported_with_exact_evidence(self):
        facts=[fact('2025-06-30','50'),fact('2025-09-30','80'),fact('2025-12-31','120'),
               fact('2026-06-30','60'),fact('2026-09-30','96')]
        metrics,q=calculate(facts,date(2026,11,5))
        for name,value in [('revenue_ytd','96'),('revenue_quarter','36'),('revenue_ttm','136'),
                           ('revenue_ytd_yoy','0.2'),('revenue_quarter_yoy','0.2')]:
            self.assertEqual(pick(metrics,name)['value'],value)
        self.assertEqual(set(pick(metrics,'revenue_quarter_yoy')['source_ids']),
                         {'2025-06-30','2025-09-30','2026-06-30','2026-09-30'})
        self.assertEqual(len(pick(metrics,'revenue_ttm')['fact_refs']),3)
        self.assertEqual(pick(metrics,'capex_ttm')['status'],'missing_field')
        self.assertEqual(pick(metrics,'free_cashflow_ttm')['status'],'missing_dependencies')
        self.assertIn('missing_field',q['issue_counts'])

    def test_q4_and_q1_are_real_quarters_not_annualized(self):
        facts=[fact('2025-09-30','80'),fact('2025-12-31','120'),fact('2026-03-31','31')]
        metrics,_=calculate(facts,date(2026,11,5))
        self.assertEqual(pick(metrics,'revenue_quarter','2025-12-31')['value'],'40')
        self.assertEqual(pick(metrics,'revenue_quarter','2026-03-31')['value'],'31')

    def test_missing_quarter_and_missing_value_are_distinct(self):
        f=fact('2026-09-30','96')
        metrics,_=calculate([f],date(2026,11,5))
        self.assertEqual(pick(metrics,'revenue_quarter')['status'],'missing_periods')
        self.assertEqual(pick(metrics,'revenue_quarter')['missing_periods'],['2026-06-30'])
        metrics,_=calculate([replace(f,value=None)],date(2026,11,5))
        self.assertEqual(pick(metrics,'revenue_ytd')['status'],'missing_value')
        self.assertIsNone(pick(metrics,'revenue_ytd')['value'])

    def test_zero_negative_and_turn_to_loss_survive_export(self):
        for current,prior,status in [('3','0','zero_base'),('3','-2','turnaround'),
                                     ('-4','-2','loss_widening'),('-1','-2','loss_narrowing'),
                                     ('-1','2','turn_to_loss')]:
            with self.subTest(status=status):
                facts=[fact('2025-09-30',prior,'parent_net_profit'),fact('2026-09-30',current,'parent_net_profit')]
                metrics,_=calculate(facts,date(2026,11,5))
                item=pick(metrics,'parent_net_profit_ytd_yoy')
                self.assertIsNone(item['value'])
                self.assertEqual(item['status'],status)

    def test_no_available_facts_is_not_passed_quality(self):
        with self.assertRaises(DataError):
            calculate([fact('2026-09-30','96')],date(2026,10,30))

    def test_ratio_outputs_keep_currency_separate(self):
        facts=[fact('2025-12-31','120'),fact('2025-12-31','12','parent_net_profit')]
        facts += [replace(f,currency='USD',value=f.value*2) for f in facts]
        metrics,_=calculate(facts,date(2026,11,5))
        margins=[x for x in metrics if x['metric']=='parent_net_margin_ttm']
        self.assertEqual({x['currency'] for x in margins},{'CNY','USD'})
        self.assertTrue(all(D(x['value'])==D('.1') for x in margins))


class ReportRegressionTests(unittest.TestCase):
    def test_readable_numbers_metadata_and_source_links_in_report_and_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'facts.csv'
            rows=list(csv.DictReader((ROOT/'examples/demo.csv').read_text(encoding='utf-8').splitlines()))
            for row in rows:
                row.update(verification='unverified',evidence_locator='',unit_basis='财务表，单位元',
                           publication_basis='披露日期',source_quality='supplier_evidence')
            rows[-4].update(verification='checked_against_disclosure',evidence_locator='三季报第1页，营业收入')
            with path.open('w',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
            out=Path(folder)/'out'
            run(path,date(2026,11,5),out)
            html=(out/'report.html').read_text(encoding='utf-8')
            self.assertIn('输入标记已对照原文 1/20 条',html)
            self.assertIn('亿元人民币',html)
            self.assertIn('归母净利率',html)
            self.assertIn('单季同比',html)
            self.assertNotIn('0.113043478260869',html)
            refs=set(re.findall(r'href="#(source-[a-f0-9]+)"',html))
            anchors=set(re.findall(r'id="(source-[a-f0-9]+)"',html))
            self.assertTrue(refs)
            self.assertTrue(refs <= anchors)
            self.assertIn('三季报第1页，营业收入',html)
            manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['verification']['input_marked_checked_facts'],1)
            sources=list(csv.DictReader((out/'sources.csv').read_text(encoding='utf-8').splitlines()))
            self.assertEqual(len(sources),20)
            self.assertTrue(all(x['publication_basis']=='披露日期' for x in sources))
            with zipfile.ZipFile(out/'review_pack.zip') as z:
                extracted=Path(folder)/'unpacked';z.extractall(extracted)
            p=subprocess.run([sys.executable,str(extracted/'recompute.py')],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            # Both metric comparison and manifest verification must survive transfer.
            (extracted/'quality.json').write_text('{}',encoding='utf-8')
            p=subprocess.run([sys.executable,str(extracted/'recompute.py')],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('Hash mismatch',p.stderr)

    def test_chart_uses_real_date_spacing_and_breaks_missing_quarters(self):
        items=[{'period_end':d,'value':v,'unit':'CNY'} for d,v in
               [('2024-12-31','169000000000'),('2025-12-31','170000000000'),
                ('2026-03-31',None),('2026-06-30','171000000000'),('2026-09-30','172000000000')]]
        svg=chart_svg(items,'CNY')
        coords={d:float(x) for d,x in re.findall(r'data-date="([^"]+)" data-x="([^"]+)"',svg)}
        self.assertGreater(coords['2025-12-31']-coords['2024-12-31'],3*(coords['2026-09-30']-coords['2026-06-30']))
        lines=re.findall(r'<polyline points="([^"]+)"',svg)
        self.assertEqual(len(lines),1)
        self.assertEqual(len(lines[0].split()),2)
        self.assertIn('纵轴从零开始',svg)
        self.assertIn('亿元人民币',svg)
        ys=[float(y) for y in re.findall(r'cy="([^"]+)"',svg)]
        self.assertLess(max(ys)-min(ys),5)

    def test_unverified_and_demo_cannot_look_verified(self):
        facts=[fact('2025-12-31','120',source_quality='tool_description')]
        metrics,q=calculate(facts,date(2026,11,5))
        report=make_report(metrics,date(2026,11,5),False,facts,q)
        self.assertIn('外部输入数据',report)
        self.assertIn('输入标记已对照原文 0/1 条',report)
        self.assertIn('工具介绍页，非财报原文',report)
        report=make_report(metrics,date(2026,11,5),True,facts,q)
        self.assertIn('非真实市场数据',report)

    def test_unsafe_source_and_unsubstantiated_checked_flag_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'facts.csv'
            rows=list(csv.DictReader((ROOT/'examples/demo.csv').read_text(encoding='utf-8').splitlines()))
            def save():
                with path.open('w',encoding='utf-8',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
            original=rows[0]['source_url']
            rows[0]['source_url']='javascript:alert(1)';save()
            with self.assertRaises(DataError):load_facts(path)
            rows[0]['source_url']=original
            rows[0]['verification']='checked_against_disclosure'
            for row in rows:row.setdefault('verification','unverified')
            save()
            with self.assertRaises(DataError):load_facts(path)


class DoctorRegressionTests(unittest.TestCase):
    def test_skill_can_be_discovered_without_cli_or_access_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'westock-data';path.mkdir()
            (path/'SKILL.md').write_text('npx -y westock-data-skillhub@1.0.5 finance',encoding='utf-8')
            with patch('invest_research.doctor.shutil.which',return_value=None), patch('invest_research.doctor.Path.home',return_value=Path(folder)/'home'):
                result=inventory([path])
            self.assertFalse(result['westock_cli_installed'])
            self.assertTrue(result['tool_discovered'])
            self.assertEqual(result['supplier_access'],'not_tested')
            self.assertEqual(result['publisher'],'not_verified')
            self.assertEqual(result['skills_discovered'][0]['referenced_npm_versions'],['1.0.5'])
            self.assertNotIn(folder,json.dumps(result))

    def test_npx_alone_does_not_prove_vendor_tool_is_installed(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('invest_research.doctor.shutil.which',side_effect=lambda name:'/bin/npx' if name=='npx' else None),patch('invest_research.doctor.Path.home',return_value=Path(folder)):
                self.assertFalse(inventory()['tool_discovered'])
