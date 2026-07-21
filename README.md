# navida-habitat

在 Habitat 中运行、评估和适配纯 NaVIDA 模型的独立仓库。

本仓库的核心目标是建立一条可审计的实验链路：

`官方 NaVIDA checkpoint → Habitat 仿真 → episode 日志 → 标准 VLN 指标 → 批量评估 → 失败分析 → 目标域适配`

## 当前定位

本仓库专门负责以下路线：

- 直接加载官方 NaVIDA-3B checkpoint。
- 使用历史 RGB、当前 RGB 和自然语言指令进行闭环导航。
- 尽量复现官方 prompt、历史帧采样、生成参数和文本 action chunk grammar。
- 明确区分 `official_repro` 与 `paper_pure` 两种评估协议。
- 保存模型原始输出、解析结果、实际执行动作、延迟、token 数和显存占用。
- 后续接入标准 R2R VLN-CE episode、SR、SPL、NE、OSR 和失败分类。
- 只有在官方 checkpoint 的目标域问题得到验证后，才开展 IDS + QLoRA 适配。

## 与 `RtimesC/habitat-lab` 的关系

本仓库不替代完整的 Habitat-Lab 工程仓库。

- `sceneeeee/navida-habitat`：官方 NaVIDA、纯模型协议、严格 parser、科学评估和后续目标域适配。
- `RtimesC/habitat-lab`：Habitat-Lab 标准 episode、Advisor + Geometric Controller、Oracle/Geometric baseline、视频、轨迹、数据收集和工程 guard。

两个仓库可以共享数据集和评估定义，但不应各自维护一套名称相同、行为不同的“官方 NaVIDA”。

## 不属于本仓库的内容

- Advisor + Geometric Controller
- 将目标距离或目标方位写入模型 prompt
- 普通单步 Qwen baseline
- anti-stuck 动作覆盖
- force-stop-within-success-radius
- 无效输出后的随机动作或 move-forward fallback
- ROS2、Nav2、`cmd_vel` 和真实小车部署
- YOLO、展示素材和其他无关模块

这些内容可以在独立工程路线中实现，但不得与 `paper_pure` 结果混合报告。

## 固定的上游版本

- NaVIDA paper: arXiv:2601.18188v2
- NaVIDA code commit: `b86316a78a2865c80b445ed5a8fcc08fc0243dfb`
- NaVIDA checkpoint revision: `0ccd8b6b3cd0826c5dd67374415ceedf51adb9e2`
- Backbone: Qwen2.5-VL-3B
- Python: 3.10
- Habitat-Sim: 0.2.4
- Habitat-Lab: 0.2.4
- Transformers: 4.50.3

Habitat-Lab 和 Habitat-Sim 作为固定版本的外部依赖，不复制到本仓库中。模型权重、数据集、评估视频和运行缓存也不得提交到普通 Git。

## 模型输入和输出

### 输入

论文协议中的模型输入仅包括：

- 最多 8 张均匀采样的历史 RGB 图像
- 1 张当前 RGB 图像
- 自然语言导航指令

默认图像尺寸为 `308 × 252`。

模型不读取：

- target distance
- target bearing
- simulator ground-truth pose
- depth
- GPS
- compass
- top-down map

首个决策没有历史帧时，runtime 按官方实现将当前帧同时作为历史输入和当前输入。

### 输出

官方模型输出普通文本 action chunks，例如：

```text
forward 50 cm, turn left 30 degree
```

当前原子动作定义：

- `forward 25 cm`
- `turn left 15 degree`
- `turn right 15 degree`
- `stop`

parser 会将带距离或角度的 chunk 展开为 Habitat 原子动作。

## 评估协议

### `official_repro`

尽量复现官方 checkpoint、processor、prompt、历史采样、生成参数、parser 和 chunk 执行策略，用于验证模型、数据集和 Habitat 接口是否正确连通。

当前本地运行使用：

- 4-bit NF4 量化
- BF16 compute
- SDPA attention
- batch size 1

