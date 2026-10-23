"""Merge a Claude Code session (main transcript, persisted tool outputs,
workflow state, subagent transcripts) into one analysable dataset."""
import collections
import csv
import glob
import json
import os
import sys
from datetime import datetime, timezone

PROJ = os.path.expanduser('~/.claude/projects/-home-minervamuses-research-agent-workspace')
SID = sys.argv[1]
OUT = sys.argv[2]
SDIR = os.path.join(PROJ, SID)
os.makedirs(OUT, exist_ok=True)

UKEYS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')


def ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def ms(v):
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


def read_transcript(path):
    """Return API calls (deduped by message id, max usage) plus tool calls/results."""
    calls = collections.OrderedDict()
    tools = {}
    events = []
    for line in open(path):
        d = json.loads(line)
        t = d.get('type')
        if t == 'assistant':
            m = d['message']
            c = calls.setdefault(m['id'], {
                'msg_id': m['id'], 'model': m.get('model'), 'start': d['timestamp'],
                'end': d['timestamp'], 'usage': collections.Counter(), 'thinking': 0,
                'tool_use_ids': [], 'text': '', 'effort': d.get('effort'),
                'stop_reason': None})
            c['end'] = d['timestamp']
            u = m.get('usage') or {}
            for k in UKEYS:
                c['usage'][k] = max(c['usage'][k], u.get(k) or 0)
            c['thinking'] = max(c['thinking'], (u.get('output_tokens_details') or {}).get('thinking_tokens') or 0)
            c['cache_1h'] = (u.get('cache_creation') or {}).get('ephemeral_1h_input_tokens', 0)
            c['stop_reason'] = m.get('stop_reason') or c['stop_reason']
            for b in m['content']:
                if b['type'] == 'tool_use':
                    c['tool_use_ids'].append(b['id'])
                    tools[b['id']] = {'id': b['id'], 'name': b['name'], 'input': b['input'],
                                      'call_ts': d['timestamp'], 'msg_id': m['id']}
                elif b['type'] == 'text':
                    c['text'] += b['text']
                    events.append(('ai_text', d['timestamp'], b['text']))
        elif t == 'user':
            cont = d['message']['content']
            if isinstance(cont, str):
                events.append(('user', d['timestamp'], cont, (d.get('origin') or {}).get('kind')))
                continue
            for b in cont:
                if b.get('type') != 'tool_result':
                    continue
                raw = b.get('content')
                s = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
                r = tools.setdefault(b['tool_use_id'], {'id': b['tool_use_id']})
                r.update(result_ts=d['timestamp'], result_chars=len(s), is_error=bool(b.get('is_error')),
                         result_head=s[:300])
                if '<persisted-output>' in s and 'saved to: ' in s:
                    p = s.split('saved to: ', 1)[1].split('\n', 1)[0].strip()
                    r['persisted_path'] = p
                    r['persisted_chars'] = len(open(p).read()) if os.path.exists(p) else None
    return list(calls.values()), tools, events


def usage_sum(calls):
    tot = collections.Counter()
    for c in calls:
        tot.update(c['usage'])
        tot['thinking_tokens'] += c['thinking']
        tot['api_calls'] += 1
    return tot


def tool_brief(t):
    i = t.get('input') or {}
    if t.get('name') == 'Bash':
        return i.get('description') or i.get('command', '')[:120]
    for k in ('file_path', 'skill', 'scriptPath', 'query', 'task_id', 'prompt'):
        if k in i:
            return f"{k}={str(i[k])[:120]}"
    if 'script' in i:
        return 'inline script ' + str(len(i['script'])) + ' chars'
    return json.dumps(i, ensure_ascii=False)[:120]


# ---------- main transcript ----------
calls, tools, events = read_transcript(os.path.join(PROJ, SID + '.jsonl'))

# Stages of the main conversation, delimited by the first timestamp of each stage
# (derived from reading the condensed timeline).
STAGES = [
    ('2026-10-21T07:34:39', 'S01 載入 skill（workflow-authoring、long-horizon-plan-author）'),
    ('2026-10-21T07:34:47', 'S02 讀計劃檔、build-log、git 歷史'),
    ('2026-10-21T07:35:20', 'S03 協調者親自先驗（重編 dist、Node 測試、pytest）'),
    ('2026-10-21T07:37:00', 'S04 撰寫並啟動 workflow #1（主驗收）'),
    ('2026-10-21T07:42:12', 'S05 等待中讀 phase 檔、回報進度'),
    ('2026-10-21T08:01:50', 'S06 workflow #1 結束 → 撞 session limit #1'),
    ('2026-10-21T12:41:30', 'S07 續跑 #1（resume workflow）'),
    ('2026-10-21T13:37:15', 'S08 讀第一輪結果、親自重現巢狀表格缺陷'),
    ('2026-10-21T14:10:10', 'S09 workflow 結束 → 撞 session limit #2'),
    ('2026-10-21T17:41:30', 'S10 續跑 #2，檢查後中止，改寫補充 workflow #2'),
    ('2026-10-21T18:21:15', 'S11 補充 workflow 組裝失敗 → 修腳本、resume、親自驗 owner flag'),
    ('2026-10-21T19:13:00', 'S12 workflow 結束 → 撞 session limit #3'),
    ('2026-10-22T02:41:10', 'S13 Try again：從 journal 重建結果、啟動 GAP-2 workflow #3'),
    ('2026-10-22T03:24:10', 'S14 統整結果、寫 memory、最終驗收報告'),
]
STAGE_T = [(ts(a + 'Z'), b) for a, b in STAGES]


