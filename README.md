# JR Qwen Image 2.1 Director

在一个 ComfyUI 节点里摆人物、转摄影机、检查最终投影，并输出 Qwen 2.1 指令和姿态参考图。

## Features / 功能

- **CAMERA**：连续方位角、俯仰、距离、FOV、roll、注视点；八方向、高度、景别预设。
- **ACTOR**：独立的位移、yaw / pitch / roll、统一缩放。
- **POSE**：22 个层级关节（17 个主体关节 + 5 个头部标记）；局部 FK 旋转、手腕/脚踝双骨 IK。
- Three.js 编辑舞台、摄影机视图和实时黑底 OpenPose 风格投影。
- 站立、T-Pose、A-Pose、举手、行走、坐姿、不对称姿态预设；撤销/重做和 JSON 导入/导出。
- 完整状态保存在 workflow 的 `director_state` 字符串输入中。Python 独立重算投影，API 执行无需浏览器。
- **从图片导入姿态**：接入 IMAGE，DWPose 检测人物，选择人物后拟合为固定骨长的可编辑骨架；支持撤销和保存。
- **内置 Fun Union ControlNet**：项目内回移植 Qwen Image 2.1 控制分支，支持 INT8 convrot / BF16；无需安装上游 PR 或修改 ComfyUI Core。
- **两种场景模式**：同人物同场景改动作（`edit_pose`），或把身份图人物放入目标场景/姿态（`replace_person`）。
- **AnyAngle 换机位（实验性）**：节点内加载作者 LoRA，接外部 3D 粗渲染图，或用导演台生成灰色实体人偶作为实验引导。支持与内置 ControlNet 叠加；当前人偶测试尚未实现准确换机位，见 [接入与实测](docs/ANYANGLE.md)。
- 提示词按任务模式区分身份参考、完整场景参考与目标姿态；无旧 LoRA 触发词。

## Installation / 安装

