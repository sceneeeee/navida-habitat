# Stage 2 Habitat 环境状态记录

## 当前状态

Stage 2 已完成：

- 2A：本地环境与版本审计
- 2B：Habitat-Sim 0.2.4 与 Habitat-Lab 0.2.4 安装
- 2C：真实场景、NavMesh、RGB 传感器与原子动作 smoke test

尚未完成：

- 2D：Habitat 环境接入 mock episode loop
- 2E：自动化测试、日志、文档与 PR 验收

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

- Conda environment：`navida_habitat_sim_gui_test`
- Python：`3.9`
- Gym：`0.22.0`
- Hydra Core：`1.2.0`
- OmegaConf：`2.2.3`
- OpenCV：`4.8.1`
- NumPy：`1.26.4`

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

## 下一步

在 `feat/habitat-mock-integration` 分支实现：

1. `HabitatEnvAdapter`
2. RGB observation 与 agent pose 接口
3. NaVIDA 原子动作到 Habitat action 的映射
4. mock backend、strict parser 与 Habitat-Sim episode loop
5. JSONL episode 日志
6. STOP、invalid output、backend exhaustion 和 max steps 测试
7. Stage 2 自动化验收脚本与使用文档
