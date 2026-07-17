# navida-habitat 项目开发路线图

## 1. 项目最终目标

本项目用于建立并验证以下完整技术链路：

NaVIDA 模型
→ Habitat 仿真
→ episode 日志
→ 批量评估
→ 失败分析
→ Jetson 可行性验证
→ 目标域适配
→ 向车辆部署仓库输出稳定接口

最终部署目标是在现有 Jetson Orin NX 上完成本地推理。Jetson 部署必须建立在 Habitat 基线完成、模型资源占用和推理延迟得到评测之后，不能跳过仿真验证直接以实车现象判断模型能力。

当前模型路线遵循以下原则：

- 优先直接使用官方 NaVIDA checkpoint 建立可复现基线。
- 不从随机参数重新预训练完整 VLM。
- mock test 不评估 NaVIDA 模型能力，只验证 parser、动作执行、episode 控制、日志和结果汇总组成的软件闭环。
- 是否进行 QLoRA、蒸馏或更小模型训练，必须由后续 Habitat 效果、失败分析和 Jetson 资源实验结果决定。

## 2. 仓库职责边界

### sceneeeee/navida-habitat

本仓库负责 NaVIDA 在 Habitat 中的独立评估、分析和适配，包括：

- strict action parser
- mock episode
- Habitat integration
- `official_repro`
- `paper_pure`
- batch evaluation
- failure analysis
- latency 和 memory profiling
- Jetson 模型推理可行性验证
- 目标域 QLoRA 或蒸馏实验

本仓库不包含 ROS2、Nav2、`cmd_vel` 和底盘代码，也不承担真实车辆的控制与安全仲裁。

### Yangbadger222/VLN

该仓库负责模型能力到机器人软件栈之间的最小部署层，包括：

- 模型服务接口
- HTTP client/server
- 相机历史帧输入
- ROS2 bridge
- action 到 `cmd_vel` 的部署映射
- watchdog 和安全停止
- 最小化部署接口测试

该仓库不复制 Habitat benchmark、数据集、训练和批量评估代码；这些工作及其科学协议继续由 `sceneeeee/navida-habitat` 维护。

### Yangbadger222/XJTLU-autonomous-vehicle-rtk

该仓库负责整车运行环境和车辆侧系统集成，包括：

- Jetson ROS2 系统
- 传感器、定位和 Nav2
- STM32 和底盘接口
- 车辆启动、日志、安全和控制仲裁

该仓库不放置 NaVIDA 训练和 Habitat 评测实现。

## 3. 评估协议

### official_repro

`official_repro` 用于验证官方 checkpoint、数据集、模型输入输出和评测链路。该协议应尽量复现官方 prompt、图像处理、历史帧采样、生成参数、parser 和执行策略。所有无法完全复现或需要独立实现的差异都应明确记录，避免将近似复现误报为完全复现。

### paper_pure

`paper_pure` 是项目的主要实验协议。模型输入只允许：

- 最多 8 张历史 RGB
- 当前 RGB
- 自然语言导航指令

该协议禁止使用：

- target distance
- target bearing
- simulator ground-truth pose
- depth、GPS、compass、top-down map
- Advisor
- Geometric Controller
- anti-stuck
- force-stop
- random fallback
- move-forward fallback

模型的有效输出不得被额外控制逻辑覆盖；无效输出必须完整记录，并立即以失败终止当前 episode。`official_repro` 与 `paper_pure` 的运行配置、日志和结果必须分开保存、分开汇总，不得混合报告。

## 4. 开发阶段

### Stage 0：基础脚手架

**状态：已完成。**

**目标**

建立不依赖 Habitat 和模型权重的最小 Python 工程，为后续闭环开发固定包结构和严格动作语义。

**主要工作**

- 建立 Python 3.10 独立 Conda 环境。
- 使用 `src` layout。
- 实现 strict action chunk parser 和原子动作展开。
- 使用 `unittest` 覆盖合法、非法输出和展开行为。
- 建立 Git 仓库并完成第一次 push。

**明确不做的内容**

- 不安装 Habitat、PyTorch 或 Transformers。
- 不加载 NaVIDA checkpoint。
- 不下载数据集。
- 不实现仿真或车辆控制。

