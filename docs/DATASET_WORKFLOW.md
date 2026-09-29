# 固定人物 IP 的 LoRA 候选集流程

用户目标：素材少时，借用 A 数据集的动作、服装、场景和视角，为 B 制作身份 LoRA 候选图；没有 A 数据集时，使用导演台逐张补齐动作和视角。
**默认只迁移 B 的脸、发型和体型，保留 A 每张图的服装。** 当前生成仍可能出现身份/体型漂移，所以结果不是自动批准的训练集。

## 先规划，再执行

使用 ComfyUI 的 Python 环境。在项目根目录运行，替换下列路径和 B 描述：

```powershell
python scripts/batch_replace_dataset.py --source-dir 'D:/datasets/person_A' --identity-image 'D:/references/person_B.png' --identity-description 'B 的脸部、发型和体型特征；不要写 B 的服装' --output-dir 'D:/datasets/person_B_candidates'
```

默认只创建 `manifest.json`，不会上传文件或执行推理。输出目录必须在 A 数据集之外，源文件保持原样。
B 的简短描述建议使用模型能清楚理解的文字；身份图片仍是主要身份参考。不要在 identity_only 模式描述 B 的外套等服装。

若已有经过核对的 A 服装/动作描述，使用 `--scene-descriptions descriptions.json`。例如：

```json
{
  "classroom/001.png": "burgundy cardigan, cream blouse, blue jeans and white sneakers; raising the right hand in a classroom"
}
```

键是相对 A 目录的图片路径，统一用 `/`。值只描述要保留的衣服、动作、场景，不包含 A 的名字、脸部或体型身份描述。
这是给生成模型的逐图约束，不是训练 caption。脚本不会自动把未经核对的 A `.txt` 文件当作这些描述。
如果第一次计划就使用该选项，恢复时也须给同一文件；改变其内容需新建一次运行。

确认路径后，同一命令加上执行参数。先跑少量样本：

```powershell
python scripts/batch_replace_dataset.py --source-dir 'D:/datasets/person_A' --identity-image 'D:/references/person_B.png' --identity-description 'B 的脸部、发型和体型特征；不要写 B 的服装' --output-dir 'D:/datasets/person_B_candidates' --run --pose-models 'D:/Comfy-Desktop/ComfyUI-Shared/models/DreamID-V/pose/models' --limit 5
```

- 默认 `identity_only`、512 长边、ControlNet 强度 0.25、区间 0–0.6、原图淡叠加 **0**。`--reference-opacity 0.05` 可另建一次实验；不能保证更好。
- `--identity-scope full_appearance` 才使用 B 的整套服装。`--resolution` 可改，但更大尺寸的批量性能尚未验证。
- 去掉 `--limit` 处理清单中剩余可执行图片。清单固定于首次扫描；新增 A 图片或改变 B / 配置应使用新输出目录。
- 同一个输出目录有进程锁，避免重复启动并发批处理。
- ComfyUI 队列有其他任务时停止，不会插入整批任务；每次只提交一张。

## 恢复与记录

再次执行**相同参数、相同输出目录**会恢复清单，已完成图片跳过；已记录 prompt ID 的任务先读取原结果，不重复提交。
退出脚本不会取消服务端正在执行的图片。网络在提交时中断、尚未获得 prompt ID，会保留 `submitting` 状态并停止自动重试，需核查队列/历史后处理，避免重复出图。
服务历史丢失、源文件变化或已保存候选图被修改时，也会要求先检查，不悄悄重新生成或覆盖。

输出结构：

```text
manifest.json           # 每张来源、SHA256、种子、状态、拟合数据、prompt ID
prompts/<id>.json       # 实际提交的完整 API 图
history/<id>.json       # ComfyUI 执行记录
pending/<id>.png        # 待审核候选
pending/<id>.json       # 来源和身份参考哈希、范围、种子、拟合数据
```

没有自动输出训练 caption，也不会把 A 的 `.txt` 标签原样复制给 B。A 原标签可能包含 A 的名字、身份或不再成立的身体描述，必须重审。

## 当前支持与需要人工处理的情况

- 单张图恰好检测到一人时自动拟合。零人、多人、关节不足或拟合误差超过长边 5% 转为 `needs_review`，跳过生成；先人工裁切、选人或用导演台处理。
- 仅用一张 B 身份参考；多角度身份参考选择、自动人脸相似度打分、自动 caption、批准/淘汰界面尚未实现。
- 生成后的 `review_status=pending` 始终表示尚未批准，不能因为模型成功执行就直接投入 LoRA 训练。
- 本机自动流程实测已完成一张输入到清单/输出的全链路，但仅用 B 描述的样本误复制了 B 的衣服并丢失举手，被人工判为不合格。单张示例中明确写出 A 服装和动作后效果更好；**尚不能称为无人审核的批量数据集生产线**。
- 人工检查：是否是 B；是否仍是 A 的服装；动作/视角是否正确；体型是否混入 A；手指和遮挡是否合理；是否混入错误脸或重复人物。
- 同一张 B 参考反复扩增可能重复模型偏差；少量真实/原始 B 素材应保留用于对照，不把所有合成结果视作等价真值。

本版本只提供候选生成和追溯，不启动 LoRA 训练，也不修改现有数据集。
