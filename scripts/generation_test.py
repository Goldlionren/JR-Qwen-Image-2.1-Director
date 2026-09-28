"""Run a local Qwen smoke render; record provenance without touching existing workflows."""
import argparse
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8188')
p.add_argument('--reference',help='Existing ComfyUI input filename. Omit to generate a fully clothed toy reference.')
p.add_argument('--case',default='reference');p.add_argument('--steps',type=int,default=12)
p.add_argument('--resolution',type=int,default=512);args=p.parse_args()
def request(path,payload=None):
    req=urllib.request.Request(args.url+path,None if payload is None else json.dumps(payload).encode(),{'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(e.read().decode()) from e
queue=request('/queue')
if queue['queue_running'] or queue['queue_pending']:raise RuntimeError('Existing queue is busy; no test submitted')
graph=json.loads(Path('examples/qwen21_director_api.json').read_text())
graph['7']['inputs']['resolution']=args.resolution
graph['8']['inputs']['steps']=args.steps
graph['10']['inputs']['filename_prefix']='Qwen21Director_test/'+args.case
if not args.reference:
    del graph['5'];del graph['6'];graph['7']['inputs'].pop('images.image_1');graph['7']['inputs'].pop('images.image_2')
    graph['7']['inputs']['prompt']='Full body studio character reference, one adult stylized wooden explorer toy, short dark hair, round glasses, teal zipped jacket, bright orange scarf, brown trousers and dark boots. Standing upright facing the camera, arms relaxed down, both feet visible. Neutral friendly expression. Plain white background, high quality 3D animation style, clean shapes, centered full body, no text.'
else:
    graph['5']['inputs']['image']=args.reference
    s=json.loads(graph['6']['inputs']['director_state'])
    if args.case=='right':s['camera']['azimuth']=90
    elif args.case=='back':s['camera']['azimuth']=180
    elif args.case=='quarter':s['camera']['azimuth']=45
    elif args.case in ('raised','walking','walking-quarter','asymmetric'):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
        from director.state import apply_preset
        s=apply_preset(s,{'raised':'Right Arm Raised','walking':'Walking','walking-quarter':'Walking','asymmetric':'Asymmetric'}[args.case])
        if args.case=='walking-quarter':s['camera']['azimuth']=45
    graph['6']['inputs'].update(director_state=json.dumps(s),width=args.resolution,height=args.resolution)
response=request('/prompt',{'prompt':graph,'client_id':'qwen-director-generation-test'})
pid=response['prompt_id'];print('Queued',pid,'case',args.case,flush=True)
Path('.local').mkdir(exist_ok=True)
Path('.local/generation-'+args.case+'-request.json').write_text(json.dumps({'prompt_id':pid,'graph':graph},indent=2))
start=time.monotonic();last=-1
while time.monotonic()-start<1200:
    record=request('/history/'+pid).get(pid)
    if record:
        Path('.local/generation-'+args.case+'-result.json').write_text(json.dumps(record,indent=2))
        if record['status']['status_str']=='error':raise RuntimeError(record['status'])
        if record['status']['completed']:
            print('Completed',round(time.monotonic()-start,1),'seconds',record['outputs'],flush=True);break
    elapsed=int((time.monotonic()-start)/30)
    if elapsed!=last:print('Waiting',elapsed*30,'seconds',flush=True);last=elapsed
    time.sleep(2)
else:raise TimeoutError('Test remains queued/running; inspect prompt_id before retrying')