**完成标准**

- 包结构可被独立导入。
- strict parser 能接受约定 grammar，并对任何无效输出抛出明确错误。
- action chunk 能按 25 cm 前进和 15 degree 转向展开为原子动作。
- 现有单元测试全部通过，基础代码已进入远端仓库。

### Stage 1：纯 Python mock episode loop

**目标**

在不安装 Habitat、不加载 NaVIDA 的条件下，先打通可测试、可终止、可追溯的软件闭环：

mock raw model text
→ strict parser
→ atomic actions
→ mock environment
→ episode runner
→ JSONL logs
→ result summary

**主要工作**

- 提供可预测的 mock raw model text 序列。
- 将模型文本通过 strict parser 转换为 action chunk，再展开为原子动作。
- 由 mock environment 记录动作和最小 episode 状态。
- 实现 episode runner 的正常停止、失败停止和 `max_steps` 终止。
- 输出逐步 JSONL 日志和 episode 级 result summary。
- 在日志中保留 raw output、parsed result 和 executed actions。
- 用测试验证 `stop` 正常终止、invalid output 失败终止、无 fallback，以及 `max_steps` 能防止死循环。

**明确不做的内容**

- 不安装或调用 Habitat。
- 不加载 NaVIDA checkpoint，也不对模型导航能力作任何结论。
- 不在解析失败后执行随机动作或 move-forward fallback。
- 不引入 simulator metrics、训练逻辑或车辆部署代码。

**完成标准**

- 正常序列能由 `stop` 明确结束并生成成功闭环日志。
- 任意 invalid output 都被记录并使 episode 以失败终止，且没有动作 fallback。
- 缺少 `stop` 的序列能由 `max_steps` 有界终止。
- 每一步均可从 JSONL 追溯 raw output、parsed result 和实际 executed actions。
- result summary 能区分 stop、invalid output 和 max-steps termination。

### Stage 2：Habitat + mock backend

**目标**

把 Stage 1 的 episode 闭环接入真实 Habitat 仿真，但仍使用 mock backend 隔离模型因素，验证场景、动作、渲染、日志和指标链路。

**主要工作**

- 安装并固定 Habitat-Sim 0.2.4 和 Habitat-Lab 0.2.4。
- 验证 scene loading、RGB rendering 和 headless/EGL 运行。
- 将原子动作映射为 forward 25 cm、turn 15 degree 和 stop。
- 接入 `max_steps`、episode log 和 metrics pipeline。
- 用确定性的 mock 输出检查动作轨迹与指标记录。

**明确不做的内容**

- 不加载 NaVIDA checkpoint。
- 不用 mock 结果评价 NaVIDA 的 SR、SPL 或泛化能力。
- 不加入 Advisor、Geometric Controller、anti-stuck、force-stop 或 fallback。
- 不进入 ROS2 或实车集成。

**完成标准**

- 固定场景能够在目标环境中稳定加载并输出 RGB。
- headless/EGL 可重复运行，不依赖交互式窗口。
- forward、turn、stop 的执行尺度与配置一致。
- `max_steps`、episode 日志和 metrics pipeline 对正常与异常终止均能给出可追溯结果。

### Stage 3：Habitat + 官方 NaVIDA

**目标**

接入官方 NaVIDA checkpoint，逐级隔离模型加载、单步调用、闭环控制和资源占用问题，形成首个真实模型 episode。

**主要工作**

按以下顺序推进：

1. 单次离线推理。
2. 单步 Habitat 推理。
3. 单个完整 episode。
4. 小批量 episode。
5. latency 和 memory profiling。

本地 RTX 4060 Ti 8GB 优先测试 4-bit 推理，并记录量化配置、显存峰值、生成延迟和失败信息。

**明确不做的内容**

- 不从随机参数预训练完整 VLM。
- 不在离线推理尚未稳定时直接开展批量评估。
- 不把单个 episode 的结果视为模型有效性结论。
- 不接入 ROS2、Nav2、`cmd_vel` 或底盘。

**完成标准**

- 官方 checkpoint 能完成可复现的离线图像与指令推理。
- 模型输出能通过同一 strict parser 接入单步 Habitat 动作执行。
- 至少一个完整 episode 能有界运行并保存完整日志。
- 小批量运行可复现，且延迟、GPU memory 和异常类型有明确记录。

