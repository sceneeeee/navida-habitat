# SURF 结项报告：NaVIDA–Habitat 工程集成

> 文档整理日期：2026-11-07。**SURF 项目已经结束，但其实际结束日期未在本仓库核实。** 本文记录项目结束时可由仓库与合并 PR 追溯的工程成果，不表示今天重新进行了模型、场景或机器人实验。

## 1. 项目背景与结项结论

本仓库是 SURF 期间 NaVIDA 视觉语言导航方向的**模型推理与 Habitat 仿真对接工程**。研究期结束后，此路线不再作为正在执行的 SURF 任务推进。

**结项状态：工程集成链路已通过有限步 smoke test；正式 VLN benchmark、目标对齐的完整自主导航实验及实机部署均未完成。**

实际已展示的路径是：

~~~text
Habitat RGB observation
  -> RGB PNG/base64 over localhost HTTP
  -> Official NaVIDA checkpoint runtime (4-bit on local GPU)
  -> history + current frame + navigation instruction
  -> strict action-chunk parsing
  -> server-side atomic-action queue
  -> one atomic action per simulator step
  -> Habitat env.step / trajectory & media artifacts
~~~

请勿将该路径中“模型产生了可执行动作”表述为“完成了指令导航任务”或“在标准基准中取得了成功率”。

## 2. 仓库与团队边界

