# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

第二十八届中国机器人及人工智能大赛 — 机器人任务挑战赛：自主巡航（地面巡航场景）。实现一套自主移动机器人系统，完成语音唤醒、任务图像识别、路径规划避障、精准到点、语音播报的完整比赛链路。

详细需求见 `docs/PROJECT_REQUIREMENTS_GROUND_CRUISE.md`。

## 构建与开发命令

> 项目当前处于初始化阶段，以下命令待代码框架搭建后补充。

- 启动比赛流程（预期）：
  - ROS 2: `ros2 launch <project> ground_cruise.launch.py`
  - 非 ROS: `python scripts/run_ground_cruise.py --config config/mission.yaml`
- 运行测试（预期）：`pytest tests/` 或 `colcon test`
- 运行单个测试（预期）：`pytest tests/<test_file>.py::<test_name>`

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
│   ├── perception.yaml         # 任务图像识别参数
│   └── voice_text.yaml         # 播报文本模板
├── src/
│   ├── mission_manager/        # 任务状态机（核心模块，统一管理比赛流程）
│   ├── navigation/             # 定位导航（建图、定位、路径规划、避障、到点判定）
│   ├── perception/             # 任务图像识别（检测、识别、置信度、重试）
│   ├── voice_io/               # 语音交互（唤醒、播报，播报时机器人必须静止）
│   ├── safety/                 # 安全保护（watchdog、heartbeat、碰撞检测、超时监控）
│   └── common/                 # 公共工具（日志、配置加载、数据类型定义）
├── launch/                     # ROS 2 launch 文件（如适用）
├── scripts/                    # 启动脚本与工具
├── tests/                      # 单元测试与仿真测试
├── logs/                       # 运行日志（按 run_YYYYMMDD_HHMMSS 组织）
└── docs/                       # 文档与比赛材料
```

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