### Stage 4：官方基线与严格纯模型评估

**目标**

分别建立官方复现基线与严格纯模型基线，确认官方 checkpoint 在统一数据划分和明确协议下的表现。

**主要工作**

- 先使用 R2R VLN-CE val-unseen。
- 按 `official_repro` 运行并记录所有官方复现假设与差异。
- 按 `paper_pure` 运行，仅提供允许的 RGB 历史、当前 RGB 和导航指令。
- 为两个协议使用独立配置、日志目录、结果汇总和报告表格。

**明确不做的内容**

- 不混合报告 `official_repro` 与 `paper_pure` 的结果。
- 不向 `paper_pure` 输入特权几何或其他被禁止的传感器信息。
- 不用 Advisor、Geometric Controller 或任何纠错 fallback 提高 `paper_pure` 指标。
- 不根据基线前的零散结果决定 QLoRA、蒸馏或更换 backbone。

**完成标准**

- 两种协议均能在 R2R VLN-CE val-unseen 上独立、可重复地运行。
- 每次运行均能从配置和日志确认输入、生成、parser 与执行策略。
- 两组结果在产物命名和报告中清晰分离，不存在指标混用。

### Stage 5：批量评估与失败分析

**目标**

将单次和小批量验证扩展为稳定的批量评估，并把总体指标与逐 episode 失败原因关联起来，为后续资源优化和目标域适配提供证据。

**主要工作**

批量记录和汇总：

- SR
- SPL
- NE
- OSR
- nDTW
- collision
- invalid-output rate
- step latency
- episode latency
- failure category

失败类型至少包括：

- model decision error
- invalid model output
- premature stop
- failure to stop
- trajectory drift
- max-steps termination
- environment or runtime error

同时保留足以复查分类的 episode 日志、动作序列、模型原始输出和运行错误上下文。

**明确不做的内容**

- 不只报告均值而丢失逐 episode 证据。
- 不把 runtime error 归因于 model decision error。
- 不把 invalid output 隐式转换为动作继续运行。
- 不在未按 scene 划分的数据上训练、选择或报告模型。

**完成标准**

- 固定数据划分上的批量任务可重复启动、恢复、汇总和审计。
- 所列指标都有明确计算来源和协议标签。
- 每个失败 episode 至少归入一个定义清晰的 failure category，环境错误与模型错误可区分。
- 失败分布能够支持是否需要 prompt、runtime、量化或目标域模型实验的下一步判断。

### Stage 6：Jetson 可行性验证

**目标**

在线下确认 Jetson 具体规格后，用资源和稳定性证据判断现有 Jetson Orin NX 是否适合本地运行 NaVIDA，以及需要哪一级优化。

**主要工作**

记录软硬件基线：

- Jetson 具体型号和内存版本
- JetPack、L4T、CUDA、TensorRT、Python、PyTorch

记录资源和运行表现：

- idle memory
- ROS2 runtime memory
- peak model memory
- steady-state memory
- swap
- P50/P95 latency
- temperature
- power mode
- continuous-run stability

根据证据决定后续路线：

- 保留 NaVIDA 3B 4-bit
- 优化推理 runtime
- 减少历史帧或视觉预算
- QLoRA
- 蒸馏
- 更小 backbone

QLoRA 只能调整模型行为和目标域适配方式，不能直接解决 3B 基座本身的推理内存问题；若主要问题是 OOM，必须优先评估量化、runtime、视觉预算、蒸馏或更小 backbone。

**明确不做的内容**

- 不在未确认 Jetson 型号、内存版本和软件栈时给出部署承诺。
- 不只测一次冷启动或单步延迟就判断可部署。
- 不把 OOM、慢速、量化损伤和模型导航错误混为一类。
- 不因 Jetson 资源不足而直接决定重新训练完整 VLM。

**完成标准**

- 环境版本、测量方法、模型配置和输入预算均可复现。
- 空闲、ROS2 共存、峰值和稳态内存均有测量，swap 使用情况明确。
- P50/P95 延迟、温度、功耗模式和连续运行稳定性均有记录。
- 能基于证据选择并说明保留 3B 4-bit、runtime 优化、减少视觉预算、QLoRA、蒸馏或更小 backbone 中的下一步。

