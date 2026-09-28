"""Create separate examples from a local Qwen workflow without modifying its source."""
import argparse
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from director.state import default_state

p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--reference',default='example.png')
args=p.parse_args()
state=default_state()
def director_node(node_id=21,pos=(-900,40)):
    return {'id':node_id,'type':'QwenImage21Director','pos':list(pos),'size':[750,1100],
            'flags':{},'order':0,'mode':0,'inputs':[{'name':'image','type':'IMAGE','link':None}],
            'outputs':[{'name':n,'type':t,'links':[]} for n,t in [('director_prompt','STRING'),('pose_control','IMAGE'),('pose_preview','IMAGE'),('camera_info','STRING'),('pose_text','STRING'),('director_state','STRING')]],
            'properties':{'Node name for S&R':'QwenImage21Director'},
            'widgets_values':[json.dumps(state),1024,1024,'character','plain white','auto','','']}
def preview_node(node_id=22,pos=(800,650)):
    return {'id':node_id,'type':'PreviewImage','pos':list(pos),'size':[380,400],'flags':{},'order':1,'mode':0,
            'inputs':[{'name':'images','type':'IMAGE','link':23}], 'outputs':[], 'properties':{'Node name for S&R':'PreviewImage'}}

base=json.loads(args.source.read_text(encoding='utf-8'))
base['nodes']=[n for n in base['nodes'] if n['id'] not in range(12,21)]
base['links']=[l for l in base['links'] if l[0] not in range(3,12)]
encode=next(n for n in base['nodes'] if n['type']=='TextEncodeQwenImage21')
encode['inputs']=[{'name':'clip','type':'CLIP','link':13}, {'name':'images.image_1','type':'IMAGE','link':2},
                  {'name':'images.image_2','type':'IMAGE','link':22}, {'name':'vae','type':'VAE','link':14},
                  {'name':'prompt','type':'STRING','link':21,'widget':{'name':'prompt'}}]
encode['widgets_values']=['','',1024]
for link in base['links']:
    if link[0]==14:link[4]=3
load=next(n for n in base['nodes'] if n['type']=='LoadImage');load['widgets_values']=[args.reference,'image']
node=director_node();node['outputs'][0]['links']=[21];node['outputs'][1]['links']=[22];node['outputs'][2]['links']=[23]
node['inputs'][0]['link']=24
load['outputs'][0]['links'].append(24)
base['nodes'] += [node,preview_node()]
base['links'] += [[21,21,0,6,4,'STRING'],[22,21,1,6,2,'IMAGE'],[23,21,2,22,0,'IMAGE']]
base['links'].append([24,load['id'],0,21,0,'IMAGE'])
base['last_node_id']=22;base['last_link_id']=24
save=next(n for n in base['nodes'] if n['type']=='SaveImage');save['widgets_values']=['Qwen21Director']
Path('examples').mkdir(exist_ok=True)
Path('examples/qwen21_director_basic.json').write_text(json.dumps(base,indent=2),encoding='utf-8')

node=director_node(1,(30,30));node['outputs'][1]['links']=[1]
preview=preview_node(2,(830,50));preview['inputs'][0]['link']=1
minimal={'last_node_id':2,'last_link_id':1,'nodes':[node,preview],'links':[[1,1,1,2,0,'IMAGE']], 'groups':[],'config':{},'extra':{},'version':.4}
Path('examples/director_pose_only.json').write_text(json.dumps(minimal,indent=2),encoding='utf-8')

api={
 '1':{'class_type':'UNETLoader','inputs':{'unet_name':'qwen_image_2.1_int8_convrot.safetensors','weight_dtype':'default'}},
 '2':{'class_type':'QwenImage21Cache','inputs':{'model':['1',0],'device':'auto','dtype':'default'}},
 '3':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen3vl_8b_int8_convrot.safetensors','type':'qwen_image','device':'default'}},
 '4':{'class_type':'VAELoader','inputs':{'vae_name':'qwen_image_2.1_vae_bf16.safetensors'}},
 '5':{'class_type':'LoadImage','inputs':{'image':args.reference}},
 '6':{'class_type':'QwenImage21Director','inputs':{'director_state':json.dumps(state),'width':1024,'height':1024,'subject_type':'character','background_mode':'plain white','framing':'auto','prompt_prefix':'','prompt_suffix':'','image':['5',0]}},
 '7':{'class_type':'TextEncodeQwenImage21','inputs':{'clip':['3',0],'vae':['4',0],'prompt':['6',0],'negative_prompt':'','resolution':1024,'images.image_1':['5',0],'images.image_2':['6',1]}},
 '8':{'class_type':'KSampler','inputs':{'model':['2',0],'positive':['7',0],'negative':['7',1],'latent_image':['7',2],'seed':21001,'steps':25,'cfg':1.,'sampler_name':'euler','scheduler':'simple','denoise':1.}},
 '9':{'class_type':'VAEDecode','inputs':{'samples':['8',0],'vae':['4',0]}},
 '10':{'class_type':'SaveImage','inputs':{'images':['9',0],'filename_prefix':'Qwen21Director'}}}
Path('examples/qwen21_director_api.json').write_text(json.dumps(api,indent=2),encoding='utf-8')
print('Wrote basic UI, API and model-free examples')