def stage_of(t):
    t = ts(t) if isinstance(t, str) else t
    cur = STAGE_T[0][1]
    for s, name in STAGE_T:
        if t >= s:
            cur = name
    return cur


main_rows = []
for i, c in enumerate(calls, 1):
    tl = [tools[x] for x in c['tool_use_ids']]
    for t in tl or [None]:
        row = {
            'call_no': i, 'stage': stage_of(c['start']), 'start': c['start'], 'model': c['model'],
            'input': c['usage']['input_tokens'], 'cache_write': c['usage']['cache_creation_input_tokens'],
            'cache_read': c['usage']['cache_read_input_tokens'], 'output': c['usage']['output_tokens'],
            'thinking': c['thinking'], 'text_chars': len(c['text']), 'stop_reason': c['stop_reason'],
            'tool': '', 'tool_brief': '', 'tool_secs': '', 'result_chars': '', 'persisted_chars': '',
            'is_error': '',
        }
        if t:
            row.update(tool=t['name'], tool_brief=tool_brief(t), result_chars=t.get('result_chars', ''),
                       persisted_chars=t.get('persisted_chars') or '', is_error=t.get('is_error', ''))
            if t.get('result_ts'):
                row['tool_secs'] = round((ts(t['result_ts']) - ts(t['call_ts'])).total_seconds(), 1)
            # Only the first tool row of a call carries the call's usage, so sums stay correct.
            if t is not tl[0]:
                for k in ('input', 'cache_write', 'cache_read', 'output', 'thinking'):
                    row[k] = 0
        main_rows.append(row)

with open(os.path.join(OUT, 'main_calls.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(main_rows[0]))
    w.writeheader()
    w.writerows(main_rows)

# ---------- workflows and subagents ----------
wf_rows, agent_rows = [], []
for wf_path in sorted(glob.glob(os.path.join(SDIR, 'workflows', 'wf_*.json'))):
    wf = json.load(open(wf_path))
    run_id = wf['runId']
    jdir = os.path.join(SDIR, 'subagents', 'workflows', run_id)
    outcome, label_by_id = {}, {}
    for line in open(os.path.join(jdir, 'journal.jsonl')):
        e = json.loads(line)
        if e.get('agentId'):
            if e['type'] == 'started':
                label_by_id[e['agentId']] = (e.get('label'), e.get('phase'))
            elif e['type'] in ('result', 'failed'):
                outcome[e['agentId']] = e['type']
    for ap in sorted(glob.glob(os.path.join(jdir, 'agent-*.jsonl'))):
        aid = os.path.basename(ap)[6:-6]
        meta = json.load(open(ap[:-6] + '.meta.json')) if os.path.exists(ap[:-6] + '.meta.json') else {}
        a_calls, a_tools, _ = read_transcript(ap)
        u = usage_sum(a_calls)
        tc = collections.Counter(t['name'] for t in a_tools.values() if 'name' in t)
        label, phase = label_by_id.get(aid, (meta.get('description'), meta.get('workflowPhase')))
        agent_rows.append({
            'workflow': wf['workflowName'], 'run_id': run_id, 'agent_id': aid,
            'label': label or meta.get('description'), 'phase': phase or meta.get('workflowPhase'),
            'model': ','.join(sorted({c['model'] for c in a_calls if c['model']})),
            'outcome': outcome.get(aid, 'unknown'),
            'start': a_calls[0]['start'] if a_calls else '', 'end': a_calls[-1]['end'] if a_calls else '',
            'minutes': round((ts(a_calls[-1]['end']) - ts(a_calls[0]['start'])).total_seconds() / 60, 1) if a_calls else 0,
            'api_calls': u['api_calls'], 'tool_calls': sum(tc.values()),
            'top_tools': ' '.join(f'{k}:{v}' for k, v in tc.most_common(4)),
            'input': u['input_tokens'], 'cache_write': u['cache_creation_input_tokens'],
            'cache_read': u['cache_read_input_tokens'], 'output': u['output_tokens'],
            'thinking': u['thinking_tokens'],
        })
    wf_rows.append({
        'run_id': run_id, 'name': wf['workflowName'], 'status': wf.get('status'),
        'reported_agentCount': wf.get('agentCount'), 'reported_totalTokens': wf.get('totalTokens'),
        'reported_totalToolCalls': wf.get('totalToolCalls'), 'durationMs_last_run': wf.get('durationMs'),
        'phases': ' → '.join(p['title'] for p in wf.get('phases') or []),
        'summary': wf.get('summary'),
    })

with open(os.path.join(OUT, 'subagents.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(agent_rows[0]))
    w.writeheader()
    w.writerows(agent_rows)

json.dump({'workflows': wf_rows, 'main_usage': usage_sum(calls), 'stages': STAGES},
          open(os.path.join(OUT, 'summary.json'), 'w'), ensure_ascii=False, indent=1, default=dict)
print(len(main_rows), 'main rows;', len(agent_rows), 'agent rows')
