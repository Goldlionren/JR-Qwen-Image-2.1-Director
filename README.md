# Qwen Image 2.1 Director

在一个 ComfyUI 节点里摆人物、转摄影机、检查最终投影，并输出 Qwen 2.1 指令和姿态参考图。

## Features / 功能

- **CAMERA**：连续方位角、俯仰、距离、FOV、roll、注视点；八方向、高度、景别预设。
- **ACTOR**：独立的位移、yaw / pitch / roll、统一缩放。
- **POSE**：22 个层级关节（17 个主体关节 + 5 个头部标记）；局部 FK 旋转、手腕/脚踝双骨 IK。
- Three.js 编辑舞台、摄影机视图和实时黑底 OpenPose 风格投影。
- 站立、T-Pose、A-Pose、举手、行走、坐姿、不对称姿态预设；撤销/重做和 JSON 导入/导出。
- 完整状态保存在 workflow 的 `director_state` 字符串输入中。Python 独立重算投影，API 执行无需浏览器。
- 自然语言提示词区分身份参考 `<image1>` 和最终姿态参考 `<image2>`；无旧 LoRA 触发词。

## Installation / 安装

将整个目录放入 `ComfyUI/custom_nodes/ComfyUI-QwenImage21-Director`，然后重启 ComfyUI，刷新浏览器。
发行目录已经包含 `web/dist`，使用者无需 Node.js，也无需安装额外 Python 包。

测试基线：ComfyUI **0.37.0**（`8d534945`）、frontend **1.53.6**、Python **3.13.12**、PyTorch **2.12.1+cu130**，支持 Vue nodes。
使用 ComfyUI V3 API。更旧版本尚未验证。本项目没有修改 Core。

菜单：`image → director → Qwen Image 2.1 Director`。
首次试用可打开 [`examples/director_pose_only.json`](examples/director_pose_only.json)，不加载模型即可运行。

## Development Setup / 开发

```powershell
npm ci
npm run build
npm test
python -m unittest discover -s tests -v
```

`python` 应使用现有 ComfyUI venv 的解释器（需要 numpy、Pillow）。
Node 20.12 已实测可构建；Vite 6 用于兼容现有环境。

```powershell
# 独立 UI 开发预览，默认只监听本机
npm run dev

# Windows 开发安装：创建 junction，不覆盖已有节点目录
.\scripts\deploy_dev.ps1 -ComfyRoot '你的 ComfyUI 目录'
```

修改前端后重新 build 并刷新页面；修改 Python 后重启 ComfyUI。
本机使用计划任务 `ComfyUI 3060 Production` 管理启停。操作前检查 `/queue` 空闲，使用既有计划任务重启。

## Camera Controls / 摄影机

Camera 模式：左键拖动 orbit，滚轮 dolly，Shift + 左键拖动 target。
右键旋转编辑观察视角，中键平移观察视角；观察视角不会改变 Director Camera。
`Camera view` 切换到真正的输出摄影机，并按输出宽高比显示画面。
下方黑底预览始终使用 Director Camera，与右键观察角度无关。

`Eye Level` 将摄影机放到当前头部高度；数值 Elevation 则是相对于轨道 target 的仰角，两者不是同一个概念。
Full Body / Medium / Close 会调整 camera target、distance 和 FOV，跟随 actor 根位置及缩放。
节点的 `framing` 为提示词覆盖项；要改变实际投影，请同时调整摄影机。

## Actor Controls / 人物

Actor 模式：左键拖动旋转人物 yaw；Shift + 左键拖动改变人物 X/Z 位置。
面板可以精确设置 XYZ、yaw、pitch、roll、scale。它们不会改变摄影机或局部关节角度。

## Pose Controls / 姿态

在 Pose 模式选择关节，用旋转环或 XYZ 数字编辑局部旋转。
直接拖动手腕/脚踝，双骨 IK 会计算肩/肘或髋/膝；目标超出可达范围时自动限制到骨链长度。
右键换观察视角后可从另一个平面调整深度。骨长来自不可变 rest offsets，不会因为拖动无限拉长。
预设只修改 pose，不改变 actor 或 camera。坐姿预设不会自动下移 actor；可在 Actor 面板调高度。
末端 wrist/ankle 自身旋转在未实现手掌/脚掌时不影响主骨架投影；使用 IK 拖动改变其位置。

## Outputs / 输出

| 输出 | 类型 | 内容 |
|---|---|---|
| `director_prompt` | STRING | Qwen 2.1 双参考图自然语言指令 |
| `pose_control` | IMAGE | 黑底彩色 OpenPose 风格身体图，float32 `[1,H,W,3]` |
| `pose_preview` | IMAGE | 当前与 pose_control 相同 |
| `camera_info` | STRING | JSON：轨道角、相对角、实际相对视角、视线高度、景别 |
| `pose_text` | STRING | 从骨架推导的基础姿态描述 |
| `director_state` | STRING | version 1 完整 3D 状态，可重新导入 |

