"""Two bounded, read-only engine entry points for Tyrion's private MCP bridge.

No shell, no secrets in responses, no browser cookies, no publishing or writes to
client sites. Subprocesses are on-demand and die after each requested operation.
"""
import collections
import json
import os
from pathlib import Path
import subprocess

HOME=Path.home()
TOOLKIT=HOME/'Documents/Advertpreneur-Design-Toolkit'
REA=HOME/'.local/bin/rea'
AURA=HOME/'Downloads/AURA-Download-Manager/chrome'
LAST30=TOOLKIT/'sources/mvanhorn-last30days-skill/skills/last30days/scripts/last30days.py'
PYTHON=Path('/usr/bin/python3.12')


def status():
    return {
        'mode':'on_demand_read_only',
        'scrapling':{'available':(HOME/'.local/bin/scrapling').exists(), 'use':'GSC Maestro existing public crawl MCP'},
        'ponytail':{'available':(HOME/'.agents/skills/ponytail/SKILL.md').is_file(),'use':'Tyrion skill router and existing coding tasks'},
        'rea':{'available':REA.exists() and AURA.is_dir(),'mode':'static AURA Chrome extension only'},
        'last30days':{'available':PYTHON.exists() and LAST30.is_file(),'mode':'keyless Reddit and Hacker News, 30 days; no cookies'},
        'note':'Installed sources and tool binaries are local; presence is not a test of all optional providers.'
    }


def recent_research(topic):
    if not isinstance(topic,str) or not (4<=len(topic.strip())<=140):
        raise ValueError('Research topic must contain 4–140 characters')
    if any(ord(c)<32 for c in topic):
        raise ValueError('Control characters are not permitted')
    if not status()['last30days']['available']:
        raise RuntimeError('Last30Days research engine unavailable')
    env={'HOME':str(HOME),'PATH':str(HOME/'.local/bin')+':/usr/bin:/bin',
         'LANG':'C.UTF-8','FROM_BROWSER':'off','BROWSER_CONSENT':'false',
         'SCRAPECREATORS_API_KEY':'', 'LAST30DAYS_REDDIT_SC_MIN_ITEMS':'-1',
         'LAST30DAYS_NATIVE_SEARCH':'0'}
    cmd=[str(PYTHON),str(LAST30),topic.strip(),'--quick','--days=30',
         '--search=reddit,hackernews','--web-backend=none','--no-browser-cookies',
         '--max-results=12','--max-per-source=6','--max-source-fetches=2',
         '--emit=compact','--save-dir=','--auto-resolve']
    try:
        result=subprocess.run(cmd,env=env,capture_output=True,text=True,
                              timeout=50,check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Research exceeded its 50-second safety deadline') from None
    if result.returncode:
        raise RuntimeError('Research did not complete; no results were accepted')
    report=result.stdout.strip()
    if not report or len(report)>300_000:
        raise RuntimeError('Research response is empty or exceeded output limit')
    return {'topic':topic.strip(),'engine':'last30days','sources_requested':['reddit','hackernews'],
            'lookback_days':30,'saved':False,'browser_cookies':False,
            'report':report[:16000], 'truncated':len(report)>16000,
            'note':'Raw third-party evidence; assess source freshness and links before conclusions.'}


def rea_aura_extension():
    if not status()['rea']['available']:
        raise RuntimeError('REA or the allowed AURA extension directory is unavailable')
    cmd=[str(REA),'analyze-javascript-application',str(AURA),'--format','json']
    try:
        result=subprocess.run(cmd,env={'HOME':str(HOME),'PATH':'/usr/bin:/bin',
                                      'LANG':'C.UTF-8'},capture_output=True,
                              text=True,timeout=50,check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError('REA analysis exceeded its 50-second deadline') from None
    if result.returncode:
        raise RuntimeError('REA static analysis could not be completed')
    try:
        data=json.loads(result.stdout)
        observed=data['normalized_result']['graph']
    except (KeyError,TypeError,ValueError):
        raise RuntimeError('Unexpected REA evidence output') from None
    nodes=observed.get('nodes',[])
    return {'engine':'REA','mode':'static_js_analysis','target':'AURA Download Manager Chrome extension',
            'executed_target':False,'evidence_id':data.get('evidence_id'),
            'artifact_sha256':data.get('subject',{}).get('digest',{}).get('sha256'),
            'graph_nodes':len(nodes),'graph_edges':len(observed.get('edges',[])),
            'node_kinds':dict(collections.Counter(node.get('kind','unknown') for node in nodes)),
            'limitations':data.get('limitations',[])[:6],
            'note':'Static structure and candidate relationships only; never proves runtime behavior.'}
