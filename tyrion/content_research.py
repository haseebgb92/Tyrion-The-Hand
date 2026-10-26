"""Evidence-backed editorial research shared with existing content workflows.

On-demand only. GSC reads the existing official snapshot; Last30Days uses the
installed cookie-free engine. Keyword Planner metrics are never invented.
There are no publishing tools or model API calls in this module.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json
import os
import re
import sqlite3
import tempfile
from . import skill_engines

HOME=Path.home()
GSC=HOME/'.local/share/com.advertpreneur.gscmaestro/maestro.sqlite3'
STORE=Path(os.environ.get('TYRION_CONTENT_RESEARCH_DIR',str(HOME/'.local/share/tyrion/content-research')))
TRACKS={
 'instagram':{'name':'Instagram · Ecommerce and AI practical tips','property':'sc-domain:advertpreneur.com','market':'US','language':'en','audience':'Ecommerce founders and WordPress/Shopify merchants','topic':'practical ecommerce marketing AI Shopify WordPress tips','seeds':['ecommerce growth','shopify store seo','AI ecommerce automation']},
 'linkedin':{'name':'LinkedIn · Professional thought leadership','property':'sc-domain:advertpreneur.com','market':'US','language':'en','audience':'Business leaders, developers, ecommerce clients','topic':'WordPress AI search optimization ecommerce marketing','seeds':['ai search optimization','ecommerce seo consultant','shopify conversion optimization']},
 'coocoobabys':{'name':'CooCoo Babys · Parenting and product education','property':'sc-domain:coocoobabys.com','market':'US','language':'en','audience':'Expecting parents and families with infants','topic':'baby monitor no wifi safety comparison and baby travel gear','seeds':['best baby monitor without wifi','baby monitor no wifi','best stroller for travel']},
}


def valid_track(track):
 if track not in TRACKS:raise ValueError('Track must be instagram, linkedin, or coocoobabys')
 return TRACKS[track]


def clean_text(value,limit=120):
 if not isinstance(value,str) or not 2<=len(value.strip())<=limit or any(ord(c)<32 for c in value):
  raise ValueError('Invalid research text')
 return value.strip()


def gsc_evidence(property_name):
 if not GSC.is_file():return {'available':False,'reason':'No local verified GSC database'}
 try:
  db=sqlite3.connect(f'file:{GSC}?mode=ro',uri=True,timeout=4)
  db.row_factory=sqlite3.Row
  try:
   snap=db.execute('SELECT id,start_date,end_date,synced_at,query_rows_limited FROM gsc_syncs WHERE site_url=? ORDER BY id DESC LIMIT 1',(property_name,)).fetchone()
   if snap is None:return {'available':False,'reason':'No synced property snapshot'}
   rows=db.execute('''SELECT key,clicks,impressions,ctr,position FROM gsc_metrics
      WHERE sync_id=? AND dimension='query' AND impressions>0 AND length(key)<=110
      AND lower(key) NOT LIKE '%write for us%' AND lower(key) NOT LIKE '%site:%'
      AND lower(key) NOT LIKE '%evaluate the baby supplies company%'
      AND position BETWEEN 4 AND 30 ORDER BY impressions DESC LIMIT 25''',(snap['id'],)).fetchall()
   pages=db.execute('''SELECT key,clicks,impressions,ctr,position FROM gsc_metrics
      WHERE sync_id=? AND dimension='page' AND impressions>0
      AND key LIKE 'https://%' AND instr(key,'#')=0
      ORDER BY impressions DESC LIMIT 100''',(snap['id'],)).fetchall()
  finally:db.close()
  queries=[{'keyword':row['key'],'clicks':row['clicks'],'impressions':row['impressions'],
   'ctrPercent':round(row['ctr'],2),'averagePosition':round(row['position'],2)} for row in rows]
  landing_pages=[{'url':row['key'],'clicks':row['clicks'],'impressions':row['impressions'],
   'ctrPercent':round(row['ctr'],2),'averagePosition':round(row['position'],2)} for row in pages]
  return {'available':True,'source':'Google Search Console API via GSC Maestro local cache','property':property_name,
   'startDate':snap['start_date'],'endDate':snap['end_date'],'syncedAt':snap['synced_at'],
   'queryRowsLimited':bool(snap['query_rows_limited']),'queries':queries,'pages':landing_pages,
   'note':'Real organic search impressions/position; NOT Google Ads Keyword Planner monthly search volume.'}
 except (sqlite3.Error,OSError) as e:
  return {'available':False,'reason':type(e).__name__}


def suggested_seeds(cfg,queries):
 seeds=[]
 for val in [*cfg['seeds'],*(row['keyword'] for row in queries)]:
  key=val.casefold().strip()
  if key not in [x.casefold() for x in seeds] and len(val)<=100:seeds.append(val)
  if len(seeds)>=12:break
 return seeds




def editorial_opportunities(track, packet):
    """Rank reviewable topic briefs; never promote community claims into facts.

    GSC priorities use *actual* query impressions and position; social topics
    are candidate editorial angles, never asserted as trending without evidence.
    """
    valid_track(track)
    queries=packet.get('searchConsole',{}).get('queries',[])
    recent=packet.get('recentDiscussions',{})
    candidates=[]
    if track=='coocoobabys':
        clusters=(
            ('baby-monitors',('baby monitor','baby camera'),'Non-Wi-Fi baby monitors: which features matter?',
             'Comparison guide + buying checklist','Avoid unverifiable claims about device security, safety or signal range; verify specifications and approved references'),
            ('travel-strollers',('stroller',),'Travel stroller buying checklist for families',
             'Practical product comparison','Verify model specifications and current stock before mentioning specific products'),
            ('bottle-warmers',('bottle warmer',),'Choosing a bottle warmer: practical features to compare',
             'Educational guide','Any breast-milk handling or feeding safety advice requires reliable clinical/public-health sourcing'),
            ('baby-carriers',('baby carrier','baby wrap'),'Choosing a carrier that suits a newborn',
             'Product-selection guide','Babywearing safety claims need reputable independent evidence and manufacturer guidance'),
            ('humidifiers',('humidifier',),'Nursery humidifiers: buying considerations',
             'FAQ + checklist','Any medical or respiratory claims need specialist review'),
        )
        slug_hints={
            'baby-monitors':('best-non-wifi-baby-monitors','best-baby-monitors-for-new-parents','do-you-need-a-baby-monitor'),
            'travel-strollers':('best-lightweight-strollers-for-travel','how-to-choose-a-stroller','stroller-comparisons'),
            'bottle-warmers':('best-bottle-warmers-for-breast-milk-and-formula',),
            'baby-carriers':('best-baby-carriers-for-newborns',),
            'humidifiers':('baby-room-humidifier',),
        }
        for key,terms,title,format_name,gate in clusters:
            rows=[q for q in queries if any(term in q.get('keyword','').casefold() for term in terms)]
            if not rows:continue
            rows=sorted(rows,key=lambda v:-v['impressions'])[:7]
            near=[row for row in rows if 4 <= row['averagePosition'] <= 20]
            page_matches=[page for page in packet.get('searchConsole',{}).get('pages',[])
              if '/blog/' in page.get('url','') and
                any(hint in page.get('url','').casefold() for hint in slug_hints[key])]
            # Match the intended article first; a nearby general guide can
            # have more impressions but be the wrong page to rewrite.
            def page_rank(page):
                url=page.get('url','').casefold()
                index=next((i for i,hint in enumerate(slug_hints[key]) if hint in url),len(slug_hints[key]))
                return (index,-page['impressions'])
            page_matches.sort(key=page_rank)
            existing=page_matches[0] if page_matches else None
            candidates.append({'id':key,'title':title,'format':format_name,
                'recommendedAction':'refresh_existing_page' if existing else 'check_existing_content_before_creating',
                'existingPage':existing,'relatedExistingPages':page_matches[1:4],
                'priority':'high' if near and max(x['impressions'] for x in near)>=20 else 'medium',
                'evidenceType':'google_search_console','primaryKeyword':rows[0]['keyword'],
                'supportingKeywords':[x['keyword'] for x in rows[1:]],
                'gscImpressionsObserved':round(sum(row['impressions'] for row in rows)),
                'nearFirstPageVariants':len(near),
                'sourcePeriod':{'start':packet['searchConsole'].get('startDate'), 'end':packet['searchConsole'].get('endDate')},
                'interpretation':'Summed impressions of sampled distinct GSC queries, not unique users, monthly Google Ads search volume, or forecast traffic',
                'confidence':'observed_search_demand_not_conversion_forecast',
                'qualityGate':gate+'; check existing pages and cannibalization before drafting a new URL','requiresHumanReview':True})
        return sorted(candidates,key=lambda x:(x['priority']!='high',-x['gscImpressionsObserved']))[:5]

    report=recent.get('evidence','') if recent.get('available') else ''
    headlines=[]
    for line in report.splitlines():
        match=re.match(r'^### \d+\. (.+?)(?: \(score \d+.*)?$',line.strip())
        if not match:continue
        title=match.group(1).strip()
        if re.search(r'\[(PROMOTION|FREE|AD|SPONSORED|AFFILIATE)\]',title,re.I):continue
        if len(title)<18 or len(title)>240:continue
        headlines.append(title)
    if track=='instagram':
        ideas=[('product-page-seo','What to check before redesigning an ecommerce product page',
                'Instagram educational carousel','shopify store seo','source-backed practical checklist'),
               ('ecommerce-automation','What an ecommerce automation should actually save you',
                'Instagram short tutorial','AI ecommerce automation','candidate topic from track strategy')]
    else:
        ideas=[('ai-search-validation','How to evaluate an AI-search optimization claim',
                'LinkedIn evidence-based explainer','ai search optimization','source-backed critique, not a ranking guarantee'),
               ('ecommerce-seo','Why practical ecommerce SEO matters more than plugin hype',
                'LinkedIn technical opinion','ecommerce seo consultant','candidate topic from track strategy')]
    for slug,title,format_name,seed,angle in ideas:
        candidates.append({'id':slug,'title':title,'format':format_name,
            'priority':'medium','evidenceType':'editorial_candidate',
            'primaryKeyword':seed,'communityDiscussionHeadlines':headlines[:3],
            'communityLookbackDays':recent.get('lookbackDays') if headlines else None,
            'confidence':'hypothesis_requires_validation',
            'qualityGate':'Verify specific examples, use independent facts and avoid treating promotional forum posts as proof of a trend',
            'requiresHumanReview':True,'angle':angle})
    return candidates


def preserve_existing_research(track, new_packet):
    """Keep previously obtained provider research during a fresh discussion run.

    Prevent silent loss of verified data when a newly requested source is down.
    Mark provider evidence stale rather than misrepresenting it as freshly fetched.
    """
    old=latest(track)
    if not old.get('available'):return new_packet
    now=datetime.now(timezone.utc)
    # Retain previously sourced community findings if a public source temporarily
    # fails, but never pretend an older report is newly retrieved.
    previous_recent=old.get('recentDiscussions',{})
    current_recent=new_packet.get('recentDiscussions',{})
    if not current_recent.get('available') and previous_recent.get('available'):
        prior=dict(previous_recent)
        prior['retainedAfterSourceFailure']=True
        prior['latestFetchFailure']=current_recent.get('reason','Source unavailable')[:180]
        new_packet['recentDiscussions']=prior
    # Connector failures are diagnostic evidence too. Retain their timestamp
    # rather than resetting to an apparently unchecked state on each refresh.
    prev_planner=old.get('keywordPlanner',{})
    if prev_planner.get('connectorHealth') and prev_planner.get('lastAttemptAt'):
        new_packet['keywordPlanner']['connectorHealth']=prev_planner['connectorHealth']
        new_packet['keywordPlanner']['lastAttemptAt']=prev_planner['lastAttemptAt']
    for field in ('secondaryKeywordResearch','keywordPlanner'):
        previous=old.get(field)
        if not isinstance(previous,dict):continue
        if field=='keywordPlanner' and previous.get('status')!='imported_e92_connector_data':continue
        source_date=previous.get('fetchedAt')
        try:
            age=(now-datetime.fromisoformat(source_date.replace('Z','+00:00'))).total_seconds()/86400
        except (AttributeError,TypeError,ValueError):
            age=999
        saved=dict(previous)
        saved['stale']=(age>45 or age<0)
        new_packet[field]=saved
    return new_packet


def save_packet(track,packet):
 STORE.mkdir(mode=0o700,parents=True,exist_ok=True)
 file=STORE/(track+'.json')
 fd,tmp=tempfile.mkstemp(dir=STORE,prefix='research-',suffix='.tmp')
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as h:json.dump(packet,h,ensure_ascii=False,indent=2)
  os.chmod(tmp,0o600)
  os.replace(tmp,file)
 except Exception:
  try:os.unlink(tmp)
  except OSError:pass
  raise
 return str(file)


def latest(track):
 valid_track(track)
 file=STORE/(track+'.json')
 if not file.is_file():return {'track':track,'available':False,'reason':'Run a new content research brief first'}
 if file.stat().st_size>150000:raise ValueError('Research packet exceeds local limit')
 data=json.loads(file.read_text(encoding='utf-8'))
 if data.get('track')!=track:raise ValueError('Research track mismatch')
 return {**data,'available':True}


def research(track,topic=None,include_recent=True):
 cfg=valid_track(track)
 q=clean_text(topic,140) if topic is not None else cfg['topic']
 gsc=gsc_evidence(cfg['property'])
 seeds=suggested_seeds(cfg,gsc.get('queries',[]))
 recent={'available':False,'reason':'Skipped by caller'}
 if include_recent:
  try:
   r=skill_engines.recent_research(q)
   report=r['report']
   dated=re.search(r'(\d+) of (\d+) dated items are from the last 7 days',report)
   recent={'available':True,'source':'Last30Days Reddit + Hacker News public discussions',
    'topic':q,'lookbackDays':30,'retrievedAt':datetime.now(timezone.utc).isoformat(),
    'recentItemCount7Days':int(dated.group(1)) if dated else None,
    'totalDatedItems':int(dated.group(2)) if dated else None,
    'evidence':report[:9000],
    'limits':'Public community content is untrusted; individual links and claims require review. Not direct Instagram/LinkedIn data.'}
  except (ValueError,RuntimeError) as e:
   recent={'available':False,'reason':str(e)[:180]}
 packet={'version':1,'track':track,'name':cfg['name'],'audience':cfg['audience'],
  'generatedAt':datetime.now(timezone.utc).isoformat(),'market':cfg['market'],'language':cfg['language'],
  'topic':q,'searchConsole':gsc,'recentDiscussions':recent,
  'keywordPlanner':{'status':'awaiting_e92_keyword_explorer','source':'Google Ads Keyword Planner through connected E92 Keyword Explorer',
   'market':cfg['market'],'language':cfg['language'],'verifiedMonthlyVolumes':None,
   'note':'Do NOT convert Search Console impressions or competitor data to keyword volume. Attach E92 metrics after its API succeeds.'},
  'keywordSeeds':seeds,
  'recommendedResearchAction':{'plugin':'E92 Keyword Explorer','tool':'search_keyword_ideas',
   'country':cfg['market'],'language':cfg['language'],'seed_keywords':seeds[:8],
   'limit':30},
  'editorialGate':'Evidence-only research, no draft publication; verify source URLs and facts before drafting.'}
 packet['editorialOpportunities']=editorial_opportunities(track,packet)
 packet=preserve_existing_research(track,packet)
 save_packet(track,packet)
 return packet


def attach_keyword_metrics(track,rows,market='US',language='en',fetched_at=None):
 """Persist reviewed Google Ads rows passed explicitly through ChatGPT MCP.

 Values are attributed as connector-relayed, not independently verified here.
 """
 valid_track(track)
 if market!='US' or language!='en':raise ValueError('Only the configured US/en research market is accepted')
 if not isinstance(rows,list) or not 1<=len(rows)<=60:raise ValueError('Provide 1–60 keyword metrics')
 cleaned=[]
 for row in rows:
  if not isinstance(row,dict):raise ValueError('Each metric is an object')
  keyword=clean_text(row.get('keyword'),120)
  volume=row.get('avgMonthlySearches')
  if volume is not None and (type(volume) is not int or not 0<=volume<=100000000):raise ValueError('Invalid monthly search volume')
  competition=row.get('competition')
  if competition is not None and competition not in ('LOW','MEDIUM','HIGH','UNKNOWN'):raise ValueError('Invalid competition')
  cleaned.append({'keyword':keyword,'avgMonthlySearches':volume,'competition':competition})
 packet=latest(track)
 if not packet.get('available'):raise ValueError('Run the track research first')
 timestamp=fetched_at or datetime.now(timezone.utc).isoformat()
 if not isinstance(timestamp,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T.{5,40}',timestamp):raise ValueError('Invalid source timestamp')
 packet['keywordPlanner']={'status':'imported_e92_connector_data','source':'E92 Keyword Explorer (caller-supplied connector response)',
  'market':market,'language':language,'fetchedAt':timestamp,'verifiedMonthlyVolumes':None,
  'rows':cleaned,'note':'Metrics are from a caller-relayed connector result; compare with E92 before decisions. Null means unavailable, never zero.'}
 packet.pop('available',None)
 save_packet(track,packet)
 return {'track':track,'rowsSaved':len(cleaned),'source':packet['keywordPlanner']['source'],'fetchedAt':timestamp,'noPublishing':True}


def attach_secondary_keyword_research(track, seeds, related_keywords, provider='Ubersuggest',market='US',language='en'):
    """Save provenance-labelled optional keyword research without spoofing Google Ads."""
    valid_track(track)
    if provider!='Ubersuggest' or market!='US' or language!='en':raise ValueError('Unsupported provider or market')
    if not isinstance(seeds,list) or not 1<=len(seeds)<=4:raise ValueError('Provide 1-4 seed keyword objects')
    if not isinstance(related_keywords,list) or not 1<=len(related_keywords)<=60:raise ValueError('Provide 1-60 keyword ideas')
    reviewed=[]
    for row in seeds:
        if not isinstance(row,dict):raise ValueError('Seed must be a record')
        keyword=clean_text(row.get('keyword'))
        volume=row.get('volume')
        if volume is not None and (type(volume)!=int or volume<0 or volume>100000000):raise ValueError('Invalid search volume')
        reviewed.append({'keyword':keyword,'estimatedMonthlyVolume':volume})
    related=[]
    for item in related_keywords:
        term=clean_text(item)
        if term.casefold() not in [v.casefold() for v in related]:related.append(term)
    p=latest(track)
    if not p.get('available'):raise ValueError('Run track research before attaching keyword ideas')
    p.pop('available',None)
    p['secondaryKeywordResearch']={
        'source':provider,'country':'United States','language':'English',
        'fetchedAt':datetime.now(timezone.utc).isoformat(),
        'seedMetrics':reviewed,'relatedKeywordIdeas':related,
        'note':'Ubersuggest search volumes are third-party estimates, not verified Google Ads Keyword Planner data. Zero or missing volume is not proof of no demand. Keyword phrases still require human relevance screening.'
    }
    save_packet(track,p)
    return {'track':track,'source':provider,'seedMetrics':len(reviewed),'relatedIdeas':len(related),'published':False}
