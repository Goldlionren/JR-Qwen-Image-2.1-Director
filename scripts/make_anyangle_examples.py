"""Generate reproducible UI/API examples with the author's image order and CFG."""
import copy
import json
import sys
import uuid
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from director.state import default_state
from director.coarse import render_coarse


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


state = default_state()
state['render'].update(width=512, height=512)
state['camera'].update(azimuth=60, elevation=15)
state['ui']['view'] = 'camera'
Image.fromarray((render_coarse(state)*255).astype('uint8')).save(ROOT/'examples/scenarios/jr_anyangle_coarse60.png')

for external in (False, True):
    name = 'external' if external else 'director'
    guide = 'external' if external else 'director_proxy'
    workflow = json.loads((ROOT/'examples/qwen21_director_edit_pose.json').read_text(encoding='utf-8'))
    workflow['id'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'JR-AnyAngle-' + name))
    nodes = {n['id']: n for n in workflow['nodes']}
    director = nodes[21]
    director['widgets_values'][:3] = [json.dumps(state),512,512]
    director['widgets_values'][6:8] = ['','']
    director['widgets_values'][8] = 'disabled'
    director['widgets_values'][9:16] = [.25,0.,.6,False,0.,'any_angle','identity_only']
    director['widgets_values'].extend(['QI2.1_AnyAngle.safetensors',1.,guide])
    director['inputs'].append({'name':'angle_reference','type':'IMAGE','link':None})
    director['outputs'].append({'name':'angle_preview','type':'IMAGE','links':[]})
    director['size'] = [800,1420]
    nodes[11]['title'] = 'JR · <image2> 原人物 / 原始画面'
    nodes[11]['widgets_values'] = ['qwen21_director_reference_20260928.png','image']
    nodes[6]['title'] = 'JR · <image1> 目标粗图 / <image2> 原图'
    nodes[7]['widgets_values'] = [21003,'fixed',25,3,'euler','simple',1]
    nodes[9]['widgets_values'] = ['JR_Director_AnyAngle/' + name]
    nodes[22]['title'] = 'JR · AnyAngle 实际角度引导'
    # Replace the ControlNet preview with the actual AnyAngle coarse guide.
    for link in workflow['links']:
        if link[3] == 22:
            link[2] = 11
    if external:
        loader = copy.deepcopy(nodes[11])
        loader.update(id=24, pos=[-980,150], order=12, title='JR · <image1> 目标机位的 3D 粗渲染图')
        loader['widgets_values'] = ['jr_anyangle_coarse60.png','image']
        workflow['nodes'].append(loader)
        link_id = max(l[0] for l in workflow['links']) + 1
        director['inputs'][-1]['link'] = link_id
        workflow['links'].append([link_id,24,0,21,4,'IMAGE'])
        workflow['last_node_id'] = 24
    nodes[23]['size'] = [780,640]
    nodes[23]['widgets_values'] = [
        'JR Qwen Image 2.1 Director · AnyAngle 换机位\n\n'
        'task_mode=any_angle；LoRA=QI2.1_AnyAngle.safetensors；强度 1。\n'
        '采样器 CFG=3，25 步。ControlNet 默认关闭；可选启用强度 0.25、区间 0–0.6 做对比。\n'
        '编码器顺序与其他模式不同：<image1> 是目标机位粗图，<image2> 是原图。已正确接线。\n'
        '通用提示词：Change the camera angle from <image2> to <image1>.\n\n'
        + ('angle_guide=external：替换 angle_reference 上的图片为 Blender / 3D / Gaussian Splat 的目标机位渲染。\n'
           '提供的灰色人偶仅用于演示接线，不是原图的真实 3D 重建。\n'
           '外部粗图已经确定机位；旋转导演台不会旋转这张图片。使用 ControlNet 时需让骨架与粗图对齐。\n'
           if external else
           'angle_guide=director_proxy：实验性灰色实体人偶，跟随导演台相机和关节。\n'
           '示例方位 60°、俯视 15°。可直接调整相机后 Run；原图接 image。\n'
           '灰色人偶没有原图的头发、服装、体型和场景结构，不等于完整 3D 粗模，角度/背景效果需筛选。\n')
        + '\nAnyAngle 用于同人物换机位，不是身份替换模型，也不自动重建 3D 场景。\n'
        'examples/reference.png → input/qwen21_director_reference_20260928.png。\n'
        'examples/scenarios/jr_anyangle_coarse60.png → input/ 同名文件（外部入口演示）。\n'
        '将作者 QI2.1_AnyAngle.safetensors 放入 models/loras，本机已安装。\n'
        '作者：https://huggingface.co/lilylilith/QI_2.1_AnyAngle'
    ]
    for n in workflow['nodes']:
        for slot, output in enumerate(n.get('outputs',[])):
            output['links'] = [l[0] for l in workflow['links'] if l[1:3] == [n['id'],slot]]
        for slot, inp in enumerate(n.get('inputs',[])):
            if inp.get('link') is not None:
                link = next(l for l in workflow['links'] if l[0] == inp['link'])
                assert link[3:5] == [n['id'],slot]
    workflow['last_link_id'] = max(l[0] for l in workflow['links'])
    workflow['groups'][0]['bounding'] = [-1460,-480,920,1800]
    workflow['groups'][1]['bounding'] = [-525,-480,850,1530]
    friendly = 'JR Director - AnyAngle External 3D.json' if external else 'JR Director - AnyAngle Camera.json'
    write(ROOT/'example'/friendly, workflow)
    write(ROOT/f'examples/qwen21_director_anyangle_{name}.json', workflow)
    api = json.loads((ROOT/'examples/qwen21_director_edit_pose_api.json').read_text(encoding='utf-8'))
    api['5']['inputs']['image'] = 'qwen21_director_reference_20260928.png'
    api['6']['inputs'].update(director_state=json.dumps(state), task_mode='any_angle',
        controlnet_name='disabled', control_strength=.25, control_end=.6, reference_opacity=0,
        pose_image_reference=False, anyangle_lora='QI2.1_AnyAngle.safetensors',anyangle_strength=1,angle_guide=guide)
    api['8']['inputs'].update(seed=21003,cfg=3,steps=25)
    api['10']['inputs']['filename_prefix'] = 'JR_Director_AnyAngle/' + name
    if external:
        api['12'] = {'class_type':'LoadImage','inputs':{'image':'jr_anyangle_coarse60.png'}}
        api['6']['inputs']['angle_reference'] = ['12',0]
    write(ROOT/f'examples/qwen21_director_anyangle_{name}_api.json', api)
print('Wrote AnyAngle Director and external 3D examples.')
