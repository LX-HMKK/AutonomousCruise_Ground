# 自主巡航 — 地面巡航场景

第二十八届中国机器人及人工智能大赛 · 机器人任务挑战赛：自主巡航（场景一：地面巡航场景）。

## 项目目标

实现一套自主移动机器人系统，完成完整比赛链路：

```text
语音唤醒 → 启动比赛 → 自主巡航搜索任务图像 → 视觉识别任务信息
→ 解析目标任务点 → 导航到点 → 静止语音播报 → 下一任务
→ 全部任务完成 → 导航到终点 → 静止语音播报结束
```

## 场地与规则摘要

| 项目 | 说明 |
|---|---|
| 场地 | 3.6 m × 3.6 m，9×9 网格，围栏高 30 cm |
| 任务点 | 9 个（网格 31-33, 40-42, 49-51），尺寸 38 cm × 32 cm |
| 任务图像 | 4 张，围栏内侧，中心高 20 cm |
| 起点 | 网格 1 或 81 |
| 终点 | 网格 9 |
| 总时长 | 180 秒 |
| 机器人 | 350 mm × 300 mm × 240 mm，四麦克纳姆轮，全向运动 |

完整规则与需求说明见 [`docs/PROJECT_REQUIREMENTS_GROUND_CRUISE.md`](docs/PROJECT_REQUIREMENTS_GROUND_CRUISE.md)。

## 开发环境

| 项目 | 说明 |
|---|---|
| OS | Windows WSL Ubuntu 18.04 |
| ROS | Melodic (Python 2.7) |
| 工作空间 | `~/abot_ws/` (catkin) |
| 仿真 | 先验地图 + mock 数据 |
| 远端设备 | ABOT 机器人 `172.16.24.173` (赛场公用) |

## 目录结构

```
.
├── config/                              # 比赛参数配置（禁止硬编码）
│   ├── competition_field.yaml           # 场地尺寸、网格、起终点、任务点、障碍物
│   ├── mission.yaml                     # 任务超时、重试次数、置信度阈值
│   ├── robot.yaml                       # 机器人 footprint、传感器参数
│   ├── navigation.yaml                  # costmap、DWA、规划器参数
│   ├── perception.yaml                  # VLM prompt 模板、相机设置
│   └── voice_text.yaml                  # 播报文本模板（12 条）
├── src/                                 # ROS 功能包
│   ├── mission_manager/                 # 【新建】任务状态机 + 安全监控（今年核心）
│   ├── common/                          # 【新建】配置加载、日志、网格坐标转换
│   ├── robot_slam/                      # 导航定位/建图/ASR/唤醒词（核心复用）
│   ├── abot_base/                       # ABOT 底盘驱动/IMU/URDF 模型/激光滤波
│   ├── abot_vlm/                        # 豆包大模型视觉识别（任务图像）
│   ├── user_demo/                       # 旧版状态机（C++，2025 射击赛，仅参考）
│   ├── abot_find/                       # find_object_2d 特征点检测（SURF）
│   ├── hector_slam/                     # Hector SLAM（无里程计建图，备选）
│   └── imu_filter/                      # IMU 姿态滤波（Madgwick/Mahony）
├── launch/
│   └── ground_cruise.launch             # 比赛统一启动入口
├── scripts/                             # 远端 ABOT 启动脚本（参考）
├── docs/                                # 需求文档 + 实现计划
└── logs/                                # 运行日志（gitignore）
```

### 功能包详细说明

#### mission_manager（新建，Python）
比赛任务状态机，今年核心模块。

| 文件 | 职责 |
|---|---|
| `scripts/mission_state_machine.py` | 完整状态机：IDLE → WAIT_FOR_WAKEUP → START_ANNOUNCE → SEARCH/RECOGNIZE/NAVIGATE/ARRIVE/ANNOUNCE × 4 → NAVIGATE_TO_FINISH → FINISH_ANNOUNCE → DONE。6 个异常状态。旋转搜索（4方向×90°扫描围栏）、footprint 区域判定、图像去重、感知重试。by move_base actionlib 导航，订阅 `/vision_result` 识别，发布 `/voiceWords` 播报。 |
| `scripts/mock_vlm.py` | Mock VLM 仿真节点：监控 `im_flag` 参数上升沿，按预设序列发布 JSON 识别结果到 `/vision_result`，支持 WSL 无摄像头测试。 |
| `scripts/safety_monitor.py` | 安全监控：激光碰撞检测 + 里程计运动监控 + heartbeat watchdog + 急停。 |
| `scripts/safety_monitor.py` | 安全监控节点：激光雷达碰撞检测（< 0.10m 急停）、里程计运动监控、heartbeat watchdog（5s 超时）、急停发布 `/safety_status`。 |

#### common（新建，Python）
公共工具包，提供配置加载、日志、坐标变换。

| 文件 | 职责 |
|---|---|
| `scripts/config_loader.py` | YAML 配置加载（多路径搜索）、网格编号 → map 坐标转换 `get_cell_center_xy()`、footprint 区域判定 `check_footprint_in_region()`（射线法） |
| `scripts/mission_logger.py` | 线程安全 JSONL 日志，按 `run_YYYYMMDD_HHMMSS/` 组织，5 个日志流：状态跳转/感知结果/导航目标/语音事件/系统事件 |

