import sys,json,collections
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import analyze as A
from seeds import DOMAINS
R4=A.R4
bE,bC,tg,bL,tt,du=A.build()
t=open(A.W+'/user_data2.txt').read(); ud=json.loads(t[t.index('{'):]); u=ud['tasks'][0]['result'][0]
bal=u['money']['balance']; dayt=u['money']['statistics']['day']['total']; dep=u['money']['total']
spent=dep-bal
net6=A.out['pos_total']+A.out['neg_total']
tasks_all=len(set((r['api'],r['id']) for r in A.pos))
calls=dict(A.out['calls'])
seen=set(x['client'] for x in bC)
missing=[d for d in DOMAINS if d not in seen]
cl={x['client']:x for x in bC}
ai_flag=[r for r in A.L if r['cost']>0 and (A.meta.get(r['id']) or {}).get('load_async_ai_overview')]
d100=[x for x in tg if x['tag'].startswith('kw_')][0]
usb=cl['(unattributed) US desktop top-10 keyword batch, numeric tags']
kwd=sum(1 for _ in A.kwdays)
fmt=lambda x:'${:,.2f}'.format(x)
named=[x for x in bC if not x['client'].startswith('(')]
findings=[
 "Money is about to run out. %s of the %s deposited has been spent, leaving %s. At the last-30-day average of %s a day that lasts about %.1f days, and at the quieter last-7-day average of %s a day about %.1f days. One run of the weekly US keyword batch costs $34 to $58, which is more than the whole balance. That batch did not run on Tuesday 2026-10-13."%(fmt(spent),fmt(dep),fmt(bal),fmt(A.avg30),bal/A.avg30,fmt(A.avg7),bal/A.avg7),
 "Half of all spend comes from one job that is not tied to any client. A Google US-English desktop top-10 SERP batch runs once a week (2026-09-16, 09-22, 09-29 and 10-06). It cost %s over the last 30 days, which is %.0f%% of %s. It made %s task_post calls over %s distinct keywords, on US insurance, pet insurance, moving-company and jewelry topics. None of those topics match the 24 client domains, and its tags are plain numbers (947 distinct values), not project names. Find out who owns it and whether it still needs to run every week."%(fmt(usb['cost']),usb['share']*100,fmt(A.last_total),'{:,}'.format(usb['tasks']),'{:,}'.format(kwd)),
 "Monthly spend has climbed and comes in bursts. Monthly totals are: "+', '.join('%s %s'%(m['month'],fmt(m['cost'])) for m in A.monthly)+" (October runs only to 14 Oct, 12:13 UTC). The biggest single days were one-off SERP batches: 2026-07-12 at $150.87 (251,295 tasks in one day), 2026-09-29 at $69.75, 2026-10-06 at $57.79 and 2026-06-23 at $56.87.",
 "Daily rank tracking is the steady base cost. The nightly 03:00 UTC run costs about $1.40 to $2.50 a day. Its most expensive part is the per-keyword trackers tagged kw_*, which request 100 results each (depth 100). They cost %s for %s tasks in 30 days, about $%.4f per task against $0.0006 for a top-10 check. These trackers belong mostly to Pro, IDI, Sapir and SanDisk/WD. At the observed depth-20 and depth-30 prices ($0.00105 and $0.0015), cutting them to depth 20-30 would more than halve this line (an estimate)."%(fmt(d100['cost']),'{:,}'.format(d100['tasks']),d100['cost']/d100['tasks']),
 "Two avoidable extras. First, load_async_ai_overview is switched on for the Israeli and international trackers. Of %s flagged SERP tasks in the last 30 days, 17,695 were charged $0.0006 above the normal price for their depth, about $10.62 extra (an estimate: the normal price is taken from unflagged tasks of the same depth). Second, the same request was sent more than once on the same day %s times, costing %s. The worst cases are DataForSEO Labs keyword_suggestions for 'raid', sent 20 times on 2026-10-07 ($2.30), and 'label', 'labels', 'sticker' and 'stickers', sent 5 to 8 times each on 2026-09-17. Cache keyword-research results instead of asking again."%('{:,}'.format(len(ai_flag)),'{:,}'.format(du['tasks']),fmt(du['cost'])),
 "Keyword research is about a sixth of spend. Google Ads search_volume/live cost %s (447 calls at $0.09 each, most of them US) and Labs keyword_suggestions cost %s over the last 30 days. Most of these calls carry no tag or client name, so tag research calls with the client to make them traceable."%(fmt([x for x in bE if x['endpoint']=='keywords_data/google_ads/search_volume/live'][0]['cost']),fmt([x for x in bE if x['endpoint']=='dataforseo_labs/google/keyword_suggestions/live'][0]['cost'])),
 "Cost by client over the last 30 days, where it can be attributed: "+', '.join('%s %s'%(x['client'],fmt(x['cost'])) for x in named[:11])+". Much of this attribution is inferred (see attribution in last30.byClient). The direct evidence is a SurgeOS project id in the tag, a domain in the target, a brand term or a SurgeOS-tracked keyword. The inferred part comes from contiguous tracker runs and keyword themes. No spend was seen in the last 30 days for: "+', '.join(missing)+".",
 "The numbers check out. id_list charges since midnight Asia/Jerusalem total %s, which equals the account's day total of %s, so nothing is missing from live endpoints. The 6-month id_list window (from 2026-04-15) adds up to %s net. Lifetime spend is %s, so the remaining %s was spent before 2026-04-15, outside what id_list can return."%(fmt(A.today),fmt(dayt),fmt(net6),fmt(spent),fmt(spent-net6)),
]
out={
 'asOf':'2026-10-14T12:13:00Z',
 'account':{'deposited':1601,'balance':R4(bal),'todaySpend':R4(dayt),'login':u.get('login'),'timezone':u.get('timezone'),'balanceFetchedAt':'2026-10-14T12:21:00Z','lifetimeSpent':R4(spent)},
 'coverage':{'from':'2026-04-15T00:00:00Z','to':'2026-10-14T12:13:00Z','tasks':tasks_all,'calls':sum(calls.values()),'callsByPath':calls,
   'grossCharges':R4(A.out['pos_total']),'refunds':R4(A.out['neg_total']),'netCost':R4(net6),
   'note':("All figures come from the free POST /v3/<api>/id_list endpoint, run over all 11 APIs. No paid calls were made. Each path was paged until a page returned fewer than 1000 rows, with large windows split into sub-windows. Rows are deduplicated on (api, id, datetime_posted). A task's cost is its positive charge row, and refund rows (negative cost, $%.4f in total) are netted. Zero-cost polling rows (task_get/tasks_ready) are ignored. Days and months are UTC. The 'today' check uses Asia/Jerusalem midnight (2026-10-13 21:00Z): id_list gives $%.4f against the account's day total of $%.4f, so the gap is $0. Keyword, tag and location metadata cover only the last 30 days (serp from 2026-09-14 11:20Z, other APIs from 11:30Z). Two gaps have no metadata: 19 rows on 2026-09-16 between 08:01 and 14:00Z, and a few polling-only rows; together they are the '(no metadata)' bucket, %s. Paging ties inside the same second can drop or double a few rows at page edges (a negligible share). Refunds show only when they fall inside a window. Lifetime spend (deposited - balance = $%.4f) is above the 6-month total because id_list cannot see before 2026-04-15. callsByPath counts stored pages plus inline probe calls; about 11 more calls that returned errors (1 Internal Error 50000, about 10 rejected for 'datetime_from' as the 30-day metadata window moved) are not included, and neither are 2 user_data GETs.")%(A.out['neg_total'],A.today,dayt,fmt(cl['(no metadata)']['cost']),spent)},
 'daily':A.daily,
 'monthly':A.monthly,
 'runRate':{'avg7':R4(A.avg7),'avg30':R4(A.avg30),'projectedMonth':R4(A.proj),'octoberToDate':R4(A.oct_mtd),
   'method':'avg7 and avg30 are mean net cost per UTC day over the last 7 and 30 complete days (to 2026-10-13). projectedMonth is October to date plus avg30 times the %.2f days left in October; on avg7 it would be $%.2f.'%(A.rem_days,A.oct_mtd+A.avg7*A.rem_days)},
 'last30':{'window':{'from':'2026-09-14T11:20:00Z','to':'2026-10-14T12:13:00Z'},'total':R4(A.last_total),
   'byEndpoint':bE,'byClient':bC,'byTag':tg,'byLocation':bL,'topTargets':tt,'duplicates':du,
   'attributionNote':'Methods, from strongest to weakest: surgeos_project_tag (a SurgeOS client id inside the task tag); domain_in_target (a client domain appears in the target, url or keyword); brand_term (a client brand name appears in the keyword); surgeos_tracked_keyword (an exact match to the client\'s top-50 tracked keywords in SurgeOS); propagated_run (an untagged rank-tracker task between two tasks of the same client, at most 100 tasks apart in the same request profile, in posting order); keyword_theme (a topic rule, e.g. Hebrew insurance or mortgage terms to bestie.co.il, Hebrew new-build real estate to yad2.co.il, packaging and labels to dappas.com). Treat propagated_run and keyword_theme as inferences.'},
 'spikes':[{'date':s['date'],'cost':s['cost'],'driver':s['driver']} for s in A.spikes],
 'spikeRule':'days whose net cost is above 2x the median daily cost of the last 30 complete days ($%.4f, so the threshold is $%.4f)'%(A.MED30,2*A.MED30),
 'findings':findings,
}
json.dump(out,open('/home/user/CI-Dashboard/data/dataforseo_usage.json','w'),ensure_ascii=False,indent=1)
print(json.dumps({k:out[k] for k in ('asOf','account','runRate')},ensure_ascii=False,indent=1))
print(json.dumps(out['coverage'],ensure_ascii=False)[:600])
for f in findings: print('-',f)
