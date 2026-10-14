import sys,json
sys.path.insert(0,__import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import analyze as A
bE,bC,tg,bL,tt,du=A.build()
print('MED30',A.MED30,'avg7',A.avg7,'avg30',A.avg30,'proj',A.proj,'octmtd',A.oct_mtd,'last30',A.last_total,'today',A.today)
print('pos',A.out['pos_total'],'neg',A.out['neg_total'])
for m in A.monthly: print(m['month'],m['cost'],m['tasks'])
for x in bE[:8]: print(x)
for x in bC[:16]: print(x['client'],x['cost'],x['tasks'],x['share'])
for x in tg[:6]: print({k:v for k,v in x.items() if k!='top'})
print(du['cost'],du['tasks'],du['byEndpoint'][:4])
# baseline: daily 03:00 tracker cost per day last 7
import collections
b=collections.Counter()
for r in A.pos:
    if r['datetime_posted'][:10]>='2026-10-07' and r['datetime_posted'][11:13] in('03',): b[r['datetime_posted'][:10]]+=r['cost']
print('03h cost',dict(b))
# US batch per week
w=collections.Counter()
for r in A.L:
    if r['cost']>0 and A.client_of(r)[0].startswith('(unattributed) US'): w[r['datetime_posted'][:10]]+=r['cost']
print('USbatch by day',{k:round(v,2) for k,v in sorted(w.items()) if v>0.5})
