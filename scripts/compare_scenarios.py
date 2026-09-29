"""Generate / sequentially run controlled scenario comparisons on an idle ComfyUI.

Each invocation has its own record directory. No source or example is overwritten.
"""
import argparse
import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    's1_bundled': dict(mode='edit_pose', backend='bundled'),
    's1_official': dict(mode='edit_pose'),
    's1_cfg3': dict(mode='edit_pose', cfg=3),
    's1_strong': dict(mode='edit_pose', cfg=3, strength=.65),
    's2_bundled': dict(backend='bundled'),
    's2_official': dict(),
    's2_cfg3': dict(cfg=3),
    's2_zero_overlay': dict(cfg=3, opacity=0),
    's2_ten_overlay': dict(cfg=3, opacity=.1),
    's2_no_control': dict(cfg=3, strength=0, opacity=0),
    's2_strong': dict(cfg=3, strength=.65, opacity=0),
    's2_reverse': dict(cfg=3, opacity=0, reverse=True),
    's2_reverse_no_control': dict(cfg=3, opacity=0, strength=0, reverse=True),
    's2_anyangle': dict(cfg=3, opacity=0, lora=.5),
    's2_head': dict(cfg=3, opacity=0, head=True),
    's2_head_extra': dict(cfg=3, opacity=0, head='extra'),
    's2_dress': dict(cfg=3, opacity=.05, dress=True),
    's2_depth': dict(cfg=3, opacity=0, depth='only'),
    's2_pose_depth': dict(cfg=3, opacity=0, depth='both'),
    's2_auto': dict(cfg=1, auto=True, backend='native_internal'),
    's2_auto_cfg3': dict(cfg=3, auto=True, backend='native_internal'),
    's2_auto_depth': dict(cfg=1, auto=True, depth='only'),
    's2_auto_pose_depth': dict(cfg=1, auto=True, depth='both'),
    's2_auto_native_depth': dict(cfg=3, auto=True, backend='native_internal',native_depth=True),
    's2_auto_standing': dict(cfg=3, auto=True, backend='native_internal',standing=True),
    's2_auto_zero': dict(cfg=3, auto=True, backend='native_internal',opacity=0),
    's2_auto_ten': dict(cfg=3, auto=True, backend='native_internal',opacity=.1),
}


def graph_for(options, prefix, seed):
    mode = options.get('mode', 'replace_person')
    graph = json.loads((ROOT/f'examples/qwen21_director_{mode}_api.json').read_text(encoding='utf-8'))
    d = graph['6']['inputs']
    d['auto_describe'] = bool(options.get('auto'))
    if options.get('auto'):
        d.update(auto_describe=True,clip=['3',0])
    else:
        d.pop('clip',None)
    if options.get('native_depth'):
        d.update(depth_model='depth_anything_v2_vitl_fp16.safetensors',depth_strength=.25)
    if options.get('standing'):
        original=json.loads((ROOT/'examples/scenarios/edit_pose-import.json').read_text(encoding='utf-8'))
        d['director_state']=json.dumps(original['state'])
        graph['5']['inputs']['image']='jr_director_classroom_source.png'
    strength = options.get('strength', .25)
    d['reference_opacity'] = options.get('opacity', d['reference_opacity'])
    model = ['6',6]
    if options.get('backend') not in ('bundled','native_internal'):
        # Leave the selected name in place to keep exactly the same prompt logic,
        # but bypass the bundled patch. The official node receives its same hint.
        d['control_strength'] = 0
        if strength:
            graph['20'] = {'class_type':'ModelPatchLoader','inputs':{'name':'qwen_image_2.1_fun_controlnet_union_int8_convrot.safetensors'}}
            graph['21'] = {'class_type':'ZImageFunControlnet','inputs':dict(model=model,model_patch=['20',0],vae=['4',0],image=['6',7],strength=strength,start_percent=0,end_percent=.6)}
            model = ['21',0]
    else:
        d['control_strength'] = strength
        d['control_backend'] = 'native' if options.get('backend') == 'native_internal' else 'bundled'
    if options.get('depth'):
        graph['24']={'class_type':'LoadImage','inputs':{'image':'jr_director_scene2_depth.png'}}
        if options['depth']=='only':
            graph['21']['inputs']['image']=['24',0]
        else:
            graph['25']={'class_type':'ZImageFunControlnet','inputs':dict(model=model,model_patch=['20',0],vae=['4',0],image=['24',0],strength=.25,start_percent=0,end_percent=.6)}
            model=['25',0]
    if options.get('dress'):
        graph['7']['inputs']['prompt']='Dress the person from <image1> in the complete outfit worn by the person in <image2>, including clothing, shoes and clothing accessories. Place this person in the scene of <image2>, replacing the original person. Keep the face, hairstyle and body build from <image1>. Match the target pose control, position, framing, background and lighting of <image2>. Fit the clothes naturally to the replacement body. Preserve unrelated people and objects.'
    if options.get('lora'):
        graph['22'] = {'class_type':'LoraLoaderModelOnly','inputs':dict(model=model,lora_name='QI2.1_AnyAngle.safetensors',strength_model=options['lora'])}
        model = ['22',0]
    if options.get('head'):
        graph['23'] = {'class_type':'ImageCrop','inputs':dict(image=['12',0],width=144,height=128,x=184,y=16)}
        if options['head']=='extra':
            graph['7']['inputs']['images.image_3']=['23',0]
            d['prompt_suffix']='Use <image3> as the close-up reference for the replacement face and hairstyle from <image1>. Keep clothing from <image2>.'
        else:
            d['identity_image']=['23',0]
    if options.get('reverse'):
        graph['7']['inputs'].update({'images.image_1':['6',9],'images.image_2':['6',8]})
        # Same macro instructions, with the two image roles consistently swapped.
        sys.path.insert(0,str(ROOT))
        from director.prompt import build_prompt
        from director.state import parse_state
        prompt = build_prompt(parse_state(d['director_state']),task_mode=mode,controlnet=True)[0]
        graph['7']['inputs']['prompt'] = prompt.replace('<image1>','<TEMP>').replace('<image2>','<image1>').replace('<TEMP>','<image2>')
    graph['8']['inputs'].update(model=model,cfg=options.get('cfg',1),seed=seed)
    graph['10']['inputs']['filename_prefix'] = prefix
    return graph


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',nargs='+',choices=list(CASES),required=True)
    parser.add_argument('--seed',type=int,default=21003)
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    run=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    directory=ROOT/'.local'/'scenario-matrix'/run;directory.mkdir(parents=True)
    manifest={'run':run,'seed':args.seed,'cases':{}}
    for name in args.cases:
        graph=graph_for(copy.deepcopy(CASES[name]),f'JR_Director_Compare/{run}/{name}',args.seed)
        path=directory/(name+'.json');path.write_text(json.dumps(graph,indent=2),encoding='utf-8')
        manifest['cases'][name]={'options':CASES[name],'graph':str(path),'tag':run+'-'+name}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Records:',directory,flush=True)
    if args.run:
        for name,case in manifest['cases'].items():
            print('CASE',name,flush=True)
            subprocess.run([sys.executable,str(ROOT/'scripts/run_api_example.py'),case['graph'],'--tag',case['tag']],cwd=ROOT,check=True)


if __name__=='__main__':main()