- **本仓库：** checkpoint runtime、RGB 历史采样、Policy API、严格 action parser、episode/decision/action-queue 状态、HTTP 服务、模型侧测试与单场景有限步 CLI。
- **协作仓库：** [RtimesC/habitat-lab](https://github.com/RtimesC/habitat-lab) 负责 Habitat evaluator、episode、仿真动作、轨迹、逐帧图像和视频等评估侧功能。本仓库的代码和验证结果不能自动代表该协作仓库的全部成果。
- **团队归属：** SURF 团队研究项目。GitHub PR #1–#6 的提交记录可用于核查仓库级改动；申请材料中对“本人负责”与“团队负责”的划分仍应结合 SURF 的真实分工逐项核对。

## 3. 实际完成的工程工作

| 模块 | 可核实的产出 | 代码或记录 |
| --- | --- | --- |
| Python 基础设施 | Python 3.10、src layout、strict parser、25 cm/15° 原子动作语义 | src/navida_habitat/action_chunk.py |
| Mock episode | 可终止、可审计的 fake-model / fake-environment 运行闭环 | src/navida_habitat/episode_runner.py；PR #1 |
| Habitat-Sim 接口 | RGB observation、真实场景动作映射、单场景联调 | src/navida_habitat/habitat_env.py；PR #2 |
| 官方 checkpoint 适配 | 资源受限 GPU 上的 4-bit 模型加载、图像历史与推理 | src/navida_habitat/model_runtime.py、navida_backend.py；PR #3 |
| 评估侧 Policy API | episode reset、observe、act；解析结果及元数据 | src/navida_habitat/policy.py；PR #5 |
| 本地推理服务 | /health、/v1/episodes/start、/v1/steps；严格字段校验、队列与状态锁 | src/navida_habitat/http_service.py；PR #6 |

**精确的 Stage 3 表述：** 已完成真实 checkpoint 和 Habitat 的推理/动作执行集成，并通过有限步验证；但早期路线图中要求的“完整指令对齐 episode、小批量导航验证和稳定 benchmark”并未全部完成。因此，不能笼统标记为整阶段所有验收项完成。

## 4. 验证证据（历史记录，非本次重测）

主要依据：[PR #6：Official NaVIDA HTTP Server](https://github.com/sceneeeee/navida-habitat/pull/6)，以及合并前的 Stage 2 环境记录。

| 证据 | 历史记录 | 可以支持的结论 |
| --- | --- | --- |
| 自动化测试 | 88 tests，87 passed，1 opt-in real-scene integration test skipped | 当时的 parser/Policy/HTTP/mock 等回归测试通过；不是今天的重测 |
| 模型推理 | 官方 checkpoint 在 RTX 4060 Ti 8GB 上以 4-bit 路线调用成功 | 本地特定环境可加载、运行模型 |
| 显存 | 峰值 allocated GPU memory 约 3.12 GiB | 该次记录中的 allocated 数值，不是总显存、持续稳定内存或跨设备部署保证 |
| 模型与 Habitat 联调 | 1 个随机 PointNav 测试 episode，5 个 simulator steps | 模型动作可通过 HTTP 到达 Habitat；不是指令对齐的导航成功率 |
| 产物 | 轨迹 CSV、逐步 RGB 帧、MP4 在测试环境中生成 | 证明当时生成了工程产物；媒体并未发布在本仓库，不能声称当前公开可下载 |
| 动作审计 | 保留 raw output、parsed sub-chunks、执行/忽略数量和队列复用信息 | 可追踪从模型输出到仿真动作的转换 |

PR #6 明确指出：当时的自然语言指令**未与随机 PointNav 目标对齐**，因此不能将该 episode 的 success、SPL 等值用于正式 VLN 比较。验证细节见 [validation-report.md](validation-report.md)。

## 5. 方法与复现限制

- 本实现只开放严格的 **paper_pure** 路径：历史 RGB、当前 RGB 和文字指令；禁止把目标距离、方位、ground-truth pose、深度、GPS、compass 或 top-down map 传入模型。
- parser 最多接受 3 个合法 sub-chunks，默认仅执行前 2 个；按 25 cm 或 15° 细分原子动作。
- 对无效模型输出，本实现返回错误且不注入随机/前进 fallback；配对 evaluator 应当终止该 episode。**这与官方 evaluator 的某些容错策略不同**，不可称为逐位忠实复现。
- HTTP 服务在一个进程内管理单一活动 episode，提供有序 step 校验；其用途是本地仿真联调，不是互联网生产服务。
- 模型权重、场景数据、完整测试日志、视频未纳入本仓库，复现真实场景/模型需要自行取得合法访问权限。
- 本仓库没有根目录 LICENSE。官方模型的授权信息不等同于官方代码或本仓库的许可；复用与发布需单独核查。

## 6. 未完成与不再纳入 SURF 交付的事项

- 指令、起点、目标相匹配的**完整自主导航** episode。
- 标准 R2R VLN-CE / RxR 数据集验证，scene-disjoint 评测，以及 SR、SPL、NE、nDTW 等正式指标。
- 成批实验、统计显著性、跨场景泛化、系统化失败分析。
- Jetson/ROS 2/FrogBot/其他机器人上的真实硬件闭环和安全验证。
- 论文复现所要求的全面协议对齐。

这些是**原计划但未完成**的工作，不应作为简历已完成成果。未来如独立继续做 Habitat 仿真，应单独注明为“Post-SURF follow-up”；如希望使用 FrogBot，须重新获得导师及设备管理方授权，不能把可能的未来实机实验算作本次 SURF 交付。

## 7. 结项后的维护规则

1. 本次只整理证据和文档，不扩展算法、训练模型或补造评测结果。
2. README 与 roadmap 的状态必须与本结项报告一致，历史 Stage 2 记录保留并注明其时间上下文。
3. 不在 Git 中提交模型权重、数据集、运行日志、结果表或视频；若以后发布 Demo，应提供有权限的独立链接并说明采集条件。
4. 不擅自发布 Release、打 tag、合并主分支或将仓库标为 archived；这些属于单独的项目管理决策。
5. 面向申请的英文案例见 [portfolio-case-study.md](portfolio-case-study.md)；HTTP 契约见 [api-contract.md](api-contract.md)。

**可对外使用的结项描述：** “During SURF, developed and validated a stateful NaVIDA-to-Habitat inference integration with strict action parsing and auditable atomic-action execution. Validation covered automated regression tests and a five-step real-checkpoint simulation smoke test; no official VLN benchmark or physical-robot deployment was completed.”
