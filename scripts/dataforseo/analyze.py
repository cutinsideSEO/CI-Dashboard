import sys,collections,json,statistics,datetime,glob,re
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from load import load,W
from seeds import *
R4=lambda x: round(x+0.0,4)
rows,meta,files=load()
NOW='2026-10-14 12:13:00'
L0='2026-09-14 11:20:00'
GAP=100
P=lambda s: datetime.datetime.strptime(s[:19],'%Y-%m-%d %H:%M:%S')
def norm_ep(r):
    u=r['url'][3:] if r['url'].startswith('v3/') else r['url']
    m=meta.get(r['id']) or {}
    if (r.get('cost') or 0)>0:
        if '/task_get/' in u: u=u.split('/task_get/')[0]+'/task_post'
        if u.endswith('refund_money'):
            if r['api']=='serp': u='serp/%s/%s/task_post'%(m.get('se','google'),m.get('se_type','organic'))
            elif r['api']=='business_data': u='business_data/google/%s/task_post'%(m.get('function') or 'reviews')
    return u
# ---- per-row
pos=[r for r in rows.values() if (r.get('cost') or 0)>0]
neg=[r for r in rows.values() if (r.get('cost') or 0)<0]
day=collections.defaultdict(lambda:{'cost':0.0,'tasks':set(),'byApi':collections.defaultdict(float)})
for r in pos+neg:
    d=r['datetime_posted'][:10]; c=r['cost']
    day[d]['cost']+=c; day[d]['byApi'][r['api']]+=c
    if c>0: day[d]['tasks'].add((r['api'],r['id']))
dates=[]; d0=datetime.date(2026,4,15)
while d0<=datetime.date(2026,10,14): dates.append(d0.isoformat()); d0+=datetime.timedelta(days=1)
daily=[{'date':d,'cost':R4(day[d]['cost']),'tasks':len(day[d]['tasks']),'byApi':{k:R4(v) for k,v in sorted(day[d]['byApi'].items(),key=lambda x:-x[1]) if abs(v)>=0.00005}} for d in dates]
mon=collections.defaultdict(lambda:{'cost':0.0,'tasks':0,'byApi':collections.defaultdict(float)})
for x in daily:
    m=mon[x['date'][:7]]; m['cost']+=x['cost']; m['tasks']+=x['tasks']
    for k,v in x['byApi'].items(): m['byApi'][k]+=v
monthly=[{'month':k,'cost':R4(v['cost']),'tasks':v['tasks'],'byApi':{a:R4(b) for a,b in sorted(v['byApi'].items(),key=lambda x:-x[1])}} for k,v in sorted(mon.items())]
# run rate on complete days
comp=[x for x in daily if x['date']<='2026-10-13']
avg7=sum(x['cost'] for x in comp[-7:])/7; avg30=sum(x['cost'] for x in comp[-30:])/30
oct_mtd=sum(x['cost'] for x in daily if x['date'][:7]=='2026-10')
rem_days=(P('2026-11-01 00:00:00')-P(NOW)).total_seconds()/86400
proj=oct_mtd+avg30*rem_days
# today (Asia/Jerusalem, UTC+3 in Oct) since 2026-10-13 21:00 UTC
T0='2026-10-13 21:00:00'
today=sum(r['cost'] for r in pos+neg if T0<=r['datetime_posted'][:19]<=NOW)
today_by=collections.defaultdict(float)
for r in pos+neg:
    if T0<=r['datetime_posted'][:19]<=NOW: today_by[norm_ep(r)]+=r['cost']
# ---- attribution
def direct(m):
    t=str(m.get('tag') or '')
    for sid,d in SURGE_IDS.items():
        if sid in t: return d,'surgeos_project_tag'
    txt=' '.join(str(m.get(k) or '') for k in ('keyword','target','url','user_prompt')).lower()
    txt+=' '+' '.join(str(x) for x in (m.get('keywords') or m.get('targets') or [])).lower()
    for d in sorted(DOMAINS,key=len,reverse=True):
        if d in txt: return d,'domain_in_target'
    for d,bs in BRANDS.items():
        for b in bs:
            if b in txt: return d,'brand_term'
    kw=str(m.get('keyword') or '').lower().strip()
    for d,s in SEEDS.items():
        if kw in s: return d,'surgeos_tracked_keyword'
    return None,None