这是一条面向 RTX 4060 Ti 8GB 的资源适配路线，不应表述为完整 BF16 + FlashAttention 官方环境的逐位复现。

### `paper_pure`

主要科学实验协议，只允许论文定义的模型输入。

该协议必须满足：

- 不使用目标距离或目标方位控制动作。
- 不使用 Advisor 或 Geometric Controller。
- 不覆盖模型生成的有效动作。
- 无效输出记录为 `invalid output` 并立即终止为失败。
- 不使用随机动作、forward fallback、anti-stuck 或 force-stop。
- 只允许使用明确记录的最大步数限制。
- 保存原始模型输出、解析结果和实际执行动作。

`official_repro` 与 `paper_pure` 的结果必须分开报告。

## 当前代码结构

```text
scripts/run_navida_habitat.py
    正式单 episode CLI，加载真实 checkpoint 并运行有限步闭环。

src/navida_habitat/model_runtime.py
    官方 NaVIDA checkpoint 的 lazy-loading Hugging Face runtime。

src/navida_habitat/frame_history.py
    有界 RGB 历史缓存和官方端点保留均匀采样。

src/navida_habitat/navida_backend.py
    Habitat RGB → NaVIDA 推理 → 决策记录。

src/navida_habitat/policy.py
    面向外部 evaluator 的 paper_pure Official NaVIDA Policy API。

src/navida_habitat/episode_runner.py
    parser、动作执行、终止状态和 JSONL episode 日志。

src/navida_habitat/habitat_env.py
    Habitat-Sim environment adapter、RGB observation 和 agent state。
```

## Official NaVIDA Policy Python API

外部 evaluator 可以注入一个实现 `NaVIDARuntimeProtocol` 的 runtime，按
episode 生命周期调用 Policy。Policy 只接收 RGB、指令、决策步和 episode ID，
不持有 Habitat 环境，也不执行动作或计算评估指标。

```python
from navida_habitat import OfficialNaVIDAPolicy
from navida_habitat.action_chunk import HabitatAction

policy = OfficialNaVIDAPolicy(runtime=runtime, protocol="paper_pure")

try:
    policy.reset("episode-1")
    policy.observe(initial_rgb)

    decision = policy.act(
        instruction="Walk through the doorway.",
        decision_step=0,
    )

    if decision.valid:
        for action in decision.atomic_actions:
            evaluator.execute(action)
            if evaluator.is_done():
                break
            policy.observe(evaluator.current_rgb)
    else:
        evaluator.record_invalid_output(decision.to_dict())
finally:
    policy.close()
```

`decision.atomic_actions` 是 `tuple[HabitatAction, ...]`，Policy 默认只展开
模型输出的前两个 sub-chunks。严格 parser 失败时，decision 会保留完整
`raw_output` 和 parser 错误，同时返回空的 `parsed_sub_chunks` 与
`atomic_actions`，不产生 STOP 或移动 fallback。

同一个 Policy/runtime 可以跨多个 episode 复用；每次 `reset()` 会清除历史帧、
决策记录、上一条生成结果和当前 RGB，但不会重新初始化模型。`close()` 可重复调用，
只会在 runtime 提供 `close()` 时调用一次。当前公共 API 只正式支持
`protocol="paper_pure"`；`official_repro` 尚未实现并会显式抛出
`NotImplementedError`。

## 已完成阶段

### Stage 0：parser 与工程骨架

- Python 3.10 `src` layout
- 严格 action chunk parser
- 距离和角度到原子动作的展开
- 基础单元测试

### Stage 1：纯 Python episode loop

- `MockBackend`
- mock environment
- 有界 episode loop
- STOP、invalid output 和 max-steps 终止
- JSONL 日志

### Stage 2：真实 Habitat-Sim 接入

- Habitat-Sim 0.2.4 environment adapter
- RGB observation
- agent position 和 yaw 日志
- 原子动作映射
- 真实测试场景闭环

