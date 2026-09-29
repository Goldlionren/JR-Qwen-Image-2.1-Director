"""Build two UI/API workflows with explicit identity, scene and pose reference roles."""
import copy
import json
import uuid
from pathlib import Path

root=Path(__file__).resolve().parents[1]
identity_hint=('The replacement identity from image 1 is the adult male character with short dark hair and his distinctive face. '
               'Replace the blonde woman in image 2 with him, wearing her burgundy cardigan, cream blouse, blue jeans and white sneakers, '
               'in her raised-hand pose. Keep the classroom unchanged.')
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
    director['widgets_values'][9:12]=[.25,0.,.6]
    director['widgets_values'][13:15]=[.05 if replace else 0.,mode]
    if replace:
        director['widgets_values'][6]=identity_hint
        director['widgets_values'][12]=False
    director['size']=[800,1280]
    byid[11]['widgets_values']=[filename,'image']
    byid[11]['title']='JR · image2 场景和姿态来源' if replace else 'JR · source image 人物和场景'
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
        identity=copy.deepcopy(byid[11]);identity.update(id=24,pos=[-980,150],order=12,title='JR · image1 替换人物身份')
        identity['widgets_values']=['qwen21_director_reference_20260928.png','image']
        workflow['nodes'].append(identity)
        director['inputs'][3]['link']=next_link
        workflow['links'].append([next_link,24,0,21,3,'IMAGE']);next_link+=1
        workflow['last_node_id']=24
    note=('JR Qwen Image 2.1 Director · '+('场景 2：人物替换' if replace else '场景 1：同人物同场景改动作')+'\n\n'
          '示例素材见仓库 examples/scenarios；本机已安装，可直接 Run。\n'
          '换图后请点击导演台「从图片导入姿态」，选择目标人物，再编辑骨架。\n'
          '导入会读取 image（场景图），不会读取 identity_image。\n\n')
    if replace:
        note+=('image1 → identity_image，默认只提供 B 的脸、发型与体型。\n'
               'image2 → image，提供场景、构图与目标姿态。\n'
               'identity_scope=identity_only：保留 image2 / A 的每张图服装。\n'
               '编码器 image_1 / 2 已接身份 / 完整场景；骨架由内部 ControlNet 控制。\n'
               'prompt_prefix 有示例人物描述；换图时一起改成人物的显著特征。\n'
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
           'control_image 可预览实际控制图；深度提取尚未集成。')
    byid[23]['widgets_values']=[note];byid[23]['size']=[780,575]
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
    api=json.loads((root/'examples/qwen21_director_controlnet_api.json').read_text())
    api['5']['inputs']['image']=filename
    api['6']['inputs'].update(director_state=json.dumps(state),task_mode=mode,background_mode='preserve',
                              reference_opacity=.05 if replace else 0.,control_strength=.25,control_end=.6,
                              width=state['render']['width'],height=state['render']['height'])
    api['7']['inputs'].update(resolution=0,**{'images.image_1':['6',8],'images.image_2':['6',9]})
    if replace:
        api['12']={'class_type':'LoadImage','inputs':{'image':'qwen21_director_reference_20260928.png'}}
        api['6']['inputs']['identity_image']=['12',0]
        api['6']['inputs'].update(pose_image_reference=False,prompt_prefix=identity_hint,identity_scope='identity_only')
    api['8']['inputs']['seed']=21003
    api['10']['inputs']['filename_prefix']='JR_Director_'+mode
    write(root/f'examples/qwen21_director_{mode}_api.json',api)
print('Wrote edit_pose and replace_person UI/API examples')
