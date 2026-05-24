# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

第二十八届中国机器人及人工智能大赛 — 机器人任务挑战赛：自主巡航（地面巡航场景）。实现一套自主移动机器人系统，完成语音唤醒、任务图像识别、路径规划避障、精准到点、语音播报的完整比赛链路。

详细需求见 `docs/PROJECT_REQUIREMENTS_GROUND_CRUISE.md`。

## 开发环境

### 本机开发（主要）

- **环境**：Windows WSL Ubuntu 18.04，ROS Melodic，catkin 工作空间
- **仿真方式**：先验地图模拟导航，mock 数据模拟图像/语音
- 所有修改优先在本机 `abot_ws/` 完成并验证

### 远端验证（临时）

远端 ABOT 设备为赛场公用设备。代码仅在使用时段临时部署。

- **远端信息**：`abot@172.16.24.173`，见 memory `[[abot-device]]`
- **部署时机**：用户明确指示需要远端验证时，`scp` 推送变更文件到远端编译运行
- **代码保护规则**：用户说出 **"我的远端使用时间结束"** 时，你**必须**执行：
  1. 将远端 `~/abot_ws/src/` 下所有本次修改的文件 `scp` 回本机 `abot_ws/src/`
  2. 将远端 `~/abot_ws/src/` 恢复到原始状态（删除新增文件，还原修改文件）
  3. 删除远端 home 目录下本次新增的脚本
  4. 确认代码不留存后告知用户
- **禁止行为**：未经用户指示，不得主动向远端推送代码；不得在远端保留任何本次开发的代码或配置

## 构建与开发命令

- 编译工作空间：`cd abot_ws && catkin_make`
- 单独编译某包：`catkin_make --pkg <package_name>`
- 运行测试：`catkin_make run_tests`
- 运行单个测试：`catkin_make run_tests --pkg <package_name>`
- Source 环境：`source abot_ws/devel/setup.bash`
- 启动仿真任务（M1 起可用）：
  ```bash
  source abot_ws/devel/setup.bash
  roslaunch mission_manager sim_mission.launch
  ```

## 文档维护规则

- **每次大修改后必须更新 `CHANGELOG.md`**：记录本次变更的 Added / Changed / Fixed / Removed，按 M0~M7 阶段分组
- **功能包职责变更时更新 `README.md` 和 `CLAUDE.md`**：保持目录结构、功能包说明与代码一致
- **CHANGELOG 格式**：遵循 Keep a Changelog，按开发里程碑（M0-M7）组织，每个条目标注日期

## Git 提交规范

严格遵循 **Angular 提交规范**，使用**中文**编写提交信息。

```
<type>(<scope>): <中文简述>

<中文详细描述（可选）>
```

type 类型：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档变更
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具变更
- `perf`: 性能优化

示例：
```
feat(mission): 实现任务状态机核心流转逻辑
fix(navigation): 修复麦克纳姆轮逆解算角度错误
docs(config): 补充比赛场地配置文件说明
```

## 代码架构

### 目录结构（规划）

