"""Build the integrated UI/API example from the existing Director examples."""
import json
from pathlib import Path

root=Path(__file__).resolve().parent.parent
name='model_patches/qwen_image_2.1_fun_controlnet_union_int8_convrot.safetensors'
workflow=json.loads((root/'examples/qwen21_director_basic.json').read_text())
workflow['id']='7cb43975-0d8b-44ee-a4a1-5e3ecad0372b'
byid={n['id']:n for n in workflow['nodes']}
director=byid[21]
director['inputs'] += [{'name':'model','type':'MODEL','link':25},{'name':'vae','type':'VAE','link':26}]
director['outputs'].append({'name':'controlled_model','type':'MODEL','links':[12]})
director['widgets_values'][1:3]=[512,512]
director['widgets_values'] += [name,1.,0.,1.,True]
director['size']=[800,1220]
encoder=byid[6]
encoder['widgets_values'][2]=512
for link in workflow['links']:
    if link[0]==12:link[1:3]=[21,6]
workflow['links'] += [[25,2,0,21,1,'MODEL'],[26,4,0,21,2,'VAE']]
workflow['last_link_id']=26
for node in workflow['nodes']:
    for index,output in enumerate(node.get('outputs',[])):
        output['links']=[l[0] for l in workflow['links'] if l[1]==node['id'] and l[2]==index]
byid[9]['widgets_values']=['JR_Qwen_Director_ControlNet']
byid[11]['widgets_values']=['qwen21_director_reference_20260928.png','image']
# Keep controls and node wiring readable when the graph is fitted to the screen.
positions={1:[-1400,-400],2:[-1000,-400],3:[-1400,-180],4:[-1000,-180],
           11:[-1380,150],21:[-500,-420],6:[400,-400],7:[850,-400],8:[1250,-400],9:[1250,-80],22:[400,300]}
for i,pos in positions.items():byid[i]['pos']=pos
for node in workflow['nodes']:
    for index,input_ in enumerate(node.get('inputs',[])):
        link=next((l for l in workflow['links'] if l[0]==input_.get('link')),None)
        if link: assert (link[3],link[4])==(node['id'],index),(node['id'],input_,link)
(root/'examples/qwen21_director_controlnet.json').write_text(json.dumps(workflow,indent=2))
api=json.loads((root/'examples/qwen21_director_api.json').read_text())
api['6']['inputs'].update(model=['2',0],vae=['4',0],width=512,height=512,
    controlnet_name=name,control_strength=1.,control_start=0.,control_end=1.,pose_image_reference=True)
api['7']['inputs']['resolution']=512
api['8']['inputs']['model']=['6',6]
api['10']['inputs']['filename_prefix']='JR_Qwen_Director_ControlNet'
(root/'examples/qwen21_director_controlnet_api.json').write_text(json.dumps(api,indent=2))
print('Wrote integrated ControlNet UI and API examples')
