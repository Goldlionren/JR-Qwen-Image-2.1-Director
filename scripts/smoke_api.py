"""Run deterministic model-free cases through an existing ComfyUI queue."""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from director.state import default_state, apply_preset

p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8188');args=p.parse_args()
def request(path,payload=None):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(args.url+path,data,{'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
results=[]
for label,az,pose in [('front',0,'Neutral Standing'),('right',90,'Neutral Standing'),('back',180,'Neutral Standing'),('left',270,'Neutral Standing'),('quarter',45,'Neutral Standing'),('raised',0,'Right Arm Raised'),('walking',45,'Walking'),('asymmetric',45,'Asymmetric')]:
    s=apply_preset(default_state(),pose);s['camera']['azimuth']=az
    graph={'1':{'class_type':'QwenImage21Director','inputs':{'director_state':json.dumps(s),'width':512,'height':512,'subject_type':'character','background_mode':'preserve','framing':'auto'}},
           '2':{'class_type':'PreviewImage','inputs':{'images':['1',1]}},
           '3':{'class_type':'PreviewImage','inputs':{'images':['1',2]}}}
    response=request('/prompt',{'prompt':graph,'client_id':'qwen-director-smoke'})
    pid=response['prompt_id'];deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        history=request('/history/'+pid).get(pid)
        if history and history['status']['completed']:break
        if history and history['status']['status_str']=='error':raise RuntimeError(history)
        time.sleep(.25)
    else:raise TimeoutError(pid)
    images=history['outputs']['2']['images']
    print(label,history['status']['status_str'],images,flush=True)
    results.append({'case':label,'prompt_id':pid,'status':history['status'],'outputs':history['outputs']})
Path('.local').mkdir(exist_ok=True)
Path('.local/smoke-results.json').write_text(json.dumps(results,indent=2))
