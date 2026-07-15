# navida-habitat

在 Habitat 中运行、评估和适配纯 NaVIDA 模型的独立仓库。

## 项目目标

本仓库用于完成以下闭环：

NaVIDA 模型 → Habitat 仿真 → episode 日志 → 批量评估 → 失败分析 → 目标域适配

主要目标包括：

- 接入官方 NaVIDA-3B checkpoint。
- 使用历史 RGB、当前 RGB 和自然语言指令进行闭环导航。
- 实现官方文本 action chunk grammar 的解析与执行。
- 分离官方复现评估和严格纯模型评估。
- 在基线完成后支持目标场景 VLN + IDS QLoRA。
- 记录 SR、SPL、NE、OSR、碰撞、无效输出、延迟和失败类型。

## 不属于本仓库的内容

- Advisor + Geometric Controller
- 将目标距离或目标方位写入 prompt
- 普通单步 Qwen baseline
- anti-stuck 动作覆盖
- force-stop-within-success-radius
- 无效输出后的随机动作或 move-forward fallback
- ROS2、Nav2、cmd_vel 和真实小车部署
- YOLO、展示素材和其他无关模块

## 固定的上游版本

- NaVIDA paper: arXiv:2601.18188v2
- NaVIDA code commit: b86316a78a2865c80b445ed5a8fcc08fc0243dfb
- NaVIDA checkpoint revision: 0ccd8b6b3cd0826c5dd67374415ceedf51adb9e2
- Backbone: Qwen2.5-VL-3B
- Habitat-Sim: 0.2.4
- Habitat-Lab: 0.2.4
- Transformers: 4.50.3

Habitat-Lab 和 Habitat-Sim 作为固定版本的外部依赖，不复制到本仓库中。

## 模型输入和输出

论文协议中的模型输入：

- 最多 8 张均匀采样的历史 RGB 图像
- 1 张当前 RGB 图像
- 自然语言导航指令

默认训练图像分辨率为 308 × 252。

模型不读取：

- target distance
- target bearing
- simulator ground-truth pose
- depth
- GPS
- compass
- top-down map

官方模型输出普通文本 action chunks，例如：

`forward 50 cm, turn left 30 degree`

原子动作包括：

- forward 25 cm
- turn left 15 degree
- turn right 15 degree
- stop

## 评估协议

### official_repro

尽量复现官方 prompt、历史帧采样、生成参数、action parser 和 chunk 执行策略，用于验证模型、数据集和 Habitat 接口是否连接正确。

官方复现结果不得与严格纯模型结果混合报告。

### paper_pure

主要实验协议，只允许论文定义的模型输入。

该协议必须满足：

- 不使用目标距离或目标方位控制动作。
- 不使用 Advisor 或 Geometric Controller。
- 不覆盖模型生成的有效动作。
- 无效输出记录为 invalid output，并终止为失败。
- 只允许使用明确记录的最大步数限制。
- 保存原始模型输出、解析结果和实际执行动作。

## 数据集计划

1. 首先在 R2R VLN-CE val-unseen 上验证官方 checkpoint。
2. HM3D PointNav smoke 只用于检查 RGB、动作、渲染、日志和指标链路。
3. 纯 VLN 的 HM3D 测试必须使用与目标轨迹绑定的自然语言指令。
4. 训练集、验证集和测试集必须按 scene 划分，避免场景泄漏。
5. HM3D、MP3D、模型权重、训练图像和评估视频不得提交到普通 Git。

## 模型路线

第一阶段使用官方 NaVIDA checkpoint 建立基线。

只有当官方模型在 scene-disjoint、grounded-instruction 验证集上表现出明确的目标域问题后，才进行目标域 QLoRA。

目标域训练应同时保留：

- VLN action prediction samples
- inverse dynamics supervision samples
- 必要的原始域 replay samples

不计划从随机参数开始预训练完整 VLM。

## 硬件说明

RTX 4060 Ti 8GB 本地环境主要用于：

- 4-bit NaVIDA 推理
- 单 episode 和小批量测试
- 小规模 QLoRA 验证
- action parser、日志和评估开发

BF16 官方基线和大规模训练使用显存更大的云 GPU。

## 当前状态

已完成 Stage 0 基础脚手架：

- 建立独立的 Python 3.10 Conda 环境。
- 实现严格的 NaVIDA action chunk parser 和原子动作展开。
- 当前 7 个单元测试全部通过。
- 尚未安装 Habitat、PyTorch、Transformers 或下载模型与数据集。

## 许可证说明

NaVIDA 官方模型页面标记为 Apache-2.0，但官方代码仓库当前未提供明确的 LICENSE 文件。

在许可证得到确认前，本仓库不直接复制官方源码，只根据论文协议和公开接口进行独立实现。
