import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tyrion import content_research
from tyrion.bridge import TOOLS,call


class ContentResearchTests(unittest.TestCase):
    def test_track_validation(self):
        for track in ('../../secrets','client-other',''):
            with self.assertRaises(ValueError):content_research.valid_track(track)

    def test_coocoobabys_real_search_data_has_source(self):
        evidence=content_research.gsc_evidence('sc-domain:coocoobabys.com')
        if not evidence['available']:self.skipTest('Current Google Search Console cache unavailable')
        self.assertIn('Google Search Console',evidence['source'])
        self.assertGreater(len(evidence['queries']),0)
        self.assertIn('position',evidence['queries'][0].keys() if 'position' in evidence['queries'][0] else {'position': evidence['queries'][0]['averagePosition']})
        self.assertIn('NOT Google Ads Keyword Planner',evidence['note'])

    def test_packet_does_not_invent_keyword_volumes(self):
        with tempfile.TemporaryDirectory() as d,patch.object(content_research,'STORE',Path(d)),patch.object(content_research.skill_engines,'recent_research',return_value={'report':'- Date range: 2026-09-26 to 2026-10-26\n- Recent evidence is thin: only 2 of 10 dated items are from the last 7 days.'}):
            r=call('tyrion_content_research',{'track':'coocoobabys'})
            self.assertEqual(r['keywordPlanner']['status'],'awaiting_e92_keyword_explorer')
            self.assertIsNone(r['keywordPlanner']['verifiedMonthlyVolumes'])
            self.assertEqual(r['recentDiscussions']['totalDatedItems'],10)
            self.assertEqual(call('tyrion_content_research_latest',{'track':'coocoobabys'})['track'],'coocoobabys')
            self.assertEqual(len(list(Path(d).glob('*.json'))),1)
            self.assertEqual((Path(d)/'coocoobabys.json').stat().st_mode & 0o777,0o600)

    def test_keyword_import_requires_supported_fields_and_is_attributed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(content_research,'STORE',Path(d)):
            content_research.research('linkedin',include_recent=False)
            with self.assertRaises(ValueError):content_research.attach_keyword_metrics('linkedin',[{'keyword':'ai search optimization','avgMonthlySearches':-3}])
            with self.assertRaises(ValueError):content_research.attach_keyword_metrics('linkedin',[{'keyword':'ai search optimization','avgMonthlySearches':'1000'}])
            result=content_research.attach_keyword_metrics('linkedin',[{'keyword':'ai search optimization','avgMonthlySearches':None,'competition':'UNKNOWN'}])
            self.assertEqual(result['rowsSaved'],1)
            saved=content_research.latest('linkedin')
            self.assertEqual(saved['keywordPlanner']['status'],'imported_e92_connector_data')
            self.assertIsNone(saved['keywordPlanner']['rows'][0]['avgMonthlySearches'])

    def test_mcp_tools_advertised(self):
        names={x['name'] for x in TOOLS}
        for name in ('tyrion_content_research','tyrion_content_research_latest','tyrion_content_keyword_import'):self.assertIn(name,names)

if __name__=='__main__':unittest.main()

