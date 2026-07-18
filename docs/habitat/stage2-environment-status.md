# Stage 2 Habitat 环境状态记录

## 当前状态

Stage 2 已完成：

- 2A：本地环境与版本审计
- 2B：Habitat-Sim 0.2.4 与 Habitat-Lab 0.2.4 安装
- 2C：真实场景、NavMesh、RGB 传感器与原子动作 smoke test
- 2D：Habitat 环境接入 mock episode loop
- 2E：自动化测试、日志与文档验收（PR 尚未创建）

当前 Stage 2 pipeline 为：

~~~text
MockBackend
→ EpisodeRunner
→ HabitatEnvAdapter
→ Habitat-Sim real scene
→ JSONL
~~~

该 pipeline 是 execution demo，不是 navigation success evaluation。当前没有正式 episode goal，STOP 只设置 `done=true`，不会伪造成功，`success` 始终保持 `false`。

## 固定版本

### Habitat-Sim

- Version：`0.2.4`
- Git tag：`v0.2.4`
- Git commit：`f179b584bcd713c5a2a998132211e2cae881d6d1`
- Source path：`~/SURF/_external/habitat-sim-0.2.4-glx`

### Habitat-Lab

- Version：`0.2.4`
- Git tag：`v0.2.4`
- Git commit：`1639e1ae732ba1e84199a1a04b79c7243c3f8586`
- Source path：`~/SURF/_external/habitat-lab-0.2.4`

### Python 环境

- Conda environment：`navida_habitat`
- Python：`3.10.20`
- Habitat-Lab：以 editable 方式安装
- Habitat-Sim：使用本地 GLX 源码构建的 Python 包

## WSL2 渲染问题

Habitat-Sim 0.2.4 官方 Conda 构建默认使用 EGL。

当前 WSL2 环境中：

- CUDA 由 Windows NVIDIA 驱动桥接提供；
- OpenGL 由 WSLg 和 Mesa D3D12 提供；
- Habitat-Sim 的 EGL CUDA-device matching 无法将两者识别为同一设备。

原始错误：

~~~text
Platform::WindowlessEglApplication::tryCreateContext():
unable to find CUDA device 0 among 1 EGL devices in total
~~~

## GLX workaround

在 Habitat-Sim 源码文件：

~~~text
src/cmake/dependencies.cmake
~~~

将：

~~~cmake
set(MAGNUM_TARGET_EGL ON CACHE BOOL "" FORCE)
~~~

修改为：

~~~cmake
set(MAGNUM_TARGET_EGL OFF CACHE BOOL "" FORCE)
~~~

然后从源码构建 Habitat-Sim，使其使用：

~~~text
WindowlessGLXApplication
~~~

动态链接验证结果：

~~~text
libGLX.so.0
libOpenGL.so.0
libGLdispatch.so.0
~~~

构建结果未链接 `libEGL.so`，也不存在缺失动态库。

## 源码构建命令

在外部 Habitat-Sim 源码目录中执行：

~~~bash
cd ~/SURF/_external/habitat-sim-0.2.4-glx

conda run --no-capture-output \
  -n navida_habitat_sim_gui_test \
  python setup.py build_ext \
  --inplace \
  --parallel 2 \
  --bullet \
  --no-lto
~~~

## 运行时路径

运行本地 GLX Habitat-Sim 时，需要确保源码 Python 包优先：

~~~bash
export PYTHONPATH="$HOME/SURF/_external/habitat-sim-0.2.4-glx/src_python"
export DISPLAY=:0
~~~

运行本仓库脚本时还需将仓库的 `src` 目录加入 `PYTHONPATH`，且 Habitat-Sim 路径保持在前：

~~~bash
export PYTHONPATH="$HOME/SURF/_external/habitat-sim-0.2.4-glx/src_python:$PWD/src"
~~~

Habitat-Lab 使用 editable install，源码路径为：

~~~text
~/SURF/_external/habitat-lab-0.2.4/habitat-lab
~~~

安装命令：

~~~bash
conda run --no-capture-output \
  -n navida_habitat_sim_gui_test \
  python -m pip install \
  --no-deps \
  -e ~/SURF/_external/habitat-lab-0.2.4/habitat-lab