```
.
├── config/                     # 所有比赛参数配置文件（禁止硬编码）
│   ├── competition_field.yaml  # 场地尺寸、网格、起终点、任务点、障碍物
│   ├── mission.yaml            # 任务超时、重试次数、语音要求
│   ├── robot.yaml              # 机器人尺寸、footprint、传感器参数
│   ├── navigation.yaml         # 导航参数（costmap、速度限制等）
│   ├── perception.yaml         # 任务图像识别参数（VLM prompt）
│   └── voice_text.yaml         # 播报文本模板（12 条，支持 {index}/{target_cell} 变量）
├── src/
│   ├── mission_manager/        # 【新建】任务状态机 + 安全监控（今年核心模块）
│   │   ├── mission_state_machine.py  # 完整状态机：IDLE→WAKEUP→识别×4→导航×4→播报×4→终点→DONE
│   │   └── safety_monitor.py         # 激光碰撞检测/里程计运动监控/heartbeat watchdog/急停
│   ├── common/                 # 【新建】公共工具包
│   │   ├── config_loader.py    # YAML 配置加载、网格坐标→map 坐标转换、footprint 区域判定
│   │   └── mission_logger.py   # JSONL 结构化日志（按 run_YYYYMMDD_HHMMSS 组织）
│   ├── robot_slam/             # 导航定位 + 建图 + ASR + 唤醒词（比赛核心复用的旧包）
│   │   ├── 定位：Cartographer (主) / AMCL (备)
│   │   ├── 导航：move_base + DWA + GlobalPlanner (Dijkstra)
│   │   ├── 建图：Gmapping / Hector SLAM
│   │   ├── 语音：Snowboy 唤醒词检测 (start.py) + FunASR Paraformer 中文识别 (demo.py)
│   │   ├── 多目标导航脚本：navigation_multi_goals_4.py 等（参考）
│   │   ├── launch/: 各类启动文件 (GameStart/navigation/gmapping/multi_goal)
│   │   ├── params/carto/: costmap/DWA/planner 参数（已调优适配 3.6m 场地）
│   │   └── maps/: 先验地图 (my_lab/my_map/shoot)
│   ├── abot_base/              # ABOT 机器人底层驱动（不改动）
│   │   ├── abot_bringup/       # 串口底盘驱动 (/dev/abot, 921600bps)，发布 odom/TF，订阅 cmd_vel
│   │   ├── abot_imu/           # IMU AHRS 驱动，发布九轴 IMU 数据
│   │   ├── abot_model/         # URDF 机器人模型 + Gazebo 仿真
│   │   └── lidar_filters/      # 激光雷达 Box 滤波器（去除机器人自身点云）
│   ├── abot_vlm/               # 豆包大模型视觉识别（Vision Pro）
│   │   └── doubao.py           # 订阅 /usb_cam/image_raw，拍照后调用豆包 API 识别任务图像
│   ├── user_demo/              # 旧版比赛状态机（C++, 2025 射击赛，今年废弃仅作参考）
│   │   └── mission_node.hpp    # C++ 模板类状态机，硬编码路径点+AR 标签射击流程
│   ├── abot_find/              # find_object_2d 特征点物体检测（SURF，Qt GUI）
│   ├── hector_slam/            # Hector SLAM 算法包（无里程计建图，备选）
│   └── imu_filter/             # IMU 姿态滤波器（Madgwick/Mahony）
├── launch/
│   └── ground_cruise.launch    # 比赛统一启动入口（唤醒+导航+VLM+状态机+安全）
├── scripts/
│   ├── mapping.sh              # 模式一：键盘控制建图（8 个节点）
│   ├── navigation_test.sh      # 模式二：预设路径导航（10 个节点）
│   ├── competition.sh          # 模式三：完整比赛（14 个节点）
│   └── *.sh                    # 其他：远端 ABOT 启动脚本（参考）
├── tests/                      # 单元测试与仿真测试（待建）
├── logs/                       # 运行日志（按 run_YYYYMMDD_HHMMSS 组织，gitignore）
└── docs/                       # 需求文档 + 实现计划 + 比赛素材
```

### 三种运行模式与节点架构

#### 模式一：键盘控制建图 (`scripts/mapping.sh`)

**8 个节点**，手动操控机器人扫图，SLAM 实时构建地图。

```
roscore
 ├── abot_driver           # 底盘串口驱动 → /odom, TF
 ├── abot_imu              # IMU 数据 → /imu
 ├── rplidar               # 激光雷达 → /scan
 ├── box_filter            # 过滤自身点云 → /scan_filtered
 ├── robot_state_publisher # URDF → TF (base_link→laser_link)
 ├── slam_gmapping         # 实时 SLAM → /map
 ├── teleop_keyboard       # 键盘遥控 → /cmd_vel
 └── rviz (可选)           # 可视化建图过程
```

启动：`./scripts/mapping.sh [地图名]`

#### 模式二：预设路径导航 (`scripts/navigation_test.sh`)

**10 个节点**，加载先验地图，按预设路径点顺序导航，验证导航精度。

```
roscore
 ├── abot_driver           # 底盘驱动 → /odom
 ├── abot_imu              # IMU → /imu
 ├── rplidar               # 激光雷达 → /scan
 ├── box_filter            # 激光滤波 → /scan_filtered
 ├── robot_state_publisher # TF 发布
 ├── robot_pose_ekf        # 里程计+IMU 融合 → /odom_combined
 ├── map_server            # 加载 .pgm 先验地图 → /map
 ├── amcl                  # 粒子滤波定位 → /amcl_pose
 ├── move_base             # 全局规划 + DWA 局部规划 + costmap
 └── multi_goals.py        # 顺序发送预设路径点 → move_base action
```

