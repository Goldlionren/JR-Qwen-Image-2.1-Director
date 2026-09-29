# 批量制作人物 LoRA 候选图

将 A 数据集的动作、服装、场景作为目标，用 B 的参考图替换身份。默认保留 A 的衣服，仅从 B 获取脸、发型和体型特征。

先用 [场景 2 工作流](../example/JR%20Director%20-%20Scene%202%20Replace%20Identity.json)确认模型可以运行，再开始批量处理。需要安装 README 中的 DWPose 模型和检测依赖。

## 1. 准备输入

- A：一个包含目标图片的文件夹。
- B：一张清晰的身份参考图。
- 输出：位于 A 文件夹之外的新目录。

在项目根目录，使用 ComfyUI 的 Python 环境执行。以下 `D:/datasets`、`D:/references` 和 `D:/ComfyUI` 都是占位路径，请替换成自己的实际位置。

```shell
python scripts/batch_replace_dataset.py --source-dir "D:/datasets/person_A" --identity-image "D:/references/person_B.png" --auto-describe --reference-opacity 0.05 --output-dir "D:/datasets/person_B_candidates"
```

这一步只创建图片清单，不提交生成。`--auto-describe` 会在生成时自动读取 B 的身份特征、A 的服装和场景，无需逐张手写提示词。

## 2. 先生成少量候选

在同一命令后加 `--run`，指定 DWPose 模型目录，并用 `--limit` 控制本次处理数量：

```shell
python scripts/batch_replace_dataset.py --source-dir "D:/datasets/person_A" --identity-image "D:/references/person_B.png" --auto-describe --reference-opacity 0.05 --output-dir "D:/datasets/person_B_candidates" --run --pose-models "D:/ComfyUI/models/dwpose" --limit 5
```

ComfyUI 须保持运行；默认连接 `http://127.0.0.1:8188`，其他地址可使用 `--url`。脚本按顺序处理图片；队列已有其他任务时会停止，待队列空闲后再运行。

默认使用 `identity_only`、512 长边、ControlNet 强度 0.25、区间 0–0.6。自动描述使用 CFG 3。需要 B 的整套服装时，添加 `--identity-scope full_appearance`；使用 `--resolution` 调整分辨率。

## 3. 检查输出

| 位置 | 内容 |
|---|---|
| `pending/` | 待审核图片及对应来源记录 |
| `manifest.json` | 处理清单、完成状态及需要人工处理的原因 |
| `history/` | 生成记录，可查看自动识图描述 |
| `prompts/` | 对应的生成工作流 |

检查是否是 B、是否保留 A 的服装与动作、身体比例是否合理，以及手指、遮挡、脸和衣服细节是否正确。候选不会自动批准为训练图，也不会复制 A 的训练标签或启动 LoRA 训练。

零人、多人、关节不足或姿态拟合明显异常的图片会标为 `needs_review`，跳过生成；可先裁切或在导演台手动处理。

## 4. 继续与恢复

再次执行相同命令，会跳过已完成图片并继续剩余任务。去掉 `--limit` 可处理剩余全部图片。

同一输出目录必须使用相同输入与配置；更换 B、新增 A 图片或改变选项时，请新建输出目录。源图片会保持原样。

关闭脚本不会取消已经提交到 ComfyUI 的任务。若遇到提交状态不明、历史缺失或文件已变更的提示，先检查 ComfyUI 队列和清单，避免重复生成。

## 可选：手写描述

去掉 `--auto-describe`，使用 `--identity-description "B 的脸部、发型和体型特征"`；此方式默认 CFG 1。`identity_only` 模式的 B 描述不应包含其服装。

需要为 A 提供逐图描述时，可添加 `--scene-descriptions descriptions.json`。文件内容为相对路径与描述的对应关系：

```json
{
  "folder/001.png": "Describe the clothing, footwear, pose and setting to retain."
}
```

请用各图实际内容替换示例句子，不包含 A 的脸、名字或身份特征。这些描述用于生成，不是训练 caption；训练标签须另行审核。

[返回使用首页](../README.md)
