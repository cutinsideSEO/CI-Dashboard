import json,glob,os,collections,pickle
W=__import__('os').environ.get('DFS_DIR','dfs-work')+'/raw'
C=__import__('os').environ.get('DFS_DIR','dfs-work')+'/cache.pkl'
def load():
    files=sorted(glob.glob(W+'/id_*.json'))
    if os.path.exists(C):
        rows,meta_by_id,fl=pickle.load(open(C,'rb'))
        if fl==files: return rows,meta_by_id,files
    rows={}; meta_by_id={}
    for f in files:
        d=json.load(open(f)); tk=d['tasks'][0]; api=tk['data']['api']
        for r in tk.get('result') or []:
            k=(api,r['id'],r['datetime_posted'])
            if k not in rows or (rows[k].get('metadata') is None and r.get('metadata')):
                rows[k]=dict(r,api=api)
            if r.get('metadata'): meta_by_id[r['id']]=r['metadata']
    for r in rows.values(): r.pop('metadata',None)
    pickle.dump((rows,meta_by_id,files),open(C,'wb'))
    return rows,meta_by_id,files
