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

## 目录结构（规划）

```
.
├── config/          # 比赛参数配置（场地、任务、机器人、导航、语音等）
├── src/             # 源代码
│   ├── mission_manager/  # 任务状态机
│   ├── navigation/       # 定位导航
│   ├── perception/       # 任务图像识别
│   ├── voice_io/         # 语音交互
│   ├── safety/           # 安全保护
│   └── common/           # 公共工具
├── launch/          # ROS 2 launch 文件
├── scripts/         # 启动脚本
├── tests/           # 测试
├── logs/            # 运行日志
└── docs/            # 文档与比赛材料
```

## 快速开始

> 项目当前处于初始化阶段，以下命令待代码落地后可用。

### 前置依赖

- Python 3.10+
- ROS 2 Humble（或非 ROS 模式：仅 Python）
- 比赛硬件平台（底盘、LiDAR、摄像头、麦克纳姆轮）

### 启动比赛

ROS 2 模式：
```bash
ros2 launch <project> ground_cruise.launch.py
```

非 ROS 模式：
```bash
python scripts/run_ground_cruise.py --config config/mission.yaml
```

### 修改比赛参数

编辑 `config/` 目录下的 YAML 文件：

| 文件 | 用途 |
|---|---|
| `competition_field.yaml` | 场地尺寸、起终点、任务点、障碍物 |
| `mission.yaml` | 任务超时、重试次数 |
| `robot.yaml` | 机器人尺寸、传感器参数 |
| `navigation.yaml` | 导航参数 |
| `perception.yaml` | 识别参数 |
| `voice_text.yaml` | 播报文本 |

### 运行测试

```bash
pytest tests/
```

## 开发里程碑

| 阶段 | 目标 |
|---|---|
| M0 | 规则建模与仓库整理 |
| M1 | 底盘与导航基础 |
| M2 | 任务点精准到达 |
| M3 | 任务图像识别 |
| M4 | 语音交互 |
| M5 | 完整任务链路 |
| M6 | 鲁棒性测试 |
| M7 | 参赛文档与答辩准备 |

## 提交规范

遵循 [Angular 提交规范](https://www.conventionalcommits.org/)，使用中文编写提交信息：

```
<type>(<scope>): <中文简述>
```

示例：`feat(mission): 实现任务状态机核心流转逻辑`

详见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

待定。
