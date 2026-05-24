#!/bin/bash
# ============================================
# 模式三：完整比赛模式
# 用途：启动全部节点，运行地面巡航完整比赛流程
#
# 节点列表 (14个):
#   roscore + abot_driver + abot_imu + rplidar
#   + box_filter + robot_state_publisher + robot_pose_ekf
#   + map_server + cartographer_node + amcl(备)
#   + move_base + game_node(Snowboy唤醒)
#   + vlm_node(豆包VLM) + mission_state_machine + safety_monitor
#
# 数据流:
#   game_node --/start--> mission_state_machine
#   vlm_node  --/vision_result--> mission_state_machine
#   mission_state_machine --/voiceWords--> TTS
#   mission_state_machine --move_base action--> 导航
#   safety_monitor --/safety_status--> mission_state_machine
# ============================================

WS_PATH="${HOME}/abot_ws"
MAP_NAME="${1:-my_lab}"
SIM_MODE="${2:-true}"

echo "========================================"
echo "  ABOT 地面巡航 — 完整比赛模式"
echo "========================================"
echo "地图:     ${MAP_NAME}"
echo "仿真:     ${SIM_MODE}"
echo "节点数:   14"
echo "总时长:   180s (max)"
echo "========================================"

export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

if grep -qi microsoft /proc/version 2>/dev/null; then
    # ===== WSL 仿真模式 =====
    echo "[WSL] 仿真后台启动..."

    roscore &
    sleep 2

    source /opt/ros/melodic/setup.bash
    source ${WS_PATH}/devel/setup.bash

    # 1. 底盘 + 传感器层 (5 个节点)
    echo "[1/5] 启动底盘驱动..."
    roslaunch abot_bringup robot_with_imu.launch &
    sleep 5

    # 2. 导航层 (4 个节点: map_server + cartographer + move_base)
    echo "[2/5] 启动导航栈..."
    roslaunch robot_slam nav_cartographer.launch map_name:=${MAP_NAME} &
    sleep 8

    # 3. 唤醒词检测 (1 个节点)
    echo "[3/5] 启动唤醒词检测..."
    roslaunch robot_slam GameStart.launch &
    sleep 2

    # 4. VLM 图像识别 (1 个节点)
    echo "[4/5] 启动 VLM 视觉识别..."
    roslaunch abot_vlm vlm_node.launch &
    sleep 2

    # 5. 任务状态机 + 安全监控 (2 个节点)
    echo "[5/5] 启动任务状态机..."
    roslaunch mission_manager sim_mission.launch sim_mode:=${SIM_MODE} &
    sleep 2

    echo "========================================"
    echo "  全部 14 个节点已启动"
    echo "========================================"
    echo ""
    echo "节点清单:"
    echo "  [底层] abot_driver, abot_imu, rplidar, box_filter"
    echo "  [融合] robot_state_publisher, robot_pose_ekf"
    echo "  [定位] map_server, cartographer_node, amcl(备)"
    echo "  [导航] move_base (GlobalPlanner + DWA)"
    echo "  [语音] game_node (Snowboy)"
    echo "  [视觉] vlm_node (豆包 Vision Pro)"
    echo "  [任务] mission_state_machine, safety_monitor"
    echo ""
    if [ "${SIM_MODE}" = "true" ]; then
        echo "仿真模式：发布 'sim_wakeup' 到 /start topic 触发比赛开始"
        echo "  rostopic pub /start std_msgs/String \"data: 'sim_wakeup'\""
    fi

    wait

else
    # ===== 实车模式：GNOME 终端分窗口 =====

    # 窗口 1: roscore
    gnome-terminal -- bash -c '
        source /opt/ros/melodic/setup.bash
        roscore
        exec bash' &
    sleep 2

    # 窗口 2: 底盘 + IMU + LiDAR + EKF + 模型 (5 个节点)
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 3
        roslaunch abot_bringup robot_with_imu.launch
        exec bash" &
    sleep 2

    # 窗口 3: 导航栈 (map_server + cartographer + move_base)
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 6
        roslaunch robot_slam nav_cartographer.launch map_name:=${MAP_NAME}
        exec bash" &
    sleep 2

    # 窗口 4: 唤醒词 + VLM
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 10
        roslaunch robot_slam GameStart.launch &
        sleep 2
        roslaunch abot_vlm vlm_node.launch &
        exec bash" &
    sleep 2

    # 窗口 5: 任务状态机 + 安全监控
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 14
        roslaunch mission_manager sim_mission.launch sim_mode:=${SIM_MODE}
        exec bash" &
    sleep 2

    # 窗口 6: RViz 可视化 (可选)
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 16
        roslaunch robot_slam view_nav.launch
        exec bash" &

    echo "========================================"
    echo "  6 个终端窗口已启动"
    echo "========================================"
    echo "窗1: roscore"
    echo "窗2: 底盘驱动 (abot_driver + IMU + LiDAR + EKF)"
    echo "窗3: 导航栈 (map_server + Cartographer + move_base)"
    echo "窗4: 唤醒词 + VLM 视觉"
    echo "窗5: 任务状态机 + 安全监控"
    echo "窗6: RViz 可视化"
    echo ""
    echo "等待唤醒词或发布 sim_wakeup..."
fi
