"""Display-only regressions from the second Windows acceptance run."""
from datetime import date
from decimal import Decimal
import re
import unittest
from invest_research.core import Fact
from invest_research.report import chart_svg, date_ticks, make_report, source_anchor


class ReadabilityTests(unittest.TestCase):
    def test_quarter_ticks_include_intermediate_dates_with_true_spacing(self):
        start,end=date(2024,12,31),date(2026,9,30)
        items=[{'period_end':d,'value':'100000000','unit':'CNY'} for d in
               ['2024-12-31','2025-12-31','2026-03-31','2026-06-30','2026-09-30']]
        svg=chart_svg(items,'CNY')
        ticks=re.findall(r'<text class="date-tick" x="([^"]+)" y="242" text-anchor="middle">([^<]+)</text>',svg)
        self.assertGreater(len(ticks),2)
        self.assertEqual(ticks[0][1],str(start))
        self.assertEqual(ticks[-1][1],str(end))
        for x,d in ticks:
            expected=90+(date.fromisoformat(d)-start).days*610/(end-start).days
            self.assertAlmostEqual(float(x),expected,places=2)
        self.assertTrue(all(float(b[0])-float(a[0]) >= 121 for a,b in zip(ticks,ticks[1:])))

    def test_short_long_and_single_period_tick_density(self):
        self.assertEqual(date_ticks(date(2026,3,31),date(2026,3,31)),[date(2026,3,31)])
        self.assertEqual(len(date_ticks(date(2025,12,31),date(2026,9,30))),4)
        ticks=date_ticks(date(2000,3,31),date(2026,9,30))
        self.assertLessEqual(len(ticks),6)
        self.assertEqual(len(ticks),len(set(ticks)))

    def test_chart_sources_exclude_unused_facts_and_keep_actual_dependencies(self):
        facts=[Fact('TEST',date.fromisoformat(d),date(2026,10,31),'revenue',Decimal('100'),'CNY',
                    source,'https://example.com/'+source) for d,source in
               [('2025-12-31','ANNUAL'),('2026-03-31','UNPLOTTED'),('2026-06-30','PRIOR'),('2026-09-30','CURRENT')]]
        annual,unused,prior,current=facts
        def item(end,value,refs):
            return {'entity_id':'TEST','currency':'CNY','period_end':end,'metric':'revenue_ttm',
                    'value':value,'unit':'CNY','status':'available' if value else 'missing_periods',
                    'fact_refs':[f.ref for f in refs],'source_ids':[f.source_id for f in refs]}
        metrics=[item('2025-12-31','100',[annual]),item('2026-03-31',None,[unused]),
                 item('2026-09-30','110',[annual,prior,current])]
        report=make_report(metrics,date(2026,11,5),False,facts)
        block=re.search(r'<details class="chart-sources">(.*?)</details>',report,re.S).group(1)
        refs=re.findall(r'href="#([^"]+)"',block)
        self.assertEqual(set(refs),{source_anchor(f.ref) for f in (annual,prior,current)})
        self.assertEqual(len(refs),3)
        self.assertIn('图表来源（3条证据',block)
        self.assertNotIn(source_anchor(unused.ref),block)
        # A prior-period dependency of a plotted TTM value must not be dropped.
        self.assertIn(source_anchor(prior.ref),block)
        # All sources still exist in the full evidence table, including unplotted inputs.
        for f in facts:self.assertIn('id="'+source_anchor(f.ref)+'"',report)
        self.assertIn('title="ANNUAL"',block)
        self.assertIn('2025-12-31 · 营业收入',block)
        self.assertIn('table class="metrics-table"',report)
        self.assertIn('white-space:nowrap',report)
        self.assertIn('overflow-x:auto',report)
        self.assertIn('class="verification"',report)