L=[r for r in pos+neg if r['datetime_posted'][:19]>=L0]
lab={}
prof=lambda m:(m.get('se_type'),m.get('location_code') or m.get('location_name'),m.get('language_code'),m.get('device'),m.get('depth'),m.get('priority'))
seq=collections.defaultdict(list)
for r in L:
    m=meta.get(r['id'])
    if not m: continue
    d,how=direct(m)
    if d: lab[r['id']]=(d,how)
    if r['api']=='serp' and (r.get('cost') or 0)>0: seq[prof(m)].append((r['datetime_posted'],r['id']))
# propagate within contiguous posting runs of the same request profile: fill an unlabelled task only when
# the nearest labelled tasks before and after it (same profile, sorted by post time) carry the same client.
for p,s in seq.items():
    s.sort()
    ids=[i for _,i in s]
    prev=[(None,-10**9)]*len(ids); nxt=[(None,10**9)]*len(ids); cur=(None,-10**9)
    for i,x in enumerate(ids):
        if x in lab: cur=(lab[x][0],i)
        prev[i]=cur
    cur=(None,10**9)
    for i in range(len(ids)-1,-1,-1):
        if ids[i] in lab: cur=(lab[ids[i]][0],i)
        nxt[i]=cur
    for i,x in enumerate(ids):
        if x not in lab and prev[i][0] and prev[i][0]==nxt[i][0] and nxt[i][1]-prev[i][1]<=GAP: lab[x]=(prev[i][0],'propagated_run')
def client_of(r):
    if r['id'] in lab: return lab[r['id']]
    m=meta.get(r['id'])
    if not m: return ('(no metadata)',None)
    if r['api']=='serp' and m.get('location_code')==2840 and m.get('device')=='desktop' and m.get('depth')==10 and str(m.get('tag','')).isdigit():
        return ('(unattributed) US desktop top-10 keyword batch, numeric tags',None)
    txt=' '.join(str(m.get(k) or '') for k in ('keyword','target','url','user_prompt')).lower()+' '+' '.join(str(x) for x in (m.get('keywords') or m.get('targets') or [])).lower()+' '
    for d,terms in THEMES:
        if any(t in txt for t in terms): return (d,'keyword_theme')
    return ('(unattributed) other',None)
agg=lambda: {'cost':0.0,'tasks':set()}
byEp=collections.defaultdict(agg); byCl=collections.defaultdict(lambda:{'cost':0.0,'tasks':set(),'how':collections.Counter()}); byTag=collections.defaultdict(lambda:{'cost':0.0,'tasks':set(),'apis':set()})
byLoc=collections.defaultdict(agg); tgt=collections.defaultdict(lambda:{'cost':0.0,'tasks':0,'days':set(),'client':None,'eps':set()})
last_total=0.0
for r in L:
    c=r['cost']; last_total+=c; k=(r['api'],r['id']); m=meta.get(r['id']) or {}
    e=byEp[norm_ep(r)]; e['cost']+=c
    if c>0: e['tasks'].add(k)
    cl,how=client_of(r); e=byCl[cl]; e['cost']+=c
    if c>0: e['tasks'].add(k); e['how'][how]+=c
    t=str(m.get('tag')) if m.get('tag') else '(no tag)'
    if t.startswith('av1|'): t='av1|'+t.split('|')[1]+' (AI visibility project)'
    elif t.startswith('kw_'): t='kw_* (per-keyword tags)'
    elif t.isdigit(): t='numeric shard tag '+t
    e=byTag[t]; e['cost']+=c; e['apis'].add(r['api'])
    if c>0: e['tasks'].add(k)
    loc=m.get('location_name') or m.get('location_code') or m.get('location_coordinate') or '(n/a)'
    e=byLoc[(str(loc),str(m.get('language_code')))]; e['cost']+=c
    if c>0: e['tasks'].add(k)
    tk=m.get('target') or m.get('url') or (','.join(m.get('targets')) if m.get('targets') else None) or m.get('keyword') or m.get('user_prompt') or (('keywords:'+'|'.join(m['keywords'][:3])) if m.get('keywords') else None)
    if tk:
        e=tgt[(str(tk),str(loc),str(m.get('language_code')))]; e['cost']+=c
        if c>0: e['tasks']+=1; e['days'].add(r['datetime_posted'][:10]); e['eps'].add(norm_ep(r))
        e['client']=cl
