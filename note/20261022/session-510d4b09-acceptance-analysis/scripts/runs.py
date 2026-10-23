import csv,json,sys,glob,collections,os
O=sys.argv[1]; SD=os.path.expanduser('~/.claude/projects/-home-minervamuses-research-agent-workspace/510d4b09-c6f3-4a71-b1c6-7887a26ab77a')
K=('input','cache_write','cache_read','output')
B=[('2026-10-21T07:41','R1 wf#1 首跑'),('2026-10-21T12:41','R2 wf#1 續跑#1'),('2026-10-21T17:41','R3 wf#1 續跑#2(中止)'),('2026-10-21T17:55','R4 wf#2 補充首跑'),('2026-10-21T18:21','R5 wf#2 resume'),('2026-10-22T02:42','R6 wf#3 GAP-2')]
def run(s):
    cur='?'
    for b,n in B:
        if s>=b: cur=n
    return cur
# verdicts / summaries from journals
res={}
for j in glob.glob(SD+'/subagents/workflows/*/journal.jsonl'):
    for l in open(j):
        e=json.loads(l)
        if e['type']=='result':
            r=e.get('result') or {}
            res[e['agentId']]=r
a=list(csv.DictReader(open(O+'/subagents.csv')))
a.sort(key=lambda r:r['start'] or '9')
seen=collections.defaultdict(list)
for r in a:
    r['run']=run(r['start']) if r['start'] else run('2026-10-21T17:54')  # synthetic-only
    r['total']=sum(int(r[k]) for k in K)
    rr=res.get(r['agent_id']) or {}
    r['verdict']=rr.get('verdict') or rr.get('status') or ''
    r['severity']=rr.get('severity') or rr.get('corrected_severity') or ''
    r['n_findings']=len(rr.get('findings') or []) if isinstance(rr,dict) else ''
    r['result_summary']=(rr.get('summary') or rr.get('reason') or rr.get('rationale') or '')[:300] if isinstance(rr,dict) else ''
    key=(r['workflow'],r['label'])
    r['attempt']=len(seen[key])+1
    r['prior_outcomes']='/'.join(x['outcome'] for x in seen[key])
    seen[key].append(r)
print('result keys sample',[list(v.keys()) for v in list(res.values())[:3]])
with open(O+'/subagents_detail.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(a[0])); w.writeheader(); w.writerows(a)
# run table
g=collections.OrderedDict()
for r in a:
    x=g.setdefault(r['run'],{'n':0,'ok':0,'fail':0,'unk':0,'tok':0,'out':0,'fail_tok':0,'start':'9','end':'0','rerun_of_ok':0,'rerun_tok':0,'tools':0})
    x['n']+=1; x['tok']+=r['total']; x['out']+=int(r['output']); x['tools']+=int(r['tool_calls'])
    x[{'result':'ok','failed':'fail'}.get(r['outcome'],'unk')]+=1
    if r['outcome']!='result': x['fail_tok']+=r['total']
    if 'result' in r['prior_outcomes'].split('/'): x['rerun_of_ok']+=1; x['rerun_tok']+=r['total']
    if r['start']: x['start']=min(x['start'],r['start']); x['end']=max(x['end'],r['end'])
for k,x in g.items(): print(k,x)
print('\nre-runs of already-successful labels:')
for r in a:
    if 'result' in r['prior_outcomes'].split('/'): print(' ',r['run'],r['label'],r['outcome'],r['total'])
print('\nkilled R3 agents:'); [print(' ',r['label'],r['minutes'],r['total']) for r in a if r['run'].startswith('R3')]
print('\nfailed agents:'); [print(' ',r['run'],r['label'],r['minutes'],'min',r['total'],r['end'][11:19]) for r in a if r['outcome']=='failed']