### Stage 7：接入 VLN 部署仓库

**目标**

向 `Yangbadger222/VLN` 输出经过 Habitat 基线和 Jetson 资源验证的最小稳定接口，使部署层无需复制评测与训练实现。

**主要工作**

固定并测试以下接口：

history RGB + current RGB + instruction
→ raw action text
→ strict parser
→ normalized action chunks

明确图像顺序、历史帧上限、数据格式、请求响应 schema、超时和错误语义，并提供最小化接口契约测试。

**明确不做的内容**

- 不把 Habitat、数据集和训练代码复制进 `Yangbadger222/VLN`。
- 不在本仓库实现 ROS2 bridge、`cmd_vel` 映射、watchdog 或底盘控制。
- 不让部署层绕过 strict parser 或为 invalid output 添加 fallback。

**完成标准**

- VLN 部署仓库能仅依赖约定接口提交历史 RGB、当前 RGB 和指令，并获得规范化动作块或明确错误。
- raw action text、解析结果与错误状态可追溯。
- 接口契约测试覆盖正常动作、stop、invalid output、超时和服务错误。
- Habitat、数据集、训练和批量评估仍保留在本仓库边界内。

### Stage 8：整车验证

**目标**

在仿真基线、资源可行性和部署接口均通过验收后，完成受控条件下的整车闭环验证，并分析 sim-to-real 差异。

**主要工作**

- Jetson 本地模型服务
- ROS2 非阻塞推理
- stale-frame handling
- action calibration
- watchdog
- low-speed closed-area tests
- sim-to-real failure analysis

整车侧实现分别归属 `Yangbadger222/VLN` 和 `Yangbadger222/XJTLU-autonomous-vehicle-rtk`；本仓库提供已验证的模型接口、协议说明和分析依据，不越过既定仓库边界。

**明确不做的内容**

- 不在无 watchdog、安全停止和控制仲裁时进行车辆闭环测试。
- 不在开放道路或未经批准的非受控区域测试。
- 不用实车部署逻辑反向改变 `paper_pure` 科学协议。
- 不因单次实车失败直接启动模型重训。

**完成标准**

- 模型推理不会阻塞 ROS2 关键控制与安全流程。
- stale frame、服务超时、invalid output 和模型不可用均能触发确定、安全的处理。
- 动作映射经过低速标定，watchdog 和安全停止经过验证。
- 封闭区域连续测试有完整日志，并能将失败区分为模型决策、接口时序、动作标定、感知域差异或车辆系统问题。

## 5. 阶段推进原则

- 每一阶段通过验收后再进入下一阶段。
- mock 成功不代表 NaVIDA 模型有效；它只说明相应软件闭环按设计运行。
- Habitat 表现正常后，才有资格判断 Jetson 和实车问题。
- Jetson 表现差时，先区分 OOM、latency、量化损伤和 sim-to-real，再选择优化方向。
- 不因单次实车失败直接决定重新训练模型。
- 数据集必须按 scene 划分，避免训练、验证和测试之间的场景泄漏。
- 模型、数据集、日志、结果和视频不进入普通 Git。
- 所有指标、失败类别和资源数据必须带有协议、模型版本、数据划分与运行配置，确保结果可复查。

## 6. 当前状态与下一步

当前已完成 **Stage 0：基础脚手架**。仓库已经采用 Python 3.10 和 `src` layout，实现 strict action chunk parser、原子动作展开及对应 `unittest`；目前尚未安装 Habitat、加载模型或下载数据集。

当前唯一下一阶段是 **Stage 1：纯 Python mock episode loop**。

Stage 1 计划涉及以下文件：

- `src/navida_habitat/mock_backend.py`
- `src/navida_habitat/mock_env.py`
- `src/navida_habitat/episode_runner.py`
- `src/navida_habitat/episode_log.py`
- `scripts/run_mock_episode.py`
- `tests/test_mock_episode.py`

这些文件目前尚未实现，本次任务不创建它们。进入 Stage 1 后，应只围绕 mock episode 软件闭环实施和验收，不提前安装 Habitat 或加载 NaVIDA。
