"""Plan or resume A -> B candidate generation. Originals and training captions stay untouched."""
import argparse
import hashlib
import json
import sys
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
import os
from contextlib import contextmanager
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXTENSIONS={'.png','.jpg','.jpeg','.webp','.bmp'}


@contextmanager
def run_lock(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with (output/'.batch.lock').open('a+b') as stream:
        if stream.tell()==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    temp.replace(path)


def plan(source,identity,output,description,scope='identity_only',resolution=512,opacity=0.,seed=21003,scene_descriptions=None):
    source,identity,output=Path(source).resolve(),Path(identity).resolve(),Path(output).resolve()
    if not source.is_dir() or not identity.is_file():raise ValueError('Source directory / identity image does not exist')
    if output==source or source in output.parents:raise ValueError('Keep the output directory outside the source dataset')
    if not description.strip():raise ValueError('Describe B identity (face / hair / body); omit B clothing in identity_only mode')
    descriptions={}
    if scene_descriptions is not None:
        descriptions=json.loads(Path(scene_descriptions).read_text(encoding='utf-8-sig'))
        if not isinstance(descriptions,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in descriptions.items()):
            raise ValueError('Scene descriptions must map relative source filenames to clothing/pose/scene text')
    config={'source':str(source),'identity':str(identity),'identity_sha256':digest(identity),
            'identity_description':description,'identity_scope':scope,'resolution':resolution,
            'reference_opacity':opacity,'seed':seed,'control_strength':.25,'control_end':.6,
            'scene_descriptions':descriptions}
    path=output/'manifest.json'
    if path.exists():
        manifest=json.loads(path.read_text(encoding='utf-8'))
        if manifest['config']!=config:raise ValueError('Run settings changed; use a new output directory to keep provenance unambiguous')
        return manifest
    if output.exists() and any(p.name!='.batch.lock' for p in output.iterdir()):raise ValueError('Use an empty output directory or an existing batch manifest')
    jobs=[]
    for file in sorted(source.rglob('*')):
        if file.suffix.lower() not in EXTENSIONS or not file.is_file() or file.resolve()==identity:continue
        relative=file.relative_to(source).as_posix();sha=digest(file)
        key=hashlib.sha256((relative+'\0'+sha).encode()).hexdigest()[:20]
        jobs.append({'id':key,'source':str(file),'relative_source':relative,'source_sha256':sha,
                     'seed':(seed+int(key[:8],16))%(2**63),'status':'planned','review_status':'pending',
                     'scene_description':descriptions.get(relative,'')})
    if not jobs:raise ValueError('No source images found')
    manifest={'version':1,'run_id':uuid.uuid4().hex[:16],'config':config,'jobs':jobs,
              'note':'Generated candidates require identity, clothing, pose and artifact review. No training captions are inferred.'}
    save(path,manifest)
    return manifest


class Client:
    def __init__(self,url):self.url=url.rstrip('/')
    def request(self,path,data=None):
        request=urllib.request.Request(self.url+path,None if data is None else json.dumps(data).encode(),{'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
        except urllib.error.HTTPError as error:raise RuntimeError(error.read().decode()) from error
    def idle(self):
        queue=self.request('/queue')
        if queue['queue_running'] or queue['queue_pending']:raise RuntimeError('ComfyUI queue is busy; resume after it is idle')
    def upload(self,path,name,run_id):
        boundary='jr'+uuid.uuid4().hex
        fields={'type':'input','subfolder':'JR_Director_Batch/'+run_id,'overwrite':'false'}
        body=b''
        for field,value in fields.items():
            body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{value}\r\n'.encode()
        body+=f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        body+=Path(path).read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
        request=urllib.request.Request(self.url+'/upload/image',body,{'Content-Type':'multipart/form-data; boundary='+boundary})
        with urllib.request.urlopen(request,timeout=60) as response:result=json.load(response)
        return (result.get('subfolder','')+'/'+result['name']).lstrip('/')
    def wait(self,pid):
        start=time.monotonic();last=-1
        while time.monotonic()-start<1800:
            record=self.request('/history/'+urllib.parse.quote(pid,safe='')).get(pid)
            if record:
                if record['status']['status_str']=='error':raise RuntimeError(json.dumps(record['status']))
                if record['status']['completed']:return record
            queue=self.request('/queue')
            if not any(row[1]==pid for row in queue['queue_running']+queue['queue_pending']):
                # Completion can happen between the history and queue requests.
                record=self.request('/history/'+urllib.parse.quote(pid,safe='')).get(pid)
                if record:
                    if record['status']['status_str']=='error':raise RuntimeError(json.dumps(record['status']))
                    if record['status']['completed']:return record
                raise RuntimeError('Recorded prompt is absent from queue/history; inspect it before retrying. Not resubmitting automatically.')
            tick=int((time.monotonic()-start)/30)
            if tick!=last:print('Waiting for',pid,tick*30,'seconds',flush=True);last=tick
            time.sleep(2)
        raise TimeoutError('Prompt may still be running; rerun the same batch command to resume')


def graph_for(job,config,identity_name,source_name,state,run_id):
    graph=json.loads((ROOT/'examples/qwen21_director_replace_person_api.json').read_text(encoding='utf-8'))
    graph['5']['inputs']['image']=source_name
    graph['12']['inputs']['image']=identity_name
    graph['6']['inputs'].update(director_state=json.dumps(state),width=state['render']['width'],height=state['render']['height'],
        task_mode='replace_person',identity_scope=config['identity_scope'],pose_image_reference=False,
        reference_opacity=config['reference_opacity'],control_strength=config['control_strength'],control_end=config['control_end'],
        prompt_prefix='The replacement identity from <image1> is: '+config['identity_description'].strip(),prompt_suffix='')
    graph['7']['inputs']['resolution']=0
    if job.get('scene_description'):
        graph['6']['inputs']['prompt_prefix']+='\nPreserve from <image2>: '+job['scene_description'].strip()
    graph['7']['inputs'].pop('images.image_3',None)
    graph['8']['inputs']['seed']=job['seed']
    graph['10']['inputs']['filename_prefix']=f'JR_Director_Batch/{run_id}/{job["id"]}'
    return graph


def run(manifest,output,url,pose_models,limit=None):
    import numpy as np
    from PIL import Image,ImageOps
    sys.path.insert(0,str(ROOT))
    from director.detection import PoseDetector
    from director.pose_import import fit_pose
    from director.state import default_state
    output=Path(output).resolve();config=manifest['config'];client=Client(url);detector=None
    manifest_path=output/'manifest.json';processed=0
    for job in manifest['jobs']:
        if job['status']=='generated_pending_review':
            candidate=output/'pending'/f'{job["id"]}.png'
            if not candidate.is_file() or digest(candidate)!=job['output_sha256']:
                raise RuntimeError('A generated candidate is missing or changed; preserve the manifest and inspect before resuming')
            continue
        if job['status'] in ('needs_review','failed'):continue
        if limit is not None and processed>=limit:break
        processed+=1
        if digest(job['source'])!=job['source_sha256']:raise RuntimeError('Source image changed; create a new run')
        if not job.get('prompt_id'):
            client.idle()
            if 'fit' not in job:
                if detector is None:detector=PoseDetector([pose_models])
                with Image.open(job['source']) as image:
                    image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1024,1024))
                    rgb=np.asarray(image)
                people=detector(rgb)
                if len(people)!=1:
                    job.update(status='needs_review',reason=f'Expected one target person, detected {len(people)}. Choose/crop the target manually.')
                    save(manifest_path,manifest);continue
                base=default_state();base['render'].update(width=config['resolution'],height=config['resolution'])
                try:fit=fit_pose(people[0]['keypoints'],rgb.shape[1],rgb.shape[0],base)
                except ValueError as error:
                    job.update(status='needs_review',reason=str(error));save(manifest_path,manifest);continue
                job['fit']=fit
                if fit['fit_error_pixels']/max(rgb.shape[:2])>.05:
                    job.update(status='needs_review',reason='Pose fit error exceeds 5% of source long edge')
                    save(manifest_path,manifest);continue
            identity_name=client.upload(config['identity'],'identity_'+config['identity_sha256'][:16]+Path(config['identity']).suffix,manifest['run_id'])
            source_name=client.upload(job['source'],job['id']+Path(job['source']).suffix,manifest['run_id'])
            graph=graph_for(job,config,identity_name,source_name,job['fit']['state'],manifest['run_id'])
            save(output/'prompts'/f'{job["id"]}.json',graph)
            # Persist before dispatch. An uncertain HTTP failure stops rather than silently duplicating a job.
            job.update(status='submitting',submitted_graph=str(output/'prompts'/f'{job["id"]}.json'))
            save(manifest_path,manifest)
            response=client.request('/prompt',{'prompt':graph,'client_id':'jr-dataset-'+manifest['run_id']})
            job.update(status='queued',prompt_id=response['prompt_id']);save(manifest_path,manifest)
        print('Processing',job['relative_source'],job['prompt_id'],flush=True)
        record=client.wait(job['prompt_id'])
        save(output/'history'/f'{job["id"]}.json',record)
        images=record.get('outputs',{}).get('10',{}).get('images',[])
        if len(images)!=1:raise RuntimeError('Expected one saved image for this batch job')
        query=urllib.parse.urlencode({k:images[0][k] for k in ('filename','subfolder','type')})
        path=output/'pending'/f'{job["id"]}.png';path.parent.mkdir(exist_ok=True)
        with urllib.request.urlopen(client.url+'/view?'+query,timeout=60) as response:data=response.read()
        temp=path.with_suffix('.download');temp.write_bytes(data)
        with Image.open(temp) as image:
            image.verify()
        temp.replace(path)
        job.update(status='generated_pending_review',output=str(path),output_sha256=digest(path),review_status='pending')
        save(output/'pending'/f'{job["id"]}.json',{'source':job['relative_source'],'source_sha256':job['source_sha256'],
            'identity_sha256':config['identity_sha256'],'identity_scope':config['identity_scope'],'seed':job['seed'],
            'prompt_id':job['prompt_id'],'review_status':'pending','pose_fit':job['fit']})
        save(manifest_path,manifest)
        print('Pending review:',path,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',required=True,type=Path)
    p.add_argument('--identity-image',required=True,type=Path)
    p.add_argument('--identity-description',required=True)
    p.add_argument('--scene-descriptions',type=Path,help='Optional reviewed JSON mapping relative A filenames to clothing / action / scene descriptions; do not include A identity')
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--identity-scope',choices=['identity_only','full_appearance'],default='identity_only')
    p.add_argument('--resolution',type=int,default=512,choices=range(256,2049,32))
    p.add_argument('--reference-opacity',type=float,default=0.)
    p.add_argument('--seed',type=int,default=21003)
    p.add_argument('--run',action='store_true',help='Without this flag, only prepare the manifest; no upload or inference')
    p.add_argument('--pose-models',type=Path,help='Directory containing yolox_l.onnx and dw-ll_ucoco_384.onnx')
    p.add_argument('--url',default='http://127.0.0.1:8188')
    p.add_argument('--limit',type=int,help='Maximum new/resumed jobs in this invocation')
    args=p.parse_args()
    if not 0<=args.reference_opacity<=.1:raise ValueError('Opacity must be 0..0.1')
    if args.limit is not None and args.limit<1:raise ValueError('limit must be positive')
    source_path,output_path=args.source_dir.resolve(),args.output_dir.resolve()
    if output_path==source_path or source_path in output_path.parents:raise ValueError('Keep output outside the source dataset')
    with run_lock(args.output_dir):
        manifest=plan(args.source_dir,args.identity_image,args.output_dir,args.identity_description,args.identity_scope,args.resolution,args.reference_opacity,args.seed,args.scene_descriptions)
        print(len(manifest['jobs']),'source images;',args.output_dir/'manifest.json',flush=True)
        if args.run:
            if any(j['status']=='submitting' and not j.get('prompt_id') for j in manifest['jobs']):
                raise RuntimeError('An earlier submission has uncertain status. Inspect the ComfyUI queue/history before editing the manifest; not resubmitting.')
            if args.pose_models is None:raise ValueError('--run requires --pose-models')
            run(manifest,args.output_dir,args.url,args.pose_models,args.limit)


if __name__=='__main__':main()