启动：`./scripts/navigation_test.sh [地图名] [路径脚本]`

#### 模式三：完整比赛 (`scripts/competition.sh`)

**14 个节点**，运行地面巡航完整比赛链路。

```
roscore
 ├── abot_driver           # 底盘驱动
 ├── abot_imu              # IMU
 ├── rplidar               # 激光雷达
 ├── box_filter            # 激光滤波
 ├── robot_state_publisher # TF 发布
 ├── robot_pose_ekf        # 里程计融合
 ├── map_server            # 先验地图 → /map
 ├── cartographer_node     # Cartographer 定位 (主)
 ├── amcl                  # AMCL 定位 (备)
 ├── move_base             # 导航规划 (GlobalPlanner + DWA)
 ├── game_node             # Snowboy 唤醒词检测 → /start
 ├── vlm_node              # 豆包 VLM 图像识别 → /vision_result
 ├── mission_state_machine # 任务状态机 (核心串联)
 └── safety_monitor        # 安全监控 + 碰撞检测 + watchdog
```

数据流：
```
game_node ──/start──→ mission_state_machine
vlm_node  ──/vision_result──→ mission_state_machine
mission_state_machine ──move_base action──→ 导航
mission_state_machine ──/voiceWords──→ TTS 播报
safety_monitor ──/safety_status──→ mission_state_machine
```

启动：`./scripts/competition.sh [地图名] [sim_mode]

### 核心模块职责与数据流

```
语音唤醒 → Mission Manager（状态机） → 语音播报
                ↓           ↑
           Navigation   Perception
                ↓           ↑
           底盘控制      摄像头/LiDAR
```

1. **Mission Manager**：比赛流程唯一入口，管理状态机（IDLE → WAIT_FOR_WAKEUP → ... → DONE），协调各模块，记录所有状态跳转日志。异常状态包括 ABORT_COLLISION_RISK、ABORT_TIMEOUT、ABORT_LOCALIZATION_LOST 等。
2. **Navigation**：加载 `config/competition_field.yaml` 地图，定位位姿，规划路径，避开随机挡板，精准到点判定（不能只看导航 action 成功，必须判断 footprint 是否完全进入任务点区域）。
3. **Perception**：搜索围栏内侧任务信息图像，识别内容并输出目标任务点编号 + 置信度。低置信度结果不得直接导航，需重识别或确认。
4. **Voice I/O**：播报接口返回"开始/完成/失败"状态；Mission Manager 仅在播报完成后进入下一状态；播报时机器人完全停止。
5. **Safety**：每个关键模块有 heartbeat；状态机有 watchdog；导航卡死触发恢复策略而非无限等待。

### 关键设计原则

- **参数与逻辑分离**：所有比赛参数（场地、任务点、机器人尺寸、超时时间、播报文本）放入 `config/`，业务代码禁止硬编码。
- **任务图像识别模块**：必须支持赛前/现场更换模板或模型；识别结果必须带置信度、时间戳、图像来源。
- **可配置项 > 硬编码**：起点、终点、任务点、障碍物候选位置全部可配置。
- **日志优先**：每次识别、导航、播报结果必须记录，方便赛前复盘和问题调试。
- **最小侵入修改**：不进行大规模重构，优先做最小可验证修改。不引入非必要大型依赖。

### 比赛关键约束

| 约束 | 值 |
|---|---|
| 场地尺寸 | 3.6m × 3.6m，围栏高 30cm |
| 网格 | 9×9，每格 0.4m × 0.4m |
| 任务点 | 9 个（网格 31-33, 40-42, 49-51），尺寸 38cm × 32cm |
| 任务图像 | 4 张，围栏内侧，中心高 20cm |
| 总时长 | 180s |
| 启动后首次运动 | ≤ 20s |
| 最大无状态变化 | ≤ 20s |
| 机器人尺寸 | 350mm × 300mm × 240mm |
| 麦克纳姆轮 | 4 个，直径 97mm |

## 开发里程碑

按优先级：M0 规则建模与仓库整理 → M1 底盘与导航基础 → M2 任务点精准到达 → M3 任务图像识别 → M4 语音交互 → M5 完整任务链路 → M6 鲁棒性测试 → M7 参赛文档