### Stage 3：官方 NaVIDA checkpoint 接入

已完成：

- 官方 NaVIDA checkpoint 的本地 4-bit 加载
- 官方 system prompt 和导航 prompt
- 历史 RGB 与当前 RGB 的多模态输入
- 官方端点保留历史帧采样
- generation token、延迟和显存峰值记录
- 严格 parser 与 Habitat 动作执行
- 正式 CLI
- 两次连续真实模型决策闭环
- summary JSON、episode JSONL、初始帧和最终帧产物

本地测试状态：

```text
40 passed, 1 skipped, 16 subtests passed
```

真实双决策验证中：

- 第一次决策使用 0 张真实历史帧。
- 执行动作后缓存 4 张历史帧。
- 第二次决策使用 4 张历史帧。
- input token 数从 295 增加到 598。
- 峰值 allocated VRAM 从约 2.41 GiB 增加到约 3.11 GiB。

该结果证明：

`official NaVIDA runtime → RGB history → strict parser → EpisodeRunner → Habitat-Sim → JSONL`

已经形成真实多决策闭环。

该 smoke test 没有正式 navigation goal，因此 `success=false` 和 `termination_reason=max_steps` 不代表模型评测失败，也不能作为 SR、SPL 或泛化结果。

## 快速测试

普通 parser、mock loop 和单元测试不要求安装 Habitat 或加载模型：

```bash
PYTHONPATH="$PWD/src" python -m pytest -q
```

真实运行要求：

- CUDA 可用
- 本地官方 checkpoint
- Habitat-Sim 0.2.4 Python path
- 可用的 GLX/EGL 渲染环境
- 本地 Habitat scene

示例：

```bash
export DISPLAY=:0
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PYTHONPATH="/path/to/habitat-sim/src_python:$PWD/src"

python -u scripts/run_navida_habitat.py \
  --scene-path /path/to/scene.glb \
  --model-path /path/to/NaVIDA/checkpoint \
  --instruction "Walk forward through the room and stop near the doorway." \
  --episode-id example-episode \
  --max-steps 2 \
  --max-new-tokens 128 \
  --output-dir /tmp/navida_habitat_run
```

输出包括：

- `episode.jsonl`
- `summary.json`
- `initial_rgb.png`
- `final_rgb.png`

## 下一阶段

### Stage 4：标准 VLN episode 与指标

下一阶段目标：

1. 读取标准 VLN episode 的 scene、instruction、start position、start rotation 和 goal。
2. 在 reset 时恢复标准起点和朝向。
3. 接入 Success、SPL、NE 和 OSR。
4. 支持 R2R VLN-CE `val_seen` 与 `val_unseen`。
5. 保存每步 RGB、轨迹、碰撞、原始输出和视频。
6. 支持单 episode、batch evaluation 和 failure analysis。

在没有 MP3D/R2R 完整数据前，HM3D 或 Habitat test scene 只用于 plumbing smoke test，不作为 R2R benchmark 替代品。

## 数据集计划

1. 首先在 R2R VLN-CE `val_seen` 上完成数据和指标链路验证。
2. 再在 `val_unseen` 上报告官方 checkpoint 的泛化基线。
3. HM3D PointNav smoke 只用于检查 RGB、动作、渲染、日志和指标链路。
4. 纯 VLN 的 HM3D 测试必须使用与目标轨迹绑定的自然语言指令。
5. 训练集、验证集和测试集必须按 scene 划分，避免场景泄漏。
6. HM3D、MP3D、模型权重、训练图像和评估视频不得提交到普通 Git。

## 模型适配路线

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

完整 BF16 官方基线和大规模训练需要显存更大的云 GPU。

## 许可证说明

NaVIDA 官方模型页面标记为 Apache-2.0，但官方代码仓库当前未提供明确的 LICENSE 文件。

在许可证得到确认前，本仓库不直接复制官方源码，只根据论文协议和公开接口进行独立实现。
