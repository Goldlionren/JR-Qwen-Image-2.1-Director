# JR Qwen Image 2.1 Director

在 ComfyUI 中从参考图导入人物姿态，编辑动作与摄影机，再用 Qwen Image 2.1 生成图片。适合制作同一人物的不同动作图片，或为人物 LoRA 准备待筛选的图像素材。

## 安装

1. 使用支持 Qwen Image 2.1 的 ComfyUI。需要节点 `TextEncodeQwenImage21`；加载工作流出现缺失的基础节点时，先更新 ComfyUI。
2. 在 `ComfyUI/custom_nodes` 下运行：

   ```shell
   git clone https://github.com/Goldlionren/JR-Qwen-Image-2.1-Director.git
   ```

3. 重启 ComfyUI，刷新页面。在节点菜单 `image → director` 中找到 **JR Qwen Image 2.1 Director**。

仓库已包含界面文件，无需安装 Node.js 或自行构建。仅编辑骨架可先打开 [姿态编辑示例](examples/director_pose_only.json)，无需生成模型。

### 生成所需模型

将模型放入 ComfyUI 对应目录，刷新模型列表，并在示例工作流中选择自己安装的文件。模型权重需另外下载。

| 模型 | 放置目录 | 示例使用的文件 |
|---|---|---|
| Qwen Image 2.1 | `models/diffusion_models` | `qwen_image_2.1_int8_convrot.safetensors` |
| Qwen3-VL 8B 文本/图像编码器 | `models/text_encoders` | `qwen3vl_8b_int8_convrot.safetensors` |
| Qwen Image 2.1 VAE | `models/vae` | `qwen_image_2.1_vae_bf16.safetensors` |
| Qwen Image 2.1 Fun ControlNet Union | `models/model_patches` | `qwen_image_2.1_fun_controlnet_union_int8_convrot.safetensors` |

