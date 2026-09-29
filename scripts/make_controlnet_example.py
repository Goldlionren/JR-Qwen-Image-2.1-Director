"""Build the integrated UI/API example from the existing Director examples."""
import json
import sys
from pathlib import Path

root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from director.state import default_state, apply_preset

state=apply_preset(default_state(),'Walking')
state['camera']['azimuth']=45
state['render'].update(width=512,height=512)
name='model_patches/qwen_image_2.1_fun_controlnet_union_int8_convrot.safetensors'
workflow=json.loads((root/'examples/qwen21_director_basic.json').read_text())
workflow['id']='ebf8dffb-887b-456e-b27d-f30bbac6f533'
byid={n['id']:n for n in workflow['nodes']}
director=byid[21]
director['inputs'] += [{'name':'model','type':'MODEL','link':25},{'name':'vae','type':'VAE','link':26}]
director['outputs'].append({'name':'controlled_model','type':'MODEL','links':[12]})
director['outputs'].append({'name':'control_image','type':'IMAGE','links':[]})
director['widgets_values'][0]=json.dumps(state)
director['widgets_values'][1:3]=[512,512]
director['widgets_values'] += [name,1.,0.,1.,True,0.]
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
byid[11]['title']='JR · 1. 身份参考 / 可选姿态来源'
byid[6]['title']='JR · 3. 双参考图编码'
byid[7]['title']='JR · 4. 使用受控模型采样'
byid[22]['title']='JR · 最终姿态控制图'
note=('JR Qwen Image 2.1 Director · ControlNet Example\n\n'
      '1. 在左侧 Load Image 换成你的参考图片。\n'
      '2. Director 已选择 INT8 Fun Union，强度 1.0，控制区间 0–1。\n'
      '3. 默认示范：Walking 行走 + 相机方位角 45°；在导演台继续调整。\n'
      '4. 如需从图片起步：点击「从图片导入姿态」，选择人物，再修改。\n'
      '5. 点击 Run，右侧保存最终生成图。默认 512 × 512、25 步、CFG 1。\n\n'
      'ControlNet 已内置在导演台，controlled_model 已接入采样器。\n'
      '身份图 → image_1；pose_control → image_2，同时用于内部 ControlNet。\n'
      'pose_image_reference 保持开启。无需额外安装 ControlNet 节点或上游 PR。\n'
      '新机器请先安装 README 中列出的基础模型、编码器、VAE 和 INT8 控制权重。')
workflow['nodes'].append({'id':23,'type':'Note','pos':[-1400,600],'size':[780,345],
    'flags':{},'order':11,'mode':0,'inputs':[],'outputs':[],
    'title':'JR · 使用说明','properties':{},'widgets_values':[note],'color':'#234','bgcolor':'#345'})
workflow['last_node_id']=23
workflow['groups']=[
    {'id':1,'title':'01 · 模型 / 参考图 / 使用说明','bounding':[-1460,-480,920,1490],'color':'#35556a','font_size':24,'flags':{}},
    {'id':2,'title':'02 · 导演台 + 内置 INT8 ControlNet','bounding':[-525,-480,850,1320],'color':'#376a62','font_size':24,'flags':{}},
    {'id':3,'title':'03 · 双参考编码 / 采样 / 输出','bounding':[370,-480,1260,1350],'color':'#635279','font_size':24,'flags':{}}]
for node in workflow['nodes']:
    for index,input_ in enumerate(node.get('inputs',[])):
        link=next((l for l in workflow['links'] if l[0]==input_.get('link')),None)
        if link: assert (link[3],link[4])==(node['id'],index),(node['id'],input_,link)
(root/'examples/qwen21_director_controlnet.json').write_text(json.dumps(workflow,indent=2,ensure_ascii=False),encoding='utf-8')
api=json.loads((root/'examples/qwen21_director_api.json').read_text())
api['6']['inputs'].update(model=['2',0],vae=['4',0],width=512,height=512,
    director_state=json.dumps(state),
    controlnet_name=name,control_strength=1.,control_start=0.,control_end=1.,pose_image_reference=True,reference_opacity=0.)
api['7']['inputs']['resolution']=512
api['8']['inputs']['model']=['6',6]
api['10']['inputs']['filename_prefix']='JR_Qwen_Director_ControlNet'
(root/'examples/qwen21_director_controlnet_api.json').write_text(json.dumps(api,indent=2))
print('Wrote integrated ControlNet UI and API examples')