# duplicates: same request (endpoint+keyword/target+location+language+device+depth) more than once on the same UTC day
dup=collections.defaultdict(list)
for r in L:
    if r['cost']<=0: continue
    m=meta.get(r['id'])
    if not m: continue
    key=(norm_ep(r),str(m.get('keyword') or m.get('target') or m.get('url') or m.get('keywords') or m.get('targets')),str(m.get('location_code') or m.get('location_name')),str(m.get('language_code')),str(m.get('device')),str(m.get('depth')),r['datetime_posted'][:10])
    dup[key].append(r['cost'])
dup_cost=0.0; dup_tasks=0; dup_by=collections.defaultdict(lambda:[0,0.0]); dup_ex=[]
for k,v in dup.items():
    if len(v)>1:
        x=sum(sorted(v)[1:]) if True else 0
        x=sum(v)-min(v); dup_cost+=x; dup_tasks+=len(v)-1; dup_by[k[0]][0]+=len(v)-1; dup_by[k[0]][1]+=x
        dup_ex.append((x,len(v),k))
dup_ex.sort(reverse=True)
# weekly re-query of identical keyword sets
kwdays=collections.defaultdict(set)
for r in L:
    m=meta.get(r['id'])
    if r['cost']>0 and m and r['api']=='serp' and m.get('location_code')==2840 and m.get('depth')==10 and str(m.get('tag','')).isdigit():
        kwdays[m.get('keyword')].add(r['datetime_posted'][:10])
rep=collections.Counter(len(v) for v in kwdays.values())
# ---- spikes: day cost > 2x median of the preceding 30 days (all coverage)
spikes=[]
MED30=statistics.median([y['cost'] for y in comp[-30:]])
for i,x in enumerate(daily):
    med=MED30
    if x['cost']>2*med:
        d=x['date']; dr=[r for r in pos if r['datetime_posted'][:10]==d]
        ep=collections.Counter(); hr=collections.Counter(); pf=collections.Counter()
        for r in dr:
            ep[norm_ep(r)]+=r['cost']; hr[r['datetime_posted'][11:13]]+=r['cost']
            m=meta.get(r['id'])
            if m: pf[(m.get('location_code') or m.get('location_name'),m.get('language_code'),m.get('device'),m.get('depth'),'numeric tags' if str(m.get('tag','')).isdigit() else (str(m.get('tag'))[:20] if m.get('tag') else 'no tag'))]+=r['cost']
        e1,c1=ep.most_common(1)[0]; h1,hc=hr.most_common(1)[0]
        n1=sum(1 for r in dr if norm_ep(r)==e1)
        drv='%s $%.2f (%d tasks)'%(e1,c1,n1)
        if len(ep)>1:
            e2,c2=ep.most_common(2)[1]; drv+=', then %s $%.2f'%(e2,c2)
        drv+='; busiest hour %s:00 UTC $%.2f'%(h1,hc)
        if pf:
            p1,pc=pf.most_common(1)[0]; drv+='; main request profile: location %s, language %s, %s, depth %s, %s ($%.2f)'%(p1[0],p1[1],p1[2],p1[3],p1[4],pc)
        if not pf and x['date']<'2026-09-14': drv+='; before the 30-day metadata window, so no keyword/location detail'
        spikes.append({'date':d,'cost':x['cost'],'driver':drv})
# ---- calls per path
calls=collections.Counter()
for f in files: calls[json.load(open(f))['tasks'][0]['data']['api']]+=1
extra=0
for line in open(W+'/_extra_calls.txt'):
    n=int(line.split()[1]); calls[line.split()[0]]+=n
out=dict(today=today,today_by=today_by,avg7=avg7,avg30=avg30,oct_mtd=oct_mtd,proj=proj,rem_days=rem_days,last_total=last_total,
 pos_total=sum(r['cost'] for r in pos),neg_total=sum(r['cost'] for r in neg),calls=calls,dup_cost=dup_cost,dup_tasks=dup_tasks,rep=rep)
