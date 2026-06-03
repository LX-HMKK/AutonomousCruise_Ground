# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

第二十八届中国机器人及人工智能大赛 — 机器人任务挑战赛：自主巡航（地面巡航场景）。实现一套自主移动机器人系统，完成语音唤醒、任务图像识别、路径规划避障、精准到点、语音播报的完整比赛链路。

详细需求见 `docs/PROJECT_REQUIREMENTS_GROUND_CRUISE.md`。

## 开发环境

### 本机开发（主要）

- **环境**：Windows WSL Ubuntu 18.04，ROS Melodic，catkin 工作空间
- **WSL 用户**：`lx_hm`，sudo 密码：`123456`
- **仿真方式**：先验地图模拟导航，mock 数据模拟图像/语音
- 所有修改优先在本机 `abot_ws/` 完成并验证
- **代码源路径**：仓库位于 Windows 文件系统 (`D:\StudyWorks\...`)，运行时需同步到 WSL 的 `~/abot_ws/src/`（Python 脚本可直接 cp，C++ 需 `catkin_make`）

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
- 启动完整仿真（推荐，10 个节点）：
  ```bash
  source /opt/ros/melodic/setup.bash && source ~/abot_ws/devel/setup.bash && roslaunch mission_manager sim_full_mission.launch
  ```
- 仅启动导航仿真测试（4 个节点，无 VLM/状态机）：
  ```bash
  roslaunch mission_manager sim_navigation.launch map_name:=game
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
│   ├── mission_manager/        # 【核心】任务状态机 + 安全监控 + 仿真 mock
│   │   ├── launch/
│   │   │   ├── sim_full_mission.launch  # 完整仿真（导航+Mock VLM+Mock TTS+状态机+安全+RViz）推荐
│   │   │   ├── sim_navigation.launch    # 仅导航仿真（无 VLM/状态机）
│   │   │   └── sim_mission.launch       # 仅状态机+安全（需外启导航栈）
│   │   └── scripts/
│   │       ├── mission_state_machine.py # 完整状态机：IDLE→WAKEUP→识别×4→导航×4→播报×4→终点→DONE
│   │       ├── safety_monitor.py        # 碰撞检测/运动监控/heartbeat watchdog/急停
│   │       ├── mock_vlm.py              # Mock VLM：按预设序列发布 /vision_result
│   │       ├── mock_tts.py              # Mock TTS：订阅 /voiceWords，发布 /tts_done（M4 新增）
│   │       └── sim_robot.py             # 仿真机器人：odom + scan + TF + 订阅 cmd_vel
│   ├── common/                 # 公共工具包
│   │   ├── config_loader.py    # YAML 配置加载、网格/坐标转换、footprint 区域判定
│   │   └── mission_logger.py   # JSONL 结构化日志
│   ├── robot_slam/             # 导航定位 + 建图 + 语音
│   │   ├── launch/             # Gmapping / Cartographer / move_base / GameStart
│   │   ├── params/carto/       # costmap/DWA/planner 参数（已调优）
│   │   ├── maps/               # 先验地图 (game/my_lab/my_map/shoot)
│   │   └── scripts/            # start.py(唤醒) / demo.py(ASR) / navigation_multi_goals_4.py(参考)
│   ├── abot_base/              # ABOT 底层驱动（不改动）
│   │   ├── abot_bringup/       # 串口底盘驱动
│   │   ├── abot_imu/           # IMU AHRS
│   │   ├── abot_model/         # URDF 模型
│   │   └── lidar_filters/      # 激光 BoxFilter
│   └── abot_vlm/               # 豆包 VLM 视觉识别（实车用）
├── launch/
│   └── ground_cruise.launch    # 比赛统一启动入口
├── scripts/
│   ├── mapping.sh              # 模式一：键盘控制建图
│   ├── navigation_test.sh      # 模式二：预设路径导航
│   ├── competition.sh          # 模式三：完整比赛
│   └── sim_full_test.sh        # WSL 仿真完整测试
├── tools/
│   └── mark_map_gui.py         # PGM 地图可视化标点（Windows 端运行，支持缩放平移）
├── config/                     # 比赛参数 YAML（6 个）
├── docs/                       # 需求文档 + 实现计划
└── logs/                       # 运行日志（gitignore）
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

启动：``./scripts/competition.sh [地图名] [sim_mode]``

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

### 开发陷阱与已知问题

以下问题是 M3 仿真调试中踩过的坑，修改代码时必须注意：

| 陷阱 | 表现 | 解决方案 |
|---|---|---|
| `rosnode list` | XML-RPC 无超时，卡死 134s | 用 `grep "process\[" log_file` 替代，从日志文件读取节点进程 |
| Python 2 中文编码 | YAML 配置含中文时崩溃 | 每个 `.py` 文件头部加 `reload(sys); sys.setdefaultencoding('utf-8')` |
| ROS 端口冲突 | 11311 端口 TIME_WAIT 60s | 启动前 `export ROS_MASTER_URI=http://localhost:0` 使用随机端口 |
| map→odom TF 缺失 | 导航栈无路径规划 | `sim_robot.py` 必须发布 `map→odom` identity transform |
| 仿真唤醒 | 状态机等待 /start 不启动 | `sim_mode=true` 下状态机 5s 后自动唤醒，无需手动发 `/start` |
| 起点在地图外 | AMCL 粒子群发散 | `game` 实赛地图，检查 init_x/init_y 是否在 map 范围内 |
| 安全监控不检测角运动 | 机器人原地旋转不触发监控 | `_on_odom` 回调中增加 yaw 变化判断 |
| heartbeat 时机 | rospy.spin 阻塞不执行心跳 | 用 `rospy.Timer(2s)` 独立线程发送 heartbeat |

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

| 阶段 | 目标 | 状态 |
|---|---|---|
| M0 | 规则建模与仓库整理 | ✅ |
| M1 | 配置系统 + 状态机骨架 + 安全监控 | ✅ |
| M2 | 导航参数调优 + 精准到点判定 | ✅ |
| M3 | 任务图像识别 + 仿真环境 | ✅ |
| M4 | 语音播报完成回调 | ✅ |
| M5 | 全链路联调（game 地图） | ✅ |
| M6 | 鲁棒性增强（导航卡死检测） | ✅ |
| M7 | 参赛文档与答辩准备 | ✅ |