尺寸支持 64–2048。`background_mode` 只影响生成指令，pose_control 固定黑底。
可选 `image` 输入预留给身份参考接线，目前不显示参考图，也不参与人体重建；同一张图需要直接接给 Qwen 的 `image_1`。

## Qwen Image 2.1 Workflow

打开 [`examples/qwen21_director_basic.json`](examples/qwen21_director_basic.json)。
它是从本机既有 Qwen 2.1 workflow 复制并接入 Director 的独立示例，原工作流未改动。

1. Load Image 选择你的角色参考图，接 `TextEncodeQwenImage21.images.image_1`。
2. Director `pose_control` 接 `images.image_2`。
3. Director `director_prompt` 接编码器 `prompt`。
4. 加载 Qwen 2.1 diffusion model、Qwen3-VL 8B、Qwen 2.1 VAE；VAE 同时接编码器和解码器。
5. 编码器的 `positive / negative / latent` 接 KSampler，使用示例的 Euler / simple / CFG 1 / 25 steps 起步。

不要额外将原图 VAEEncode 后作为 sampler 初始 latent。本地 Core 编码器会处理参考 latent 和输出初始 latent。
模型文件名请按自己安装的文件调整。仓库不下载模型。
API 形式在 [`examples/qwen21_director_api.json`](examples/qwen21_director_api.json)。

测试用玩具角色参考图位于 [`examples/reference.png`](examples/reference.png)。其他机器使用该示例时先在 Load Image 上传它，选择实际返回的文件名。
生成结果与限制见 [`docs/VALIDATION.md`](docs/VALIDATION.md)。

## Architecture / 状态与坐标

`shared/rig.json` 是骨架层级、不可变 rest offsets、颜色、连接和预设的共享定义。
`frontend/three` 负责场景/关节/IK/投影；`frontend/components` 负责 UI；`director/` 是无 ComfyUI 依赖的纯 Python 逻辑。
V3 节点仅做参数桥接与 IMAGE tensor 转换。没有 sampler、模型或 ControlNet 的重复实现。

- 右手坐标，Y 向上，角色正面为 +Z，角色自身右侧为 -X。
- Camera azimuth：0° 正面、90° 角色右侧、180° 背面、270° 左侧。
- 局部关节旋转使用 XYZ Euler（度）；actor 使用 YXZ 顺序，其中正 yaw 对应绕世界 -Y。
- 相对 yaw 元数据 = `(camera.azimuth - actor.yaw) mod 360`。
- 人物发生位移/倾斜时，提示词使用实际摄影机位置在 actor 坐标系内的角度，避免简单相减带来的偏差。
- 六平面 frustum clipping、相机后方剔除、深度排序、宽高比在前后端一致；两种光栅化器的抗锯齿像素可能略有不同。

完整设计说明见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## Known Limitations / 已知限制

- 自然语言的连续角度不是模型几何约束；双参考图也是指导，不等于 Pose ControlNet。
- 实测玩具角色：侧面/45°和举手有效；正面行走腿部跟随较弱，背面鞋朝向不可靠，举手可能被裁切。请见验收记录，而不是将成功出图当作严格姿态达标。
- 当前只输出 OpenPose 风格身体图；没有针对某一个 ControlNet 模型的逐项兼容验证。
- 无完整手指、脚掌、面部 rig，无 DWPose 自动检测/导入，无自动 2D→3D 恢复。
- FK/IK 保持骨长，但没有人体关节角度限制、碰撞、脚底接地或躯干 IK；可以摆出不自然的姿态。
- front/back 与完全重合的侧面肢体仍可能存在二维歧义；骨架颜色不代表身份或服装。
- 新视角看不到的身份/服装细节需要模型猜测；图像参考比例和人体 rig 比例不同会影响服从程度。
- `auto` framing 是基于关键关节可见性的粗略判断。
- 不包含 multi-actor、timeline、video、训练 LoRA 或 ControlNet 安装。

## License / Third-party references

本项目源代码采用 MIT。Vue 与 Three.js 采用 MIT；分发许可证见 [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)。
Inspired by the interaction concepts of ComfyUI-qwenmultiangle and ComfyUI-3D-OpenPose-Editor-DW, but implemented as a separate Qwen-Image 2.1 Director architecture.

- [ComfyUI-qwenmultiangle](https://github.com/jtydhr88/ComfyUI-qwenmultiangle)：参考 Vue/TS/Three 与 DOM widget 架构。
- [ComfyUI-3D-OpenPose-Editor-DW](https://github.com/LLAI-lab/ComfyUI-3D-OpenPose-Editor-DW)：参考交互与算法思路；未复制其未明确许可的源码。
- [设计讨论](https://chatgpt.com/share/6aba3a2c-c3a4-83ea-b686-4faa2d635055)：任务方向与取舍。