#### robot_slam（复用，C++ + Python）
导航定位和语音交互的核心包，来自 2025 比赛代码。

| 模块 | 关键文件 | 职责 |
|---|---|---|
| 定位 | Cartographer (`zoo_2Dlidar_localication.launch`) AMCL (`include/amcl.launch.xml`) | 2D 激光雷达实时定位 |
| 导航 | `include/move_base.launch.xml` + `params/carto/*.yaml` | move_base + DWA 局部规划 + GlobalPlanner 全局规划，已调优适配 3.6m 场地 |
| 唤醒词 | `scripts/start.py` + `resources/models/startGame.pmdl` | Snowboy 热词检测，触发后发布 `/start` |
| 语音识别 | `scripts/demo.py` + `scripts/paraformer-zh/` | FunASR Paraformer 中文识别（10s 录音），发布 `/chinese_topic` |
| 建图 | `launch/gmapping.launch` `launch/hector_mapping.launch` | Gmapping / Hector SLAM 建图 |
| 地图 | `maps/my_lab.yaml, my_map.yaml, shoot.yaml` | 先验地图（仿真用） |

#### abot_base（复用，C++）
ABOT 机器人底层硬件驱动，**不改动**。

| 子包 | 职责 |
|---|---|
| `abot_bringup/` | 串口底盘驱动 (`/dev/abot`, 921600bps)，里程计发布 `/odom`，TF 变换，订阅 `/cmd_vel` |
| `abot_imu/` | IMU AHRS 驱动，发布九轴 IMU 数据 |
| `abot_model/` | URDF 机器人模型描述 + Gazebo 仿真 |
| `lidar_filters/` | 激光雷达 BoxFilter，去除机器人自身点云（`/scan` → `/scan_filtered`） |

#### abot_vlm（复用，Python）
大模型视觉识别，订阅 `/usb_cam/image_raw`，触发后拍照发送豆包 Vision Pro API (`doubao-1-5-vision-pro-32k-250115`)，发布 JSON 识别结果到 `/vision_result`。Prompt 已改为比赛任务图像识别规格。

#### 其他包

| 包 | 职责 | 状态 |
|---|---|---|
| `user_demo` | 2025 射击赛 C++ 状态机（硬编码路径点 + AR 标签射击），今年废弃 | 仅参考 |
| `abot_find` | find_object_2d，SURF 特征点物体检测（Qt GUI），可用于备选识别方案 | 可选 |
| `hector_slam` | Hector SLAM，不依赖里程计的激光 SLAM | 备选建图 |
| `imu_filter` | Madgwick/Mahony 姿态滤波器 | IMU 后处理 |

## 构建与运行

### 前置依赖

- WSL Ubuntu 18.04 + ROS Melodic
- Python 2.7 + 依赖包（rospy, yaml, tf, cv2 等）

### 编译

```bash
source /opt/ros/melodic/setup.bash
cd ~/abot_ws
catkin_make
source devel/setup.bash
```

### 启动仿真任务（WSL 一键启动）

```bash
source /opt/ros/melodic/setup.bash && source ~/abot_ws/devel/setup.bash && roslaunch mission_manager sim_full_mission.launch
```

自动启动全部 9 个节点（map_server + robot_state_publisher + sim_robot + move_base + mock_vlm + 状态机 + 安全监控 + RViz），5 秒后自动唤醒开始比赛流程。

### 启动完整比赛（实车）

```bash
roslaunch launch/ground_cruise.launch sim_mode:=false map_name:=competition_field
```

### 修改比赛参数

编辑 `config/` 目录下的 YAML 文件，无需重新编译：

| 文件 | 修改内容 |
|---|---|
| `competition_field.yaml` | 场地尺寸、起终点、任务点坐标、障碍物布局 |
| `mission.yaml` | 总时长、超时时间、重试次数、置信度阈值 |
| `robot.yaml` | 机器人尺寸、footprint、传感器话题 |
| `navigation.yaml` | 速度限制、到点容差、costmap 参数 |
| `perception.yaml` | VLM 模型、prompt 模板、相机分辨率 |
| `voice_text.yaml` | 各阶段播报文本（支持 `{index}` / `{target_cell}` 变量） |

## 开发进度

| 阶段 | 目标 | 状态 |
|---|---|---|
| M0 | 规则建模与仓库整理 | ✅ 完成 |
| M1 | 配置系统 + 状态机骨架 + 安全监控 | ✅ 完成 |
| M2 | 导航参数调优 + 精准到点判定 | ✅ 完成 |
| M3 | 任务图像识别完善（旋转搜索、mock VLM、仿真验证） | ✅ 完成 |
| M4 | 语音播报完善（播报完成回调、蓝牙耳机） | ⬜ 待开发 |
| M5 | 完整任务链路联调 | ⬜ 待开发 |
| M6 | 鲁棒性测试（随机挡板、异常恢复） | ⬜ 待开发 |
| M7 | 参赛文档与答辩准备 | ⬜ 待开发 |

## 提交规范

遵循 [Angular 提交规范](https://www.conventionalcommits.org/)，使用中文编写提交信息：

```
<type>(<scope>): <中文简述>
```

示例：`feat(mission): 实现任务状态机核心流转逻辑`

详见 [CHANGELOG.md](CHANGELOG.md) 和 [CLAUDE.md](CLAUDE.md)。
