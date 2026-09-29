# AnyAngle 换机位使用指南

AnyAngle 用目标机位的 3D / Gaussian Splat 粗渲染图引导 Qwen Image 2.1 改变视角。它用于同人物换机位；人物替换请使用 README 中的场景 2。

## 准备

从 [QI_2.1_AnyAngle 模型页](https://huggingface.co/lilylilith/QI_2.1_AnyAngle)下载 `QI2.1_AnyAngle.safetensors`，放入 ComfyUI 的 `models/loras`，刷新模型列表。

准备原图，以及同一人物或场景在目标机位下的粗渲染图。可在 Blender 等工具中制作；Director 不自动将原图重建为 3D 场景。

## 使用外部粗渲染图

打开 [AnyAngle External 3D 工作流](../example/JR%20Director%20-%20AnyAngle%20External%203D.json)：

1. 原图接 `image`，目标机位粗图接 `angle_reference`。
2. 保持 `task_mode=any_angle`、`angle_guide=external`。
3. 选择 `anyangle_lora=QI2.1_AnyAngle.safetensors`，`anyangle_strength=1`。
4. 使用示例的 CFG 3、25 步，点击 Run。

这里 `<image1>` 是目标粗图，`<image2>` 是原图，与身份替换模式的顺序不同。示例已连接 `reference_image_1/2`，编码器 `resolution=0`，提示词为 `Change the camera angle from <image2> to <image1>.`。

即使关闭 ControlNet，采样器仍须连接 `controlled_model`，以使用已加载 AnyAngle 的模型。

示例中的灰色人偶图片仅用于演示接线，请换成自己的目标粗渲染。外部图片已经决定目标视角，在导演台旋转摄影机不会旋转该图片。

## 使用导演台人偶

[AnyAngle Camera 工作流](../example/JR%20Director%20-%20AnyAngle%20Camera.json)使用 `angle_guide=director_proxy`。原图接 `image`，在导演台调整摄影机和姿态，`angle_preview` 显示用于引导的实体人偶。

此方式为实验性入口。人偶没有原人物的服装、发型、体型和场景细节，不能替代完整的场景粗模，也不保证准确改变视角。

## 与 ControlNet 配合

默认关闭 ControlNet。需要时选择 2.1 Fun Union，从强度 0.25、区间 0–0.6 开始，并保持 `reference_opacity=0`。外部粗图与 Director 骨架必须对齐，否则两种控制可能冲突。

生成新角度时，原图看不到的身份和服装细节可能被补绘。请检查人物一致性、朝向、遮挡和手脚后再保留候选。

[返回使用首页](../README.md)
