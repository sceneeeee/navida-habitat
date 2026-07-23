# navida-habitat

在 Habitat 中运行官方 NaVIDA checkpoint 的独立推理服务与严格 `paper_pure` 协议实现。

本仓库当前负责模型侧：

```text
Official NaVIDA checkpoint
        ↓
历史 RGB + 当前 RGB + 自然语言指令
        ↓
严格 action-chunk parser
        ↓
有状态 localhost HTTP service
        ↓
Habitat evaluator 执行原子动作并记录结果
```

## 当前状态

官方 NaVIDA 与 Habitat 的真实闭环已经打通：

- 官方 NaVIDA-3B checkpoint 可以在 RTX 4060 Ti 8GB 上以 4-bit 方式加载。
- 模型接收历史 RGB、当前 RGB 和自然语言指令。
- 模型文本输出会被严格解析为 Habitat 原子动作。
- 服务端维护 episode 生命周期、历史帧、决策步和待执行动作队列。
- `RtimesC/habitat-lab` 已接入本仓库的 HTTP 服务，并负责 Habitat episode、动作执行、轨迹、图片、视频和指标。
- 已完成真实 checkpoint 的多步端到端 smoke test。
- 已完成合并后的 HTTP health check 和客户端回归测试。

当前已经证明的是：

```text
模型加载 → 图像与指令输入 → 模型推理 → 动作解析 → HTTP 传输
→ Habitat env.step → 轨迹与媒体产物
```

当前 smoke test 不是标准 R2R benchmark，因此不能将其中的 `success` 或 `SPL` 当作论文复现结果。

## 双仓职责

### `sceneeeee/navida-habitat`

负责：

- 官方 NaVIDA checkpoint runtime
- 官方 prompt 与历史帧采样
- 严格 action-chunk parser
- `paper_pure` 协议
- 服务端 action queue
- 原始模型输出、解析结果、延迟和显存元数据
- localhost HTTP API

### `RtimesC/habitat-lab`

负责：

- Habitat-Lab 标准 episode
- RGB observation 和 simulator step
- Official NaVIDA HTTP client adapter
- trajectory CSV
- 逐步 JPG 与 MP4
- Success、SPL、distance 等环境指标
- batch evaluation 和 failure analysis
- 独立的 Advisor + Geometric Controller 工程路线

两个仓库共享协议，但不各自维护行为不同的“官方 NaVIDA”实现。

## `paper_pure` 协议

`paper_pure` 是当前正式支持的 Official NaVIDA 协议，只允许使用论文定义的模型输入。

模型输入：

- 最多 8 张均匀采样的历史 RGB 图像
- 1 张当前 RGB 图像
- 自然语言导航指令

模型不读取：

- target distance
- target bearing
- simulator ground-truth pose
- depth
- GPS
- compass
- top-down map

执行约束：

- 不使用 Advisor 或 Geometric Controller。
- 不覆盖模型生成的有效动作。
- 不使用随机动作或 move-forward fallback。
- 不使用 anti-stuck。
- 不使用 privileged goal-distance force stop。
- 无效输出立即记录为失败，不伪造 STOP 或移动动作。
- 只允许使用明确记录的最大步数限制。
- 保存原始输出、解析结果和实际执行动作。

## 模型输出与原子动作

官方模型输出文本 action chunks，例如：

```text
forward 50 cm, turn left 30 degree
```

当前 Habitat 原子动作定义：

- `move_forward`：前进 25 cm
- `turn_left`：左转 15°
- `turn_right`：右转 15°
- `stop`

Policy 默认解析模型输出的前两个 sub-chunks，再将距离和角度展开成原子动作。HTTP 服务按 simulator step 逐个返回队列中的原子动作；队列耗尽后才触发下一次模型推理。

## HTTP API

默认监听地址：

```text
http://127.0.0.1:8008
```

### Health check

```http
GET /health
```

响应示例：

```json
{"status":"ok","policy":"official_navida","protocol":"paper_pure"}
```

### 开始 episode

```http
POST /v1/episodes/start
Content-Type: application/json
```

```json
{"episode_id":"episode-0"}
```

该请求会清除上一 episode 的历史帧、动作队列和决策状态，但不会重新加载模型。

### 执行一步

```http
POST /v1/steps
Content-Type: application/json
```

```json
{
  "episode_id":"episode-0",
  "simulator_step":0,
  "instruction":"Walk through the doorway and turn left.",
  "rgb_png_base64":"..."
}
```

服务端严格检查 episode ID、step 顺序、PNG 数据和请求字段。

## 启动 Official NaVIDA 服务

环境要求：

- Python 3.10
- CUDA
- Transformers 4.50.3
- bitsandbytes
- 本地官方 NaVIDA checkpoint

```bash
cd /path/to/navida-habitat
conda activate navida_habitat_stage3

export PYTHONPATH="$PWD/src"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python scripts/run_official_navida_http_server.py \
  --model-path /path/to/NaVIDA/checkpoint \
  --host 127.0.0.1 \
  --port 8008
```

另一个终端检查：

```bash
curl -fsS http://127.0.0.1:8008/health
```

模型 runtime 采用 lazy loading；`/health` 不会触发 checkpoint 加载，第一次真实 inference 才会加载模型。

## Habitat 客户端

Habitat evaluator 位于：

```text
https://github.com/RtimesC/habitat-lab
```

客户端通过以下模式连接本服务：

```bash
python habitat_vln/habitat_vln_nav.py \
  --official-navida-http \
  --official-navida-url http://127.0.0.1:8008 \
  --policy-protocol paper_pure \
  --frequency-mode joint \
  --joint-hz 1 \
  --num-episodes 1 \
  --max-steps 80
```