将 [GitHub 仓库](https://github.com/Goldlionren/JR-Qwen-Image-2.1-Director) 克隆到 `ComfyUI/custom_nodes/JR-Qwen-Image-2.1-Director`，然后重启 ComfyUI，刷新浏览器。
发行目录已经包含 `web/dist`，使用者无需 Node.js。手动编辑无需额外 Python 包；图片识别的可选依赖与模型见下节。

测试基线：ComfyUI **0.37.0**（`8d534945`）、frontend **1.53.6**、Python **3.13.12**、PyTorch **2.12.1+cu130**，支持 Vue nodes。
使用 ComfyUI V3 API。更旧版本尚未验证。本项目没有修改 Core。

菜单：`image → director → JR Qwen Image 2.1 Director`。
内部节点 ID 保留为 `QwenImage21Director`，兼容更名前保存的工作流；项目与界面名称统一使用 JR 前缀。
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
| `controlled_model` | MODEL | 追加的第七个输出；ControlNet 开启时为施加姿态控制后的模型，关闭时透传输入模型 |
| `control_image` | IMAGE | 第八个输出；实际送入内部 ControlNet 的控制图，含可选的淡原图叠加 |
| `reference_image_1` | IMAGE | edit_pose 的原图，或 replace_person 的替换人物身份图；适配到 Director 画布 |
| `reference_image_2` | IMAGE | edit_pose 的目标骨架，或 replace_person 的完整目标场景图 |
| `reference_image_3` | IMAGE | 仅 replace_person：目标骨架 |

尺寸支持 64–2048。`background_mode` 只影响生成指令，pose_control 固定黑底。
可选 `image` 用于明确点击后的姿态导入，也可作为实验性原图叠加来源。普通运行只使用你已经编辑并保存的姿态，绝不会自动重识别并覆盖它。
Qwen 的身份参考仍需直接接 `image_1`；姿态来源图和身份参考图可以是不同图片。
以上直接接线适用于原 `director` 模式；另外两种模式使用下面的专用示例。
`director` 模式不产生 reference_image_1/2/3；edit_pose 不产生 reference_image_3，不要连接这些空输出。

## 两种实际场景 / v0.4.0

| 模式 | Director 的 `image` | `identity_image` | 要保留的内容 |
|---|---|---|---|
| `edit_pose` | 同一个人所在的原场景 | 不需要 | 人物身份、服装、场景和相机，只编辑动作 |
| `replace_person` | `<image2>`：目标场景与姿态 | `<image1>`：替换人物 | 使用 `<image1>` 的人物，保留 `<image2>` 的场景与目标姿态 |

`identity_scope` 默认 **identity_only**：B 提供脸、发型和体型，保留 A / `<image2>` 每张图的服装与鞋子。
`full_appearance` 才会连 B 的衣服一起带过去。它们是生成指令，不是精确身体重建或像素级换脸。

- [场景 1 工作流](examples/qwen21_director_edit_pose.json)：点击「从图片导入姿态」，修改关节后 Run。示例已导入教室人物，并只修改右臂为举手。
- [场景 2 工作流](examples/qwen21_director_replace_person.json)：身份图与场景图分开加载。姿态从 `image`（场景图）导入；5%–10% 叠加如开启，也取这张场景图。
- 两个示例默认使用通用提示词，`prompt_prefix` / `prompt_suffix` 留空；身份、服装和场景直接引用 `<image1>` / `<image2>`，动作以最终骨架为准。换素材后重新导入姿态即可开始测试，无需先写人物、衣服颜色或动作描述。本机通用提示词测试中，场景 1 动作修改有效，场景 2 仍未替换身份；后者需要继续验证，必要时可用前后缀补充约束，详见 [验证记录](docs/SCENARIOS.md)。
- [配套素材](examples/scenarios) 中的两张 PNG 放入 ComfyUI/input；原有 `examples/reference.png` 放入 input 并命名 `qwen21_director_reference_20260928.png`。本机已安装素材。
- 示例把 reference_image 输出接到 Qwen 编码器的相应图像槽，`resolution=0`。这样编码器依据已统一的画布决定输出尺寸，避免身份照的比例改变目标场景。
- 保持来源图的比例，优先先导入姿态再编辑关节。这两种模式保留源场景视点；`background_mode` 和 `framing` 的提示词覆盖仅在原 `director` 模式生效。
- `pose_image_reference` 指编码器是否额外接入骨架：edit_pose 的 image_2，或 replace_person 的 image_3；关闭时骨架仅经过 ControlNet，完整场景图仍须保留。

这是生成式场景编辑，不是背景像素锁定或带遮罩的局部合成；多人选择只决定导入哪具骨架，不能保证模型只替换该人物。
实际通过和失败的测试、默认配置依据见 [两种场景验证](docs/SCENARIOS.md)。

### A 数据集 → B 身份 LoRA 候选集

提供 [批量脚本](scripts/batch_replace_dataset.py)，默认只生成清单；加 `--run` 才上传并执行。
默认使用 B 身份、A 服装；每张 A 自动检测/拟合姿态，按源图比例生成，支持断点恢复并记录种子、输入哈希、实际 API 图和 prompt ID。
多人、检测失败或明显拟合错误的图片转为人工检查，不猜测目标人物。
生成图片只进入 `pending`，不自动变成批准的训练集，也不复制 A 的 caption 作为 B 的训练标签。
命令、复核标准和当前限制见 [数据集批量流程](docs/DATASET_WORKFLOW.md)。

## Integrated ControlNet / 内置姿态控制（v0.3.0）

打开 [`examples/qwen21_director_controlnet.json`](examples/qwen21_director_controlnet.json)。
API 示例为 [`examples/qwen21_director_controlnet_api.json`](examples/qwen21_director_controlnet_api.json)。
本机已安装带中文说明和分组的示例工作流 **JR_Director_ControlNet_Example**，默认 512、25 步、强度 1.0，演示 Walking + 45° 相机。
桌面同时提供 `JR Qwen Image 2.1 Director - ControlNet Example.json`，可以直接拖入 ComfyUI。

1. 从 [Kijai 的测试权重目录](https://huggingface.co/Kijai/QwenImage_experimental/tree/main/model_patches)
   下载 `qwen_image_2.1_fun_controlnet_union_int8_convrot.safetensors`，放到 ComfyUI 配置的 `models/model_patches`。
   约 3.78GB；本机已经安装并校验。也支持同目录 BF16 版本，BF16 尚未在本机实测。
2. 将 Qwen 2.1 的 `MODEL`、`VAE` 接入 Director，在 `controlnet_name` 中选择权重。
3. Director 的 `controlled_model` 接 KSampler；原有 `director_prompt` 继续接 Qwen 文本编码器。
4. 身份图接编码器 `image_1`，Director 的 `pose_control` 接 `image_2`。
   保持 `pose_image_reference=true`，让双参考图与 ControlNet 同时发挥作用。
5. 编辑姿态后运行。`control_strength` 为控制强度；`control_start/end` 是去噪过程的开始/结束比例。
   `disabled` 或强度为零不会加载本节点的 ControlNet 权重，输入模型直接透传。

只想使用 ControlNet 时，可断开编码器 `image_2` 并关闭 `pose_image_reference`；该开关调整提示词，**不会自动修改接线**。
目前建议保留双参考图：本机测试中，只有身份图时原图姿势仍可能占主导。
关闭 ControlNet 后若也断开 `image_2`，请另提供不引用姿态参考图的提示词。

该集成保持旧节点 ID 和前六个输出索引。旧工作流默认关闭控制；模型文件不随 Git 仓库分发。
权重必须是 **Qwen Image 2.1 Fun Union**，旧 Qwen InstantX / Fun ControlNet 不兼容，选错会明确报错。
此版 UI 暴露 Pose 控制；虽然权重也支持 Depth、边缘和局部重绘，这些输入尚未集成到导演台。

### 实验：骨架下叠加淡原图

`reference_opacity` 默认 **0（关闭）**，可试 `0.05` 或 `0.10`，表示原图保留 5% 或 10% 的强度。
将来源图接到 Director 的 `image`，把 `control_image` 接到 Preview Image 查看实际控制图。
原图取第一帧、等比例居中适配并留黑边；骨架颜色保持清晰。不会自动把原图人物变形到修改后的姿态。
内部 ControlNet 使用此合成图；原来的 `pose_control` / `pose_preview` 仍是纯骨架，原有输出索引不变。
现有示例的编码器 `image_2` 仍接纯骨架；如需单独实验图像参考叠加，可改接 `control_image`。
大幅换姿态、换视角时，原图可能与目标骨架冲突；**不能将 5%–10% 当作已经验证的通用增强配方**。
GitHub 调研、同种子对比与深度方案见 [姿态增强实验](docs/POSE_CONTROL_RESEARCH.md)。

底层实现来源与修改范围见 [第三方声明](docs/THIRD_PARTY_NOTICES.md)，
本机实测见 [ControlNet 验证记录](docs/CONTROLNET_VALIDATION.md)。
包含 GPL 回移植的 v0.3.0 整体按 GPL-3.0-or-later 分发；原 Director 代码的 MIT 授权保留。
模型权重另受 Qwen Research License 约束。

## Image → Editable Pose / 图片导入姿态

打开 [`examples/director_image_import.json`](examples/director_image_import.json)，无需加载 Qwen 模型。

1. Load Image 上传图片，将 IMAGE 接到 Director 的 `image` 输入。
2. 点击导演台上的 **从图片导入姿态**。只执行取得图片所需的上游节点，不运行 Director 后面的生成链。
3. 预览中会显示人物编号，多人图选择目标人物，再点 **应用所选人物**。
4. 人物变为 `Imported image` 姿态，进入 POSE 模式。可以修改关节、使用 IK、调整人物或摄影机，支持撤销/重做。
5. 保存工作流即可保留导入及后续修改。普通 Run 使用已保存状态；换图后需再次主动导入。

导入会重建姿态、人物变换和摄影机，按源图比例调整输出尺寸（32 像素步长）。源图中的人物位置也会保留；如需居中，可调整摄影机 target。
批量 IMAGE 目前只取第 1 张；一张图最多检测 8 人，每次导入其中一人。检测先将最长边限制到 1024，界面报告的拟合误差以该检测图的像素为单位。
未检测到人物时不修改当前姿态。低置信度的肢体关节保留默认局部角度，并显示缺失提示。

**这是二维关键点到三维 rig 的近似拟合**，使用固定骨长和姿态先验；它不恢复真实的人体比例、摄像机参数或被遮挡的深度。侧身、交叉肢体、严重遮挡、非人类比例需要手动检查。手指和完整面部不会被导入。

图片在本机处理。导入缓存最多 8 张、10 分钟，不把源图、检测缩略图或临时令牌写进 Director 状态；导入后的骨架状态独立于缓存。
关闭导入面板停止等待；已经提交的上游任务可在 ComfyUI 队列中查看或取消。

### Optional detector setup / 可选检测配置

使用当前 ComfyUI 的 Python 环境安装缺少的 `onnxruntime`、`opencv-python-headless`（如已有 `cv2` 则无需重复安装 OpenCV）；依赖清单为 [`requirements-pose.txt`](requirements-pose.txt)。拟合使用 ComfyUI 已有的 SciPy。
将官方 [DWPose ONNX 模型](https://github.com/IDEA-Research/DWPose/tree/onnx) `yolox_l.onnx` 和 `dw-ll_ucoco_384.onnx` 放进 `ComfyUI/models/dwpose/`。
也会从 ComfyUI 配置的共享模型根目录查找已有文件；可用 `JR_DIRECTOR_POSE_MODELS` 环境变量指定模型目录。
不会自动下载模型或改变 CUDA/PyTorch。检测使用 CPU，避免挤占生成模型的显存。本机已有模型和依赖已直接复用。

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
- 无完整手指、脚掌、面部 rig；DWPose 导入是近似 2D→rig 拟合，不是可靠的真实三维重建。
- FK/IK 保持骨长，但没有人体关节角度限制、碰撞、脚底接地或躯干 IK；可以摆出不自然的姿态。
- front/back 与完全重合的侧面肢体仍可能存在二维歧义；骨架颜色不代表身份或服装。
- 新视角看不到的身份/服装细节需要模型猜测；图像参考比例和人体 rig 比例不同会影响服从程度。
- `auto` framing 是基于关键关节可见性的粗略判断。
- 支持从多人图片中选择一人，不包含同一舞台的 multi-actor、timeline、video、训练 LoRA 或 ControlNet 安装。

## License / Third-party references

本项目源代码采用 MIT。Vue 与 Three.js 采用 MIT；分发许可证见 [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)。
Inspired by the interaction concepts of ComfyUI-qwenmultiangle and ComfyUI-3D-OpenPose-Editor-DW, but implemented as a separate JR Qwen Image 2.1 Director architecture.

- [ComfyUI-qwenmultiangle](https://github.com/jtydhr88/ComfyUI-qwenmultiangle)：参考 Vue/TS/Three 与 DOM widget 架构。
- [ComfyUI-3D-OpenPose-Editor-DW](https://github.com/LLAI-lab/ComfyUI-3D-OpenPose-Editor-DW)：参考交互与算法思路；未复制其未明确许可的源码。
- [设计讨论](https://chatgpt.com/share/6aba3a2c-c3a4-83ea-b686-4faa2d635055)：任务方向与取舍。