~~~

## 空场景验证

空场景 RGB smoke test 已通过：

~~~text
Renderer: D3D12 (NVIDIA GeForce RTX 4060 Ti)
OpenGL version: 4.2
simulator: OK
rgb shape: (64, 64, 4)
rgb dtype: uint8
~~~

## 测试场景

官方 Habitat 测试场景保存于：

~~~text
~/SURF/datasets/habitat/scene_datasets/habitat-test-scenes
~~~

已下载的测试场景包括：

~~~text
apartment_1.glb
apartment_1.navmesh
skokloster-castle.glb
skokloster-castle.navmesh
van-gogh-room.glb
van-gogh-room.navmesh
~~~

测试数据总大小约为：

~~~text
106M
~~~

这些测试数据仅保存在本地，不提交到 Git 仓库。

## 真实场景验证

测试场景：

~~~text
apartment_1.glb
apartment_1.navmesh
~~~

验证结果：

~~~text
navmesh loaded: True
forward displacement m: 0.25129958987236023
left turn degrees: 15.000001425579999
right turn degrees: 15.000001170802827
rgb shape: (128, 128, 4)
rgb dtype: uint8
rgb MAD after forward: 13.732808430989584
rgb MAD after left: 20.093892415364582
rgb MAD after right: 20.093994140625
REAL_SCENE_SMOKE_OK
~~~

以上结果证明：

- GLB 真实场景可以加载；
- NavMesh 可以加载；
- RGB 传感器工作正常；
- 前进 25 cm 的动作语义正确；
- 左右旋转 15° 的动作语义正确；
- agent 位姿变化后 RGB 观测发生变化；
- WSL2 下的 GLX 渲染方案能够正常运行 Habitat-Sim 0.2.4。

## 本地目录结构

当前相关目录：

~~~text
~/SURF/navida-habitat
~/SURF/_external/habitat-sim-0.2.4-glx
~/SURF/_external/habitat-lab-0.2.4
~/SURF/datasets/habitat
~~~

其中只有 `navida-habitat` 是当前项目仓库。

## 不提交到本仓库的内容

以下内容属于本地运行依赖，不提交到 `navida-habitat`：

- Habitat-Sim 上游源码及编译产物
- Habitat-Lab 上游源码
- Conda 环境
- Habitat 测试场景
- HM3D、R2R 或其他正式数据集
- 模型权重
- 临时 smoke test 脚本

这些内容保存在 `~/SURF/_external`、`~/SURF/datasets` 或 `/tmp`。

## Stage 2D/2E 实现结果

- `EpisodeRunner` 依赖最小 backend/environment Protocol，不再依赖具体 `MockEnv` 类型。
- `HabitatEnvAdapter` 对 Habitat 依赖使用 lazy import，只配置 RGB 传感器。
- `move_forward` 为 0.25 m，`turn_left` 和 `turn_right` 均为 15°。
- STOP 由 adapter 处理，不调用 Habitat-Sim 中不存在的默认 STOP action。
- adapter 暴露真实 `position`、`rotation_yaw` 和当前 uint8 RGBA observation。
- adapter 提供幂等 `close()` 和 context manager，运行脚本在异常路径也会关闭 simulator。
- JSONL 保留 Stage 1 字段，同时提供 `parsed_action`、`rotation_yaw` 和 `termination` 字段名。
- 普通测试使用纯 Python fake simulator，不要求 Habitat、DISPLAY 或真实场景。
- `tests/test_habitat_integration.py` 默认跳过；只有显式设置 `NAVIDA_HABITAT_RUN_INTEGRATION=1` 和 `NAVIDA_HABITAT_SCENE` 才运行真实场景。

真实运行入口：

~~~bash
python scripts/run_habitat_mock_episode.py \
  --scene /path/to/scene.glb \
  --output logs/habitat/stage2_demo.jsonl \
  --episode-id stage2-demo-001 \
  --instruction "Walk forward and turn left." \
  --max-steps 10
~~~

当前 backend 仍为 `MockBackend`，尚未加载 NaVIDA 模型。下一阶段是在保持相同 runner/environment seam 和科学协议约束的前提下接入官方 checkpoint。
