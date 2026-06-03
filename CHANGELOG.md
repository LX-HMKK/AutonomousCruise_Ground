# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 格式，使用 [Angular 提交规范](https://www.conventionalcommits.org/) 进行版本记录。

## [Unreleased]

### M6 — 鲁棒性增强 (2026-06-03)

#### Added
- 导航卡死检测：`_handle_arrive_task` 改用轮询循环，每 2s 检查 robot 位移，超过 `nav_stuck_timeout_s`(10s) 无进展则取消导航并重试
- `mission.yaml` 新增 `nav_stuck_timeout_s` 参数

#### Changed
- 导航等待从阻塞 `wait_for_result()` 改为轮询循环，支持实时进度监控

### M5 — 全链路就绪 (2026-06-03)

- Game 地图（1056×992px, x∈[-15.4,11.0], y∈[-13.8,11.0]）已接入仿真
- 3.6m 比赛场地位于 map origin，task cells 均在地图可通行范围内
- 需用户在 WSL 中运行 `roslaunch mission_manager sim_full_mission.launch` 验证

### M4 — 语音播报完成回调 (2026-06-03)

#### Added
- `mock_tts.py`：Mock TTS 仿真节点，订阅 `/voiceWords`，按字数估算时长，完成后发布 `/tts_done`
- `_speak()` 改为 `tts_done_event.wait()` 阻塞等待播报完成，替代固定 `rospy.sleep`
- 播报期间机器人保持停止，超时 10s(sim)/20s(real)

#### Changed
- `sim_full_mission.launch` 节点数 9→10，新增 mock_tts

### 仓库裁剪 (2026-06-03)

#### Removed
- 功能包：user_demo, abot_find, hector_slam, imu_filter（与本次比赛无关）
- 脚本：8 个远端 ABOT 旧 sh + 18 个旧 Python（AR标签/射击/demo/旧导航）

### M3 仿真调试 — 关键修复 (2026-06-03)

#### Fixed
- rosnode list XML-RPC 调用无超时卡 134s — 改为从 log 文件读取节点进程
- 端口 11311 TIME_WAIT 60s — 改随机端口 + tcp_tw_reuse
- launch-prefix 语法不兼容 — 状态机内置 sim_mode 5s 自动唤醒
- Python 2 ASCII 编码崩溃 — 所有脚本加 `sys.setdefaultencoding('utf-8')`
- sim_robot 起点 (-1.5,1.5) 在地图外 — 改为 (0,0) + 创建 competition_field 地图
- map→odom TF 缺失 — sim_robot 发布 identity transform
- 安全监控不检测角运动 — _on_odom 增加 yaw 变化判断
- 安全监控 heartbeat 时机 — 改为 rospy.Timer(2s) 独立线程
- 导航结果订阅类型错误 — String 改为 SimpleActionClient.wait_for_result
- 感知重试计数器无限重置 — 移到任务切换时重置
- mission_logger 并发崩溃 — os.makedirs 加 try/except
- /abot/pose 仿真无发布者 — 增加 /odom 备选位姿源

#### Changed
- 仿真启动从复杂脚本简化为单条 roslaunch 命令
- 默认地图从 my_lab 改为 competition_field（3.6m×3.6m 场地）

### M3 — 任务图像识别完善 (2026-06-03)

#### Added

- `sim_robot.py` 仿真机器人节点：发布 mock odometry、laser scan、TF，订阅 cmd_vel 模拟运动，支持全链路仿真测试
- `sim_navigation.launch` 仿真导航启动文件：map_server + sim_robot + AMCL + move_base，用于 WSL 无硬件的完整导航验证
- `_search_rotation()` 旋转搜索：找不到图像时原地旋转 90 度扫描围栏四个方向，每个方向触发相机并等待识别结果
- `mock_vlm.py` Mock VLM 仿真节点：模拟豆包大模型返回预设任务序列，支持 WSL 无摄像头的完整链路测试
- `seen_image_ids` 去重逻辑：防止同一张任务图像被识别 4 次，已识别过的 image_id 自动跳过

#### Changed

- `_handle_recognize_task_image` 增加旋转重试：每方向等待 10s，4 个方向全部失败才触发 `_retry_perception`
- `_retry_perception` 改为接收 `phase` 参数，重置旋转计数后回到 SEARCH 状态从头开始
- `_on_vision_result` 增加 image_id 去重检查 + 低置信度旋转重试（而非直接重试）

#### Fixed

- 修复 3 个 map YAML 文件（my_lab.yaml, shoot.yaml, my_map.yaml）中硬编码的绝对路径（指向 `/home/abot/` 和 `/home/bcsh/`），改为相对路径，使 map_server 可正常加载地图

### M2 — 精准到点判定 (2026-05-24)

#### Added

- `check_footprint_in_region()` 精准到点判定函数（射线法判断 footprint 四顶点是否全在任务区域内）
- `_on_pose` 回调订阅 `/abot/pose` 获取机器人实时位姿
- `_get_current_pose()` 位姿读取方法
- 三种运行模式启动脚本：`mapping.sh`（8 节点）、`navigation_test.sh`（10 节点）、`competition.sh`（14 节点）
- `my_lab` 先验地图（从远端 ABOT 备份拷贝，用于仿真）
- README.md 重写：实际开发环境、9 个功能包详细职责、构建命令、开发进度

#### Changed

- `_handle_arrive_task` 增加 footprint 区域验证：导航成功后等待位姿稳定 → 检查 footprint → 不通过则发送修正目标
- CLAUDE.md 补充节点架构文档（三种模式树状图 + 数据流 + 14 个节点清单）

### M1 — 配置系统与状态机骨架 (2026-05-24)

#### Added

- `config/` 6 个 YAML 参数配置文件（competition_field / mission / robot / navigation / perception / voice_text）
- `src/common/` 公共工具包：`config_loader.py`（配置加载 + 网格坐标转换）、`mission_logger.py`（JSONL 结构化日志）
- `src/mission_manager/` 任务管理包：`mission_state_machine.py`（438 行完整状态机，6 个正常状态 + 6 个异常状态）、`safety_monitor.py`（激光碰撞检测 + 里程计运动监控 + heartbeat watchdog + 急停）
- `launch/ground_cruise.launch` 比赛统一启动入口
- Snowboy 唤醒词模型 `startGame.pmdl`
- FunASR Paraformer 中文语音识别模型（本地保留，gitignore）

#### Changed

- `abot_vlm/doubao.py` VLM prompt 改为比赛任务图像识别规格（从 ROS param `/perception/prompt_template` 读取）
- `robot_slam/params/carto/` 导航参数调优适配 3.6m 小场地（xy_goal_tolerance 0.03m, footprint 175×150mm, inflation_radius 0.22m）
- MissionState 从 Python 3 `Enum` 改为 Python 2 兼容的自定义类

#### Fixed

- `mission_logger.py` 移除 `os.makedirs(exist_ok=True)` Python 3 专有参数

### M0 — 仓库初始化 (2026-05-23)

#### Added

- `docs/PROJECT_REQUIREMENTS_GROUND_CRUISE.md` 比赛完整需求说明（来源：第二十八届中国机器人及人工智能大赛比赛规则）
- `README.md` 项目说明
- `CLAUDE.md` Claude Code 协作指引
- 远端 ABOT 设备 `abot_ws/` 源码同步（17 个功能包，保留 7 个有用包）
- 比赛场地图与机器人参数表素材
- `.gitignore` 配置（build/devel/logs/__pycache__/大模型文件/API_KEY）
