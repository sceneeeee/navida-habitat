# NaVIDA–Habitat：SURF 视觉语言导航仿真工程

[English README](README.md) · [SURF 结项报告](docs/surf-closeout.zh-CN.md) · [仿真端说明](habitat_vln/README.md) · [个人贡献审计](docs/contribution-audit.md) · [迁移来源](docs/evaluator-provenance.md)

**项目状态：** SURF 已结束，历史上已经完成 NaVIDA 模型与 Habitat 的双进程联调；个人仓库现已迁入 SURF 主仓库的仿真应用层，**但迁移后的双端工程尚未重新在真实 checkpoint 和 Habitat 场景下运行验收**。

## 项目目的与成果

将 NaVIDA 视觉语言导航模型与 Habitat 仿真器连接，通过 RGB 历史帧和自然语言导航指令生成原子动作，并保留模型输出、解析信息、时序、轨迹与媒体产物。这是一项模型推理系统与仿真评估的**工程集成**，而不是模型原创、完整论文指标复现或实机导航成果。

项目架构刻意划分为两个运行环境：

| 模块 | 代码 | 环境 |
| --- | --- | --- |
| 模型端 | src/navida_habitat/、scripts/ | Python 3.10；NaVIDA checkpoint；CUDA；4-bit |
| 仿真端 | habitat_vln/、test/ | Python 3.9；历史 Habitat-Lab/Habitat-Sim 环境 |
| 交互方式 | localhost HTTP；RGB PNG/base64；episode/step ID | 每一步返回一项原子动作 |

模型端默认只允许当前 RGB、历史 RGB、文字指令，不向模型提供目标距离、方位、pose、深度或地图。严格解析输出，不使用随机动作补救或隐藏的目标距离提前停止。

## 实际历史验证

- **模型端自动化测试：** 88 项，87 通过，1 项可选场景测试跳过，记录于 [个人仓库 PR #6](https://github.com/sceneeeee/navida-habitat/pull/6)。
- **真实模型：** RTX 4060 Ti 8GB 上采用 4-bit 推理；原记录 GPU peak allocated 约 3.12 GiB。
- **五步工程联调：** 模型服务、HTTP、动作队列与 Habitat 动作执行正常；指令与随机 PointNav 目标未对齐，不代表导航成功。
- **真实模型目标对齐 Demo：** 由你的账号提交至 [SURF 主仓库 PR #5](https://github.com/RtimesC/habitat-lab/pull/5)。在固定测试场景执行 80 步，NaVIDA 在错误位置 STOP，success=0、SPL=0、最终距离约 8.620 m。对照 Oracle 成功，但**不是 NaVIDA 的成功率**。
- **缺少的工作：** 标准 R2R/RxR benchmark、多场景统计性能、Jetson/ROS 2/FrogBot 实机验证。

以上均是历史证据，本次迁移没有重跑测试，也没有增加新的成功率。

## 为什么重新整合

SURF 的评估侧主仓库是 [RtimesC/habitat-lab](https://github.com/RtimesC/habitat-lab)。其中你的账号提交过 HTTP 客户端（PR #4）和目标对齐 Demo（PR #5），但原仓库还包含 Meta 的 Habitat-Lab 源码及其他成员的通用框架。为了能够独立维护和展示，个人仓库仅提取了 **2026-07-23 历史快照**中与 NaVIDA 评估闭环直接相关的应用代码和测试。

35 个历史源码/测试文件按 Git blob SHA 与原仓库逐一核实一致。通用 runner、controller、environment wrapper 等部分仍明确标注为源自 SURF 团队工程，而不全部归个人原创；MIT 许可文本保存在 [third_party/habitat-lab-MIT.LICENSE](third_party/habitat-lab-MIT.LICENSE)。

你的个人模型端由本人和 Codex 辅助开发，没有其他人工协作者（以你的说明为准）。NaVIDA 原模型和 Meta Habitat-Lab 仍属于各自上游作者。

## 如何运行与验收

先阅读 [英文 README 的双终端 Quickstart](README.md#quickstart--two-processes-two-environments)，以及 [仿真应用说明](habitat_vln/README.md)。

迁入后的模型端测试：

~~~bash
PYTHONPATH=src python -m unittest discover -s tests -v
~~~

无需真实场景的 HTTP 契约测试：

~~~bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_evaluator_http_contract.py' -v
~~~

评估端历史测试（需对应 Python 3.9、Habitat 和相关依赖）：

~~~bash
python -m unittest discover -s test -p 'test_grounded_demo_episode.py' -v
python -m unittest discover -s test -p 'test_official_navida_http.py' -v
python -m unittest discover -s test -p 'test_grounded_navida_demo.py' -v
~~~

当前不能声称这些测试已在迁移后的仓库通过。待完成 [验收清单](docs/evaluator-migration-acceptance.md) 中的真实执行及记录，才能把迁移状态改为 Verified。

**仓库禁止提交** checkpoint、Habitat 场景、数据集、视频与其他大型实验产物。Codex 每次运行后要把完整进度、测试结果和注意事项追加到根目录 temp_report.md，并确保该文件不进入 Git。
