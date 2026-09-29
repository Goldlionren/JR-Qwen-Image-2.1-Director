"""Run a saved API graph on an idle local ComfyUI and retain the exact request/history."""
import argparse
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('graph',type=Path)
p.add_argument('--tag',required=True)
p.add_argument('--url',default='http://127.0.0.1:8188')
args=p.parse_args()
if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.tag):raise ValueError('Use a filename-safe tag')

def request(path,data=None):
    req=urllib.request.Request(args.url+path,None if data is None else json.dumps(data).encode(),{'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
    except urllib.error.HTTPError as error:raise RuntimeError(error.read().decode()) from error

queue=request('/queue')
if queue['queue_running'] or queue['queue_pending']:raise RuntimeError('Queue busy; no test submitted')
graph=json.loads(args.graph.read_text(encoding='utf-8'))
record_dir=Path('.local');record_dir.mkdir(exist_ok=True)
start=time.monotonic()
pid=request('/prompt',{'prompt':graph,'client_id':'jr-director-scenario-test'})['prompt_id']
(record_dir/(args.tag+'-request.json')).write_text(json.dumps({'prompt_id':pid,'graph':graph},indent=2),encoding='utf-8')
print('Queued',pid,flush=True)
last=-1
while time.monotonic()-start<1200:
    record=request('/history/'+pid).get(pid)
    if record:
        (record_dir/(args.tag+'-history.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
        if record['status']['status_str']=='error':raise RuntimeError(record['status'])
        if record['status']['completed']:
            elapsed=round(time.monotonic()-start,2)
            (record_dir/(args.tag+'-metrics.json')).write_text(json.dumps({'elapsed_seconds':elapsed}),encoding='utf-8')
            print('Completed',elapsed,record['outputs'],flush=True);break
    tick=int((time.monotonic()-start)/30)
    if tick!=last:print('Waiting',tick*30,'seconds',flush=True);last=tick
    time.sleep(2)
else:raise TimeoutError('Prompt may still be running; check recorded prompt ID before retrying')
