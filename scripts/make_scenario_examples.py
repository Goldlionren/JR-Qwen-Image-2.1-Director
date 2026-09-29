"""Build two UI/API workflows with explicit identity, scene and pose reference roles."""
import copy
import json
import uuid
from pathlib import Path

root=Path(__file__).resolve().parents[1]
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

for mode in ('edit_pose','replace_person'):
    replace=mode=='replace_person'
    state=json.loads((root/f'examples/scenarios/{mode}-state.json').read_text(encoding='utf-8'))
    filename='jr_director_classroom_raised.png' if replace else 'jr_director_classroom_source.png'
    workflow=json.loads((root/'examples/qwen21_director_controlnet.json').read_text(encoding='utf-8'))
    workflow['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,'jr-director/scenarios/'+mode))
    byid={n['id']:n for n in workflow['nodes']}
    director=byid[21]
    director['widgets_values'][0]=json.dumps(state)
    director['widgets_values'][1:3]=[state['render']['width'],state['render']['height']]
    director['widgets_values'][4]='preserve'
    director['widgets_values'][6:8]=['','']
    director['widgets_values'][9:12]=[.25,0.,.6]
    director['widgets_values'][13:15]=[.05 if replace else 0.,mode]
    director['widgets_values'][16:]=['disabled',1.,'external','auto',replace,'disabled',.25]
    director['inputs'] += [dict(name='angle_reference',type='IMAGE',link=None),dict(name='clip',type='CLIP',link=None),dict(name='depth_image',type='IMAGE',link=None)]
    director['outputs'] += [dict(name='angle_preview',type='IMAGE',links=[]),dict(name='reference_description',type='STRING',links=[]),dict(name='depth_preview',type='IMAGE',links=[])]
    byid[7]['widgets_values']=[21003,'fixed',25,3 if replace else 1,'euler','simple',1]
    if replace:
        director['widgets_values'][12]=False
    director['size']=[800,1450]
    byid[11]['widgets_values']=[filename,'image']
    byid[11]['title']='JR · <image2> 场景和姿态来源' if replace else 'JR · <image1> 原人物和场景'
    byid[9]['widgets_values']=['JR_Director_'+mode]
    byid[6]['title']='JR · 人物身份 / 完整场景双图编码' if replace else 'JR · 原图 / 新姿态双图编码'
    byid[6]['widgets_values'][2]=0
    byid[22]['title']='JR · 实际 ControlNet 控制图'
    # Rebuild encoder inputs and links together so Autogrow slot indices remain valid.
    workflow['links']=[l for l in workflow['links'] if l[3]!=6]
    encoder_inputs=[('clip','CLIP',3,0),('images.image_1','IMAGE',21,8),('images.image_2','IMAGE',21,9)]
    encoder_inputs += [('vae','VAE',4,0),('prompt','STRING',21,0)]
    byid[6]['inputs']=[]
    next_link=27
    for slot,(name,kind,source,output) in enumerate(encoder_inputs):
        item={'name':name,'type':kind,'link':next_link}
        if name=='prompt':item['widget']={'name':'prompt'}
        byid[6]['inputs'].append(item)
        workflow['links'].append([next_link,source,output,6,slot,kind]);next_link+=1
    for link in workflow['links']:
        if link[3]==22:link[2]=7
    if replace:
        identity=copy.deepcopy(byid[11]);identity.update(id=24,pos=[-980,150],order=12,title='JR · <image1> 替换人物身份')
        identity['widgets_values']=['qwen21_director_reference_20260928.png','image']
        workflow['nodes'].append(identity)
        director['inputs'][3]['link']=next_link
        workflow['links'].append([next_link,24,0,21,3,'IMAGE']);next_link+=1
        workflow['last_node_id']=24
        director['inputs'][5]['link']=next_link
        workflow['links'].append([next_link,3,0,21,5,'CLIP']);next_link+=1
        workflow['nodes'].append(dict(id=25,type='PreviewAny',pos=[350,950],size=[650,250],flags={},order=13,mode=0,
            title='JR · 自动识别的身份 / 服装描述（请检查）',inputs=[dict(name='source',type='*',link=next_link)],
            outputs=[dict(name='STRING',type='STRING',links=[])],properties={'Node name for S&R':'PreviewAny'},widgets_values=[]))
        workflow['links'].append([next_link,21,12,25,0,'STRING']);next_link+=1
        workflow['last_node_id']=25
    note=('JR Qwen Image 2.1 Director · '+('场景 2：人物替换' if replace else '场景 1：同人物同场景改动作')+'\n\n'
          '示例素材见仓库 examples/scenarios；本机已安装，可直接 Run。\n'
          '换图后请点击导演台「从图片导入姿态」，选择目标人物，再编辑骨架。\n'
          '导入会读取 image（场景图），不会读取 identity_image。\n\n')
    note+=('通用提示词由 Director 按模式自动生成；默认无需填写 prompt_prefix / prompt_suffix。\n'
           '不限定人物性别、发型、服装颜色、场景或具体动作；最终动作以骨架为准。\n\n')
    if replace:
        note+=('<image1> → identity_image，默认只提供 B 的脸、发型与体型。\n'
               '<image2> → image，提供场景、构图与目标姿态。\n'
               'identity_scope=identity_only：保留 <image2> / A 的每张图服装。\n'
               'auto_describe 已开启：用现有 Qwen3-VL 自动识别 B 身份和 A 服装，默认无需手写人物特征。\n'
               '先检查右侧自动描述；误识别可用 prompt_prefix / prompt_suffix 补充纠正。采样器 CFG=3。\n'
               '编码器 image_1 / 2 已接身份 / 完整场景；骨架由内部 ControlNet 控制。\n'
               '如自行添加骨架到 image_3，再开启 pose_image_reference。\n'
               'reference_opacity=0.05：将场景图淡叠到内部 ControlNet 骨架。可比较 0 / 0.05 / 0.10。\n'
               '当前示例针对单人场景；多人先裁切或准备人物遮罩以减少误替换。\n')
    else:
        note+=('source image 同时提供身份和场景。\n'
               '默认姿态已从示例照片导入，只修改右臂为举手。\n'
               '编码器 image_1 / 2 已接原图 / 修改后骨架。\n'
               'reference_opacity=0，避免原图旧动作与新骨架冲突。\n')
    note+=('\n画布以 Director width / height 为准，参考图等比例适配。\n'
           'ControlNet 以低强度 0.25、区间 0–0.6 起步，避免把场景压掉。\n'
           '编码器 resolution 保持 0；导入姿态后不要单独改画布比例。\n'
           '这两种模式保留原场景视点；background_mode / framing 仅用于 director 模式。\n'
           'control_image 可预览骨架控制图。可选 depth_model 启用自动深度或 external 外部深度，depth_preview 输出实际深度。\n'
           '深度默认关闭；改动作时，原图深度可能与新骨架冲突。')
    byid[23]['widgets_values']=[note+'\ncontrol_backend=auto：新 Core 优先使用官方实现，旧 Core 自动回退。'];byid[23]['size']=[780,650]
    workflow['groups'][0]['bounding']=[-1460,-480,920,1630]
    workflow['groups'][1]['bounding']=[-525,-480,850,1380]
    workflow['last_link_id']=next_link-1
    for node in workflow['nodes']:
        for index,output in enumerate(node.get('outputs',[])):
            output['links']=[l[0] for l in workflow['links'] if l[1]==node['id'] and l[2]==index]
        for index,input_ in enumerate(node.get('inputs',[])):
            if input_.get('link') is not None:
                link=next(l for l in workflow['links'] if l[0]==input_['link'])
                assert (link[3],link[4])==(node['id'],index)
    write(root/f'examples/qwen21_director_{mode}.json',workflow)
    example_dir=root/'example';example_dir.mkdir(exist_ok=True)
    friendly='JR Director - Scene 2 Replace Identity.json' if replace else 'JR Director - Scene 1 Edit Pose.json'
    write(example_dir/friendly,workflow)
    api=json.loads((root/'examples/qwen21_director_controlnet_api.json').read_text())
    api['5']['inputs']['image']=filename
    api['6']['inputs'].update(director_state=json.dumps(state),task_mode=mode,background_mode='preserve',
                              prompt_prefix='',prompt_suffix='',
                              control_backend='auto',auto_describe=replace,
                              reference_opacity=.05 if replace else 0.,control_strength=.25,control_end=.6,
                              width=state['render']['width'],height=state['render']['height'])
    api['7']['inputs'].update(resolution=0,**{'images.image_1':['6',8],'images.image_2':['6',9]})
    if replace:
        api['12']={'class_type':'LoadImage','inputs':{'image':'qwen21_director_reference_20260928.png'}}
        api['6']['inputs']['identity_image']=['12',0]
        api['6']['inputs'].update(pose_image_reference=False,identity_scope='identity_only')
        api['6']['inputs']['clip']=['3',0]
        api['13']={'class_type':'PreviewAny','inputs':{'source':['6',12]}}
    api['8']['inputs']['seed']=21003
    api['8']['inputs']['cfg']=3 if replace else 1
    api['10']['inputs']['filename_prefix']='JR_Director_'+mode
    write(root/f'examples/qwen21_director_{mode}_api.json',api)
    if replace:
        depth_workflow=copy.deepcopy(workflow)
        depth_nodes={n['id']:n for n in depth_workflow['nodes']}
        depth_nodes[21]['widgets_values'][21]='depth_anything_v2_vitl_fp16.safetensors'
        depth_nodes[23]['widgets_values'][0]+='\n\n本流程为可选深度对照：读取原场景自动估计深度，在骨架之外叠加 0.25 强度深度控制。\n需要本地 Depth Anything V2 Large 权重；不保证优于默认骨架方案，体型可能更接近 A。'
        depth_nodes[9]['widgets_values']=['JR_Director_replace_person_depth']
        depth_workflow['id']=str(uuid.uuid5(uuid.NAMESPACE_URL,'jr-director/scenarios/replace_person_depth'))
        link=max(l[0] for l in depth_workflow['links'])+1
        preview=copy.deepcopy(depth_nodes[22]);preview.update(id=26,pos=[350,1250],order=14,title='JR · 实际深度控制图')
        preview['inputs'][0]['link']=link
        depth_workflow['nodes'].append(preview)
        depth_workflow['links'].append([link,21,13,26,0,'IMAGE'])
        depth_nodes[21]['outputs'][13]['links']=[link]
        depth_workflow.update(last_node_id=26,last_link_id=link)
        write(root/'example/JR Director - Scene 2 Pose and Depth.json',depth_workflow)
        depth_api=copy.deepcopy(api)
        depth_api['6']['inputs'].update(depth_model='depth_anything_v2_vitl_fp16.safetensors',depth_strength=.25)
        depth_api['10']['inputs']['filename_prefix']='JR_Director_replace_person_depth'
        write(root/'examples/qwen21_director_replace_person_depth_api.json',depth_api)
print('Wrote edit_pose and replace_person UI/API examples')
