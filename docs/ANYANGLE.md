# AnyAngle 接入与实测

2026-09-29，JR Qwen Image 2.1 Director v0.5.0。

## 适用范围

[作者模型卡](https://huggingface.co/lilylilith/QI_2.1_AnyAngle/blob/e42ac7827e2cad7ce22dc099109ae29681239eba/README.md)
将 AnyAngle 定义为由 Gaussian Splat / 3D 粗渲染引导的机位转换 LoRA。
其完整方法先从原图生成 3D 或高斯场景，在 Blender 中改变相机并渲染，再与原图一起输入 Qwen Image 2.1。
骨架只提供关节点，缺少服装体积、遮挡、人物轮廓与环境几何，不能视为等价输入。
本项目接入 LoRA 和参考图路径，不包含 Tripo / Trellis / Blender 的自动建模链。

适合探索同人物的侧面、背面、俯仰等 LoRA 数据候选，不负责把 A 的身份替换成 B。
生成背面或被遮挡细节仍可能偏离原人物，必须筛选。

## 本机安装

- 模型：`QI2.1_AnyAngle.safetensors`，119,590,312 字节，rank 24。
- 作者：lilylilith；模型卡声明 Apache-2.0。权重不随节点仓库发布。
- 固定版本：`e42ac7827e2cad7ce22dc099109ae29681239eba`。
- SHA-256：`e4d7a0d44a45ed62daabd0f2484a1a59046618a4c47e76b1eab5e386a7a35d8a`。
- [权重下载](https://huggingface.co/lilylilith/QI_2.1_AnyAngle/resolve/e42ac7827e2cad7ce22dc099109ae29681239eba/QI2.1_AnyAngle.safetensors)，放入 ComfyUI 的 `models/loras`；本机共享目录已安装并校验。
- ComfyUI 0.37.0 / frontend 1.53.6，基础模型和文本编码器使用现有 INT8 ConvRot。未升级或修改 Core。

## 用法

打开 `example/JR Director - AnyAngle External 3D.json`，这是与作者输入形式相符的入口：

1. `task_mode=any_angle`，`anyangle_lora=QI2.1_AnyAngle.safetensors`，强度 1。
2. `image` 接原图，`angle_reference` 接目标机位的 3D / Splat 粗渲染，`angle_guide=external`。
3. Director 的 `reference_image_1` 接编码器第一张图；`reference_image_2` 接第二张图。两张图统一到 Director 画布，编码器 `resolution=0`。
4. 采样器 CFG 3、25 步。作者建议至少 20 步；暂未叠加 Turbo LoRA。
5. 默认提示词为作者短指令：`Change the camera angle from <image2> to <image1>.`

这里 `<image1>` 是粗图，`<image2>` 是原图，顺序与身份替换模式不同。示例已接好。
外部粗图已经决定目标机位，导演台不会旋转这张位图。
示例 Load Image 中提供的 `jr_anyangle_coarse60.png` **仍只是灰色人偶接线样例**；请替换为自己的真实场景粗渲染。

`example/JR Director - AnyAngle Camera.json` 使用 `angle_guide=director_proxy`：

- 无需额外粗图，Python 根据导演台 FK、相机、关节生成带遮挡和光照的实体人偶，`angle_preview` 可预览实际输入。
- 相机方位 60°、俯视 15°为起始示范。可改变相机、人物旋转、关节后运行；导入新人物姿态后需重新设置目标机位。
- 这是固定比例的几何代理，不是对原人物或背景的 3D 重建；其方位属于虚拟人偶坐标，不是自动测得的原照片相机差值。
- 本次测试没有达到正确机位，保留这个入口用于实验，不作为生产推荐。

所有新参数追加在既有参数之后，旧节点 ID 和原 11 个输出位置保持不变；末尾新增 `angle_preview`。
AnyAngle LoRA 只在 `any_angle` 模式加载；禁用或强度 0 用于无 LoRA 对照。
模型经原生 `load_lora_for_models` 克隆后打补丁，再按需叠加内部 ControlNet；不永久合并权重，不修改基础模型文件。
新模式仍使用 `controlled_model` 输出，即使 ControlNet 关闭，也必须把这个已加载 LoRA 的输出接给采样器。

## 与 ControlNet 联用

两个示例默认关闭 ControlNet，以先检查粗图与 AnyAngle 本身。
可选择现有 Fun Union INT8，强度 0.25、区间 0–0.6 起步做对照。
人偶模式的骨架和粗图共用相机；外部模式须自行保证 Director 骨架与外部粗图对齐，否则两个控制条件可能冲突。
不额外把骨架作为第三张编码器参考。`reference_opacity` 默认 0，不把旧机位原图混入骨架。
联用能运行不代表必然提升质量；深度控制仍未接入。

## 实测结果

RTX 3060 12GB；512×512，25 步，CFG 3，Euler/simple，种子 21003。
原图为仓库动画人物 `examples/reference.png`，粗图是 60° 方位、15° 俯视的灰色人偶。

| 测试 | 耗时 | 本机输出 `JR_Director_AnyAngle/` | 观察 |
|---|---:|---|---|
| 人偶 + AnyAngle 1，无 ControlNet | 56.29 秒 | `proxy60_00001_.png` | 身份/服装大致保留，接近正面，没有跟随目标机位 |
| 外部人偶 PNG + AnyAngle 1 + ControlNet 0.25 | 74.49 秒 | `external60_control025_00001_.png` | 成功运行，仍接近正面，未改善机位 |
| 同参数人偶，无 LoRA、无 ControlNet | 54.29 秒 | `proxy60_without_lora_00001_.png` | 产生侧向视图，但与目标人偶朝向不符，也不算准确换机位 |

有无 LoRA 的输出像素平均绝对差约 18.58/255，实际结果不同；LoRA 不是被节点忽略。
但这不能证明所有适配层或精度均正确，也不能外推真实粗模上的质量。
当前没有原人物的真实 3D / Gaussian 场景素材，尚未验证作者完整输入流程；不能将这些灰色人偶测试视为对模型能力的否定或成功复现。

验证通过：19 项 Python、7 项 Core 运行时、6 项前端检查，前端构建成功。
实际 GPU 执行验证了内置 LoRA、两种粗图入口、INT8 基础模型和 ControlNet 联用路径。
原场景 1 / 2 示例不默认启用 AnyAngle。