可在 [QwenImage 模型目录](https://huggingface.co/Kijai/QwenImage_experimental/tree/main) 查找上述转换权重，或使用兼容的 Qwen Image 2.1 权重。ControlNet 必须使用 **2.1 Fun Union**，不要选旧版 Qwen ControlNet。各模型的授权以其发布页为准。

### 从图片导入姿态

使用 **ComfyUI 的 Python 环境** 安装 [姿态检测依赖](requirements-pose.txt)：

```shell
python -m pip install -r ComfyUI/custom_nodes/JR-Qwen-Image-2.1-Director/requirements-pose.txt
```

请按实际安装位置调整路径。若环境已有可用的 `cv2`，只补装缺少的 `onnxruntime` 即可。

将 [DWPose ONNX 模型](https://github.com/IDEA-Research/DWPose/tree/onnx)中的 `yolox_l.onnx` 和 `dw-ll_ucoco_384.onnx` 放入 `ComfyUI/models/dwpose/`，然后重启 ComfyUI。也可通过环境变量 `JR_DIRECTOR_POSE_MODELS` 指定模型目录。姿态检测在本地 CPU 上运行。

## 选择工作流

将 [example 文件夹](example)中的 JSON 拖入 ComfyUI。首次使用，请在各个 Load Image 节点上传图片，并选择已安装的模型。

| 想做什么 | 工作流 |
|---|---|
| 保留原人物和场景，修改动作 | [Scene 1 Edit Pose](example/JR%20Director%20-%20Scene%201%20Edit%20Pose.json) |
| 把 A 换成 B，保留 A 的服装、动作和场景 | [Scene 2 Replace Identity](example/JR%20Director%20-%20Scene%202%20Replace%20Identity.json) |
| 在人物替换中增加深度控制 | [Scene 2 Pose and Depth](example/JR%20Director%20-%20Scene%202%20Pose%20and%20Depth.json) |
| 使用目标机位的 3D 粗渲染图换视角 | [AnyAngle External 3D](example/JR%20Director%20-%20AnyAngle%20External%203D.json) |

演示素材位于 [examples/scenarios](examples/scenarios)，人物 B 参考图为 [examples/reference.png](examples/reference.png)。使用自己的图片时，需重新导入姿态，避免沿用示例的骨架。

## 场景 1：同人物、同场景，修改动作

1. 打开 **Scene 1 Edit Pose**，在 Load Image 中上传原图，接入 Director 的 `image`。
2. 点击 **从图片导入姿态**，选择目标人物，再点 **应用所选人物**。
3. 在 **POSE** 模式下调整关节，例如拖动手腕抬起手臂。
4. 查看黑底骨架预览，确认动作和构图后点击 **Run**。

示例已将 `<image1>` 作为原图、`<image2>` 作为编辑后的骨架接入编码器。保存工作流可保留姿态；普通 Run 不会重新识图覆盖你的修改。

默认使用 CFG 1、25 步、ControlNet 强度 0.25、控制区间 0–0.6。原图叠加和深度关闭，避免旧动作干扰新动作。

## 场景 2：用 B 替换 A，保留 A 的服装与场景

1. 打开 **Scene 2 Replace Identity**。
2. 将 B 的参考图接到 `identity_image`，作为 `<image1>`；将 A 的目标场景图接到 `image`，作为 `<image2>`。
3. 点击 **从图片导入姿态**，导入 A 的姿态；需要时继续编辑。
4. 保持 `identity_scope=identity_only`，点击 **Run**。
5. 检查输出的自动描述和生成图，筛选符合 B 身份及目标服装、动作的候选。

`identity_only` 使用 B 的脸、发型和体型特征，保留 A 的服装与鞋子。若希望连衣服也来自 B，改为 `full_appearance`。

示例开启 `auto_describe`，复用连接的 Qwen3-VL 编码器读取 B 的身份特征及 A 的服装、动作和场景；默认无需逐张手写这些描述。识图有误时，可用 `prompt_prefix` / `prompt_suffix` 补充，或关闭自动描述后使用自己的提示词。图像引用统一写为 `<image1>`、`<image2>`。

自动描述接受 `IDENTITY:` / `OUTFIT_AND_SCENE:` 标签的大小写差异、标签后的空白和中英文冒号，也兼容描述开头的 `ID:` 缩写。缺少标签时，节点报错和 ComfyUI 日志会显示缺失项及完整生成原文，便于排查。前后缀只用于后续图像生成，不会修改自动识图指令。自动描述采用贪心解码，不受采样器的 seed 或 CFG 控制。

默认使用 CFG 3、25 步、ControlNet 强度 0.25、区间 0–0.6，原图叠加 5%。骨架通过 ControlNet 提供，编码器保留两张完整参考图。

## 导演台操作

| 模式 / 操作 | 用途 |
|---|---|
| CAMERA：左键拖动、滚轮 | 调整输出摄影机的角度与距离 |
| CAMERA：Shift + 左键 | 移动摄影机注视点 |
| ACTOR：左键 / Shift + 左键 | 旋转人物 / 移动人物位置 |
| POSE：选择关节，调整旋转环或 XYZ | 修改局部姿态 |
| POSE：拖动手腕或脚踝 | 调整手脚位置并带动相关关节 |
| 右键 / 中键拖动 | 旋转 / 平移编辑观察视角 |
| Camera view | 查看实际输出摄影机的构图 |

右键观察视角与输出摄影机相互独立；黑底骨架预览反映输出视角。预设用于快速选择姿态，撤销/重做可恢复编辑。换图后应重新导入，再做动作调整。

## 常用设置与接线

| 设置 / 输出 | 使用方法 |
|---|---|
| `controlnet_name` | 选择 2.1 Fun Union；`disabled` 关闭控制 |
| `control_strength`、`control_start/end` | 调整控制力度与作用区间；从示例默认值开始 |
| `control_backend` | 保持 `auto` 即可 |
| `reference_opacity` | 原场景淡叠到骨架；可在 0–0.10 调整，改动作时建议先关闭 |
| `controlled_model` | 接采样器 MODEL；使用 ControlNet 或 AnyAngle 时均从这里输出模型 |
| `director_prompt` | 接 Qwen 编码器的提示词输入 |
| `reference_image_1/2` | 使用场景示例中已连接的参考图输出，编码器 `resolution` 保持 0 |
| `pose_image_reference` | 编码器是否还接入骨架：场景 1 开启，默认场景 2 关闭；开关不会自动改接线 |
| `control_image`、`reference_description` | 分别预览实际姿态控制图与自动识图描述 |

导入姿态后保持画布比例；改变宽高比会影响骨架与原图的对应关系。场景 1、2 用于保留原场景视点；换机位请使用 [AnyAngle 指南](docs/ANYANGLE.md)。

### 可选深度

打开 **Scene 2 Pose and Depth**，选择已安装的 Depth Anything V2 权重。支持文件名带 `vits` / `vitb` / `vitl` 的 `depth_anything_v2_*.safetensors`，放入 `models/depthanything` 或 `models/depth_anything`，重启后选择。模型信息见 [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2)。该示例预选 Large，使用其他规格时请修改 `depth_model`。

自动深度从 `image` 读取场景，在 CPU 上处理。`depth_strength` 调整深度控制强度，`depth_preview` 显示深度图。已有对齐的深度图时，选择 `depth_model=external`，接入 `depth_image`，使用白近黑远的相对深度。

深度为可选项，会增加运行时间。原图深度保留旧动作和原人物体型，可能与目标动作或 B 的体型冲突；需要时关闭或降低强度。

## 批量制作候选图

使用 [批量操作指南](docs/DATASET_WORKFLOW.md)处理 A 数据集。脚本会逐张导入姿态、替换身份，并保存待筛选候选，支持中断后继续。

## 常见问题

- **找不到节点或界面没有加载**：确认节点目录安装正确，重启 ComfyUI 后刷新浏览器；检查启动日志中的缺失依赖。
- **缺少模型 / 模型名称无效**：将权重放到上表目录，刷新列表，并在工作流中重新选择文件。示例不会下载模型。
- **换图后仍是旧姿态**：重新点击“从图片导入姿态”；Run 会保留已编辑的骨架。
- **脸、衣服或动作不符合要求**：先检查图像顺序、`identity_scope`、自动描述及骨架预览；再调整控制强度或补充提示词。
- **多人图换错人**：人物选择只决定导入哪具骨架；建议先裁切目标人物，再处理多人场景。

图片导入属于近似姿态拟合，手指、完整面部、遮挡和特殊体型需要人工调整。生成式编辑不保证背景像素不变，也不保证身份、衣物细节和身体比例完全一致。制作 LoRA 数据时应逐张筛选，并另行核对训练标签。

## 许可证

项目整体按 [GPL-3.0-or-later](LICENSE) 分发。第三方组件及原始组件的授权见 [第三方声明](docs/THIRD_PARTY_NOTICES.md)。模型权重不随仓库分发，使用前请查看各自的模型许可证。
