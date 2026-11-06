# SURF 结项报告：NaVIDA–Habitat 工程集成

> 文档整理日期：2026-11-07。**SURF 项目已经结束，但其实际结束日期未在本仓库核实。** 本文记录项目结束时可由仓库与合并 PR 追溯的工程成果，不表示今天重新进行了模型、场景或机器人实验。

## 1. 项目背景与结项结论

本仓库是 SURF 期间 NaVIDA 视觉语言导航方向的**模型推理与 Habitat 仿真对接工程**。研究期结束后，此路线不再作为正在执行的 SURF 任务推进。

**结项状态：已完成真实 checkpoint 的五步链路联调，以及协作仓库中一个目标对齐、80 步但未成功抵达目标的仿真实验；正式 VLN benchmark 和实机部署均未完成。**

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
- **团队归属及个人提交：** 该仓库主分支历史 17 条提交全部由 Git 作者 `evenS`（GitHub `sceneeeee`）署名，PR #1–#6 均由 `sceneeeee` 提交；协作仓库 `RtimesC/habitat-lab` 的 PR #4、#5 也由 `sceneeeee` 提交。可以据此描述账号承担模型侧集成与部分 evaluator 侧适配/Demo 的工程责任，**不能据此证明所有代码均由本人逐行手写，或将整个团队的 evaluator 框架归为个人成果**。逐项来源见 [贡献核查](contribution-audit.md)。

## 3. 实际完成的工程工作

| 模块 | 可核实的产出 | 代码或记录 |
| --- | --- | --- |
| Python 基础设施 | Python 3.10、src layout、strict parser、25 cm/15° 原子动作语义 | src/navida_habitat/action_chunk.py |
| Mock episode | 可终止、可审计的 fake-model / fake-environment 运行闭环 | src/navida_habitat/episode_runner.py；PR #1 |
| Habitat-Sim 接口 | RGB observation、真实场景动作映射、单场景联调 | src/navida_habitat/habitat_env.py；PR #2 |
| 官方 checkpoint 适配 | 资源受限 GPU 上的 4-bit 模型加载、图像历史与推理 | src/navida_habitat/model_runtime.py、navida_backend.py；PR #3 |
| 评估侧 Policy API | episode reset、observe、act；解析结果及元数据 | src/navida_habitat/policy.py；PR #5 |
| 本地推理服务 | /health、/v1/episodes/start、/v1/steps；严格字段校验、队列与状态锁 | src/navida_habitat/http_service.py；PR #6 |
| Habitat 端 HTTP adapter（协作仓库） | RGB PNG/base64、服务调用、paper_pure 动作执行和轨迹元数据 | [RtimesC/habitat-lab PR #4](https://github.com/RtimesC/habitat-lab/pull/4)，由 sceneeeee 提交 |
| 目标对齐单场景 Demo（协作仓库） | 确定性 episode 生成、80 步模型运行、轨迹与视频输出 | [RtimesC/habitat-lab PR #5](https://github.com/RtimesC/habitat-lab/pull/5)，由 sceneeeee 提交；模型导航失败 |

**精确的 Stage 3 表述：** 模型侧集成与有限步联调已完成，并在协作仓库中跑过一个目标对齐的单场景 80 步 episode（NaVIDA 导航失败）。**小批量、跨场景和正式 benchmark** 尚未完成，因此原 Stage 3 的全部验收标准并未满足。

## 4. 验证证据（历史记录，非本次重测）

主要依据：[本仓库 PR #6：Official NaVIDA HTTP Server](https://github.com/sceneeeee/navida-habitat/pull/6)、[协作仓库 PR #4](https://github.com/RtimesC/habitat-lab/pull/4) 与 [PR #5：Grounded Demo](https://github.com/RtimesC/habitat-lab/pull/5)，以及历史 Stage 2 环境记录。

| 证据 | 历史记录 | 可以支持的结论 |
| --- | --- | --- |
| 自动化测试 | 88 tests，87 passed，1 opt-in real-scene integration test skipped | 当时的 parser/Policy/HTTP/mock 等回归测试通过；不是今天的重测 |
| 模型推理 | 官方 checkpoint 在 RTX 4060 Ti 8GB 上以 4-bit 路线调用成功 | 本地特定环境可加载、运行模型 |
| 显存 | 峰值 allocated GPU memory 约 3.12 GiB | 该次记录中的 allocated 数值，不是总显存、持续稳定内存或跨设备部署保证 |
| 模型与 Habitat 联调 | 1 个随机 PointNav 测试 episode，5 个 simulator steps | 模型动作可通过 HTTP 到达 Habitat；其指令与目标不匹配 |
| 目标对齐 Demo（协作仓库 PR #5） | 1 个 `skokloster-castle` 测试场景 episode，真实模型运行 80 步，STOP；NaVIDA success=0、SPL=0、最终目标距离约 8.620 m | **模型未找到目标**；是单场景工程实验，不是 R2R/RxR/MP3D/HM3D 正式指标 |
| Oracle 对照（同一 Demo） | Oracle success=1、SPL=1、0 次碰撞，终点距离约 0.055 m | 仅验证场景、导航目标、评估链路配置；**不是 NaVIDA 的结果** |
| 产物 | 轨迹 CSV、逐步 RGB 帧、MP4 在测试环境中生成 | 证明当时生成了工程产物；媒体并未发布在本仓库，不能声称当前公开可下载 |
| 动作审计 | 保留 raw output、parsed sub-chunks、执行/忽略数量和队列复用信息 | 可追踪从模型输出到仿真动作的转换 |

PR #6 的五步联调中，自然语言指令**未与随机 PointNav 目标对齐**。随后，协作仓库 PR #5 实现了目标对齐测试，但 NaVIDA **运行 80 步后在错误位置 STOP，success=0**。两者都不能被表述为标准 VLN benchmark。验证细节见 [validation-report.md](validation-report.md)。

## 5. 方法与复现限制

- 本实现只开放严格的 **paper_pure** 路径：历史 RGB、当前 RGB 和文字指令；禁止把目标距离、方位、ground-truth pose、深度、GPS、compass 或 top-down map 传入模型。
- parser 最多接受 3 个合法 sub-chunks，默认仅执行前 2 个；按 25 cm 或 15° 细分原子动作。
- 对无效模型输出，本实现返回错误且不注入随机/前进 fallback；配对 evaluator 应当终止该 episode。**这与官方 evaluator 的某些容错策略不同**，不可称为逐位忠实复现。
- HTTP 服务在一个进程内管理单一活动 episode，提供有序 step 校验；其用途是本地仿真联调，不是互联网生产服务。
- 模型权重、场景数据、完整测试日志、视频未纳入本仓库，复现真实场景/模型需要自行取得合法访问权限。
- 本仓库没有根目录 LICENSE。官方模型的授权信息不等同于官方代码或本仓库的许可；复用与发布需单独核查。

## 6. 未完成与不再纳入 SURF 交付的事项

- 成功完成目标对齐自主导航任务：协作仓库虽已进行一次 80 步目标对齐 episode，但 NaVIDA 在错误位置 STOP，**没有导航成功**；更没有多场景规模验证。
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

**可对外使用的结项描述：** “Contributed the model-side NaVIDA–Habitat inference service and evaluator-side HTTP adapter/demo, with strict action parsing and auditable atomic-action execution. Historical tests covered a five-step connectivity smoke test and an 80-step instruction-grounded simulation episode in which NaVIDA stopped at the wrong goal location. No standard VLN benchmark or physical-robot deployment was completed.”