正式运行还需要提供对应的 Habitat task config、dataset path 和 scene directory。

## 独立 Habitat-Sim CLI

仓库仍保留模型侧的有限步单场景 CLI：

```bash
export DISPLAY=:0
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

完整逐步图片、视频、trajectory CSV 和标准 Habitat 指标由 `RtimesC/habitat-lab` 生成。

## 当前代码结构

```text
scripts/run_official_navida_http_server.py
    启动有状态 Official NaVIDA localhost HTTP server。

scripts/run_navida_habitat.py
    单场景有限步 Habitat-Sim CLI。

src/navida_habitat/model_runtime.py
    官方 checkpoint 的 lazy-loading Hugging Face runtime。

src/navida_habitat/frame_history.py
    有界 RGB 历史缓存和端点保留均匀采样。

src/navida_habitat/policy.py
    Official NaVIDA paper_pure Policy API。

src/navida_habitat/action_chunk.py
    严格 action-chunk parser 与原子动作展开。

src/navida_habitat/http_service.py
    episode、step、action queue 和 HTTP transport。

src/navida_habitat/episode_runner.py
    本地 episode loop、终止状态和 JSONL 日志。

src/navida_habitat/habitat_env.py
    Habitat-Sim environment adapter。
```

## 测试

普通 parser、Policy、HTTP service 和 mock episode 测试不要求加载真实模型：

```bash
cd /path/to/navida-habitat
conda activate navida_habitat_stage3
export PYTHONPATH="$PWD/src"
python -m pytest -q
```

最近一次合并验证包括：

- action chunk 测试
- Policy 生命周期测试
- HTTP service 与协议测试
- 完整测试集 88 项，其中 87 项通过、1 项 opt-in integration test 跳过
- RTX 4060 Ti 8GB 上真实 checkpoint smoke test
- 与 Habitat 客户端的 5-step 端到端闭环
- 合并后独立端口启动和 `/health` 验证

## 数据集与 Demo 路线

### 当前：HM3D 工程 Demo

当前优先使用 HM3D 或其他合法 Habitat 场景，制作 instruction-aligned 工程 demo：

- 为场景定义明确起点、朝向和目标。
- 编写与实际目标和路径对应的自然语言指令。
- 使用真实 Official NaVIDA checkpoint 自主决策。
- 保存 MP4、GIF、逐步 JPG、trajectory CSV 和模型元数据。
- 报告是否 STOP、最终距离、碰撞和失败原因。

该结果用于验证工程闭环和观察跨场景泛化，不作为官方 R2R/RxR benchmark。

### 后续：MP3D + R2R VLN-CE

论文级或正式 benchmark 阶段再接入：

- Matterport3D scenes
- R2R VLN-CE `val_seen`
- R2R VLN-CE `val_unseen`
- Success、SPL、NE、OSR、nDTW
- batch evaluation 和 failure analysis

R2R episode 绑定 MP3D 的 scene ID、起点、朝向、目标和参考路径，因此 HM3D 结果不能与 R2R 论文指标直接比较。

项目当前计划是先完成 HM3D 工程 demo；在论文阶段正式使用 MP3D/R2R 数据前，再联系数据集维护者并完成所需授权确认。

数据集、场景、模型权重、训练图像和评估视频不得提交到普通 Git。

## 下一阶段

下一阶段交付目标：

1. 构造一个 instruction、起点、路径和目标相匹配的 HM3D episode。
2. 跑通一个完整 Official NaVIDA 自主导航 episode。
3. 输出 MP4、GIF、关键帧、trajectory CSV 和结果摘要。
4. 扩展到 5 个 episode 小批量。
5. 分类提前停止、路口走错、连续旋转、非法输出和 max-steps 等失败。
6. MP3D/R2R 条件成熟后，再运行正式 benchmark。

## 固定上游版本

- NaVIDA paper：arXiv:2601.18188v2
- NaVIDA code commit：`b86316a78a2865c80b445ed5a8fcc08fc0243dfb`
- NaVIDA checkpoint revision：`0ccd8b6b3cd0826c5dd67374415ceedf51adb9e2`
- Backbone：Qwen2.5-VL-3B
- Python：3.10
- Habitat-Sim：0.2.4
- Habitat-Lab：0.2.4
- Transformers：4.50.3

本地 RTX 4060 Ti 8GB 路线使用：

- 4-bit NF4
- BF16 compute
- SDPA attention
- batch size 1

这是一条面向 8GB 显存的资源适配路线，不应表述为完整 BF16 + FlashAttention 官方环境的逐位复现。

## 不属于本仓库的内容

- Advisor + Geometric Controller
- 将目标距离或目标方位写入 NaVIDA prompt
- anti-stuck 动作覆盖
- force-stop-within-success-radius
- 无效输出后的随机动作或 move-forward fallback
- ROS2、Nav2、`cmd_vel` 和真实小车部署
- YOLO 或其他无关展示模块

这些路线可以在独立工程中实现，但不得与 `paper_pure` 结果混合报告。

## 模型适配原则

第一阶段先使用官方 checkpoint 建立可审计基线。

只有当官方模型在 scene-disjoint、grounded-instruction 验证集上表现出明确目标域问题后，才考虑 IDS + QLoRA。当前不计划从随机参数开始预训练完整 VLM。

## 许可证

NaVIDA 官方模型页面标记为 Apache-2.0，但官方代码仓库当前未提供明确的 LICENSE 文件。在许可证得到确认前，本仓库不直接复制官方源码，只根据论文协议和公开接口进行独立实现。