if __name__=='__main__':
    print({k:(R4(v) if isinstance(v,float) else v) for k,v in out.items() if k not in('today_by',)})
    print('today by ep',{k:R4(v) for k,v in sorted(today_by.items(),key=lambda x:-x[1])})
    for m in monthly: print(m['month'],m['cost'],m['tasks'],m['byApi'])
    print('last7',[(x['date'],x['cost']) for x in comp[-10:]])
    print('--byEp'); [print(' ',k,R4(v['cost']),len(v['tasks'])) for k,v in sorted(byEp.items(),key=lambda x:-x[1]['cost'])[:15]]
    print('--byClient'); [print(' ',k,R4(v['cost']),len(v['tasks']),{a:R4(b) for a,b in v['how'].items()}) for k,v in sorted(byCl.items(),key=lambda x:-x[1]['cost'])]
    print('--byTag'); [print(' ',k,R4(v['cost']),len(v['tasks'])) for k,v in sorted(byTag.items(),key=lambda x:-x[1]['cost'])[:12]]
    print('--byLoc'); [print(' ',k,R4(v['cost']),len(v['tasks'])) for k,v in sorted(byLoc.items(),key=lambda x:-x[1]['cost'])[:10]]
    print('--top targets'); [print(' ',k,R4(v['cost']),v['tasks'],len(v['days']),v['client'],v['eps']) for k,v in sorted(tgt.items(),key=lambda x:-x[1]['cost'])[:15]]
    print('--dupes by ep',{k:(v[0],R4(v[1])) for k,v in sorted(dup_by.items(),key=lambda x:-x[1][1])[:8]})
    for x in dup_ex[:8]: print('  dup',R4(x[0]),x[1],x[2])
    print('--repeat days of US batch keywords',sorted(rep.items()))
    print('--spikes'); [print(' ',s) for s in spikes]

def build():
    nm=lambda d:sorted(d.items(),key=lambda x:-x[1]['cost'])
    tot=last_total
    byEndpoint=[{'endpoint':k,'cost':R4(v['cost']),'tasks':len(v['tasks']),'share':round(v['cost']/tot,4)} for k,v in nm(byEp) if abs(v['cost'])>=0.00005]
    byClient=[{'client':k,'cost':R4(v['cost']),'tasks':len(v['tasks']),'share':round(v['cost']/tot,4),'attribution':{(a or 'none'):R4(b) for a,b in sorted(v['how'].items(),key=lambda x:-x[1])}} for k,v in nm(byCl)]
    num=[(k,v) for k,v in byTag.items() if k.startswith('numeric shard tag')]
    tags=[{'tag':k,'cost':R4(v['cost']),'tasks':len(v['tasks']),'apis':sorted(v['apis'])} for k,v in nm({k:v for k,v in byTag.items() if not k.startswith('numeric shard tag')})]
    tags.append({'tag':'numeric tags (%d distinct values, used as worker/shard numbers, not projects)'%len(num),'cost':R4(sum(v['cost'] for _,v in num)),'tasks':sum(len(v['tasks']) for _,v in num),'apis':['serp'],
        'top':[{'tag':k.split()[-1],'cost':R4(v['cost']),'tasks':len(v['tasks'])} for k,v in sorted(num,key=lambda x:-x[1]['cost'])[:10]]})
    tags.sort(key=lambda x:-x['cost'])
    byLocation=[{'location':k[0],'language':k[1],'cost':R4(v['cost']),'tasks':len(v['tasks'])} for k,v in nm(byLoc)[:20]]
    topTargets=[{'target':k[0],'location':k[1],'language':k[2],'cost':R4(v['cost']),'tasks':v['tasks'],'days':len(v['days']),'client':v['client'],'endpoints':sorted(v['eps'])} for k,v in nm(tgt)[:25]]
    dups={'rule':'same endpoint + keyword/target + location + language + device + depth requested more than once on the same UTC day; cost counted for every repeat after the first',
          'cost':R4(dup_cost),'tasks':dup_tasks,
          'byEndpoint':[{'endpoint':k,'repeatTasks':v[0],'cost':R4(v[1])} for k,v in sorted(dup_by.items(),key=lambda x:-x[1][1])[:10]],
          'examples':[{'endpoint':k[0],'request':k[1][:120],'location':k[2],'language':k[3],'date':k[6],'timesRequested':n,'repeatCost':R4(x)} for x,n,k in dup_ex[:10]]}
    return byEndpoint,byClient,tags,byLocation,topTargets,dups
