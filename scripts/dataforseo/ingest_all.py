import json, os, glob
T=__import__('os').environ['DFS_TOOL_RESULTS']
W=__import__('os').environ.get('DFS_DIR','dfs-work')+'/raw'
seenf=os.path.join(W,'_seen.json')
seen=set(json.load(open(seenf))) if os.path.exists(seenf) else set()
for f in sorted(glob.glob(T+'/mcp-DataForSEO-api_request-*.txt')):
    b=os.path.basename(f)
    if b in seen: continue
    t=open(f).read()
    try: d=json.loads(t[t.index('{'):])
    except Exception as e: print('skip',b,e); continue
    tk=d['tasks'][0]; da=tk['data']
    if da.get('function')!='id_list': seen.add(b); continue
    name='%s__%s__%s__%s__o%s__m%d'%(da['api'],da.get('sort','asc'),da['datetime_from'][:19].replace(' ','T').replace(':',''),da['datetime_to'][:19].replace(' ','T').replace(':',''),da.get('offset',0),1 if da.get('include_metadata') else 0)
    json.dump(d,open(os.path.join(W,'id_'+name+'.json'),'w'))
    res=tk.get('result') or []
    print(name.replace('__2026-','|').replace('__m0',''), tk['status_code'] if tk['status_code']!=20000 else '', len(res), (res[0]['datetime_posted'][5:19]+'>'+res[-1]['datetime_posted'][5:19]) if res else '', round(sum(r.get('cost') or 0 for r in res),3) if res else '')
    seen.add(b)
json.dump(sorted(seen),open(seenf,'w'))
# pacing: ensure >= 62s between ingest runs (10 calls per cycle => <=10 calls/min)
import time
tf=os.path.join(W,'_last.txt')
try: last=float(open(tf).read())
except Exception: last=0
wait=62-(time.time()-last)
if 0<wait<62: time.sleep(wait)
open(tf,'w').write(str(time.time()))