class EditorialResearchQualityTests(unittest.TestCase):
    def test_coocoobabys_topics_are_search_evidence_backed(self):
        gsc={'available':True,'startDate':'2026-09-26','endDate':'2026-10-23','queries':[
          {'keyword':'best baby monitor without wifi','impressions':180,'averagePosition':10.24},
          {'keyword':'best baby monitor no wifi','impressions':111,'averagePosition':9.37},
          {'keyword':'travel stroller','impressions':20,'averagePosition':19},
        ]}
        out=content_research.editorial_opportunities('coocoobabys',{'searchConsole':gsc,'recentDiscussions':{}})
        self.assertEqual(out[0]['id'],'baby-monitors')
        self.assertEqual(out[0]['gscImpressionsObserved'],291)
        self.assertEqual(out[0]['priority'],'high')
        self.assertTrue(out[0]['requiresHumanReview'])
        self.assertEqual(out[0]['evidenceType'],'google_search_console')

    def test_promotional_social_posts_do_not_become_evidence(self):
        report='''### 1. [PROMOTION] Try our AI ranking shortcut (score 40, 1 item, sources: Reddit)
### 2. Real SEO specialist asks how to compare product page content (score 20, 1 item, sources: Reddit)'''
        ideas=content_research.editorial_opportunities('linkedin',{'recentDiscussions':{'available':True,'lookbackDays':30,'evidence':report}})
        self.assertTrue(ideas)
        self.assertFalse(any('PROMOTION' in title for x in ideas for title in x.get('communityDiscussionHeadlines',[])))
        self.assertTrue(all(x['confidence']=='hypothesis_requires_validation' for x in ideas))

    def test_research_refresh_preserves_provider_evidence(self):
        with tempfile.TemporaryDirectory() as d,patch.object(content_research,'STORE',Path(d)):
            content_research.research('instagram',include_recent=False)
            content_research.attach_secondary_keyword_research('instagram',[{'keyword':'shopify seo','volume':1900}],['shopify seo checklist'])
            content_research.attach_keyword_metrics('instagram',[{'keyword':'shopify seo','avgMonthlySearches':800,'competition':'MEDIUM'}])
            fresh=content_research.research('instagram',include_recent=False)
            self.assertEqual(fresh['secondaryKeywordResearch']['source'],'Ubersuggest')
            self.assertFalse(fresh['secondaryKeywordResearch']['stale'])
            self.assertEqual(fresh['keywordPlanner']['status'],'imported_e92_connector_data')
            self.assertFalse(fresh['keywordPlanner']['stale'])
            self.assertEqual(fresh['keywordPlanner']['rows'][0]['avgMonthlySearches'],800)

    def test_stale_provider_data_marked_not_refreshed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(content_research,'STORE',Path(d)):
            content_research.research('linkedin',include_recent=False)
            p=content_research.latest('linkedin');p.pop('available',None)
            p['secondaryKeywordResearch']={'source':'Ubersuggest','fetchedAt':'2020-01-01T00:00:00+00:00','seedMetrics':[{'keyword':'ecommerce seo','estimatedMonthlyVolume':1000}]}
            content_research.save_packet('linkedin',p)
            updated=content_research.research('linkedin',include_recent=False)
            self.assertTrue(updated['secondaryKeywordResearch']['stale'])
            self.assertEqual(updated['secondaryKeywordResearch']['source'],'Ubersuggest')

class ProviderDiagnosticPreservationTests(unittest.TestCase):
    def test_e92_connector_failure_remains_attributed_after_refresh(self):
        with tempfile.TemporaryDirectory() as d,patch.object(content_research,'STORE',Path(d)):
            initial=content_research.research('instagram',include_recent=False)
            initial['keywordPlanner']['connectorHealth']='tool_internal_error_across_endpoints'
            initial['keywordPlanner']['lastAttemptAt']='2026-10-26'
            content_research.save_packet('instagram',initial)
            fresh=content_research.research('instagram',include_recent=False)
            self.assertEqual(fresh['keywordPlanner']['connectorHealth'],'tool_internal_error_across_endpoints')
            self.assertEqual(fresh['keywordPlanner']['lastAttemptAt'],'2026-10-26')
            self.assertIsNone(fresh['keywordPlanner']['verifiedMonthlyVolumes'])

class ExistingPageTargetingTests(unittest.TestCase):
    def test_existing_page_is_refreshed_not_duplicate_created(self):
        data={
            'searchConsole':{'startDate':'2026-09-26','endDate':'2026-10-23',
              'queries':[{'keyword':'best travel stroller','impressions':53,'averagePosition':14}],
              'pages':[{'url':'https://coocoobabys.com/blog/how-to-choose-a-stroller/','impressions':186,'clicks':0,'ctrPercent':0,'averagePosition':32},
                       {'url':'https://coocoobabys.com/blog/best-lightweight-strollers-for-travel/','impressions':185,'clicks':0,'ctrPercent':0,'averagePosition':23}]},
            'recentDiscussions':{}
        }
        ideas=content_research.editorial_opportunities('coocoobabys',data)
        self.assertEqual(ideas[0]['recommendedAction'],'refresh_existing_page')
        self.assertIn('best-lightweight-strollers-for-travel',ideas[0]['existingPage']['url'])
        self.assertEqual(len(ideas[0]['relatedExistingPages']),1)
        self.assertTrue(ideas[0]['requiresHumanReview'])

    def test_missing_page_does_not_autogenerate_new_url(self):
        data={'searchConsole':{'startDate':'2026-09-26','endDate':'2026-10-23','queries':[
          {'keyword':'best baby monitor no wifi','impressions':111,'averagePosition':9.3}],'pages':[]},
          'recentDiscussions':{}}
        ideas=content_research.editorial_opportunities('coocoobabys',data)
        self.assertEqual(ideas[0]['recommendedAction'],'check_existing_content_before_creating')
