#!/bin/bash
# ============================================
# 模式一：键盘控制建图
# 用途：手动操控机器人在场地中移动，SLAM 实时构建地图
#
# 节点列表 (8个):
#   roscore + abot_driver + abot_imu + rplidar
#   + box_filter + robot_state_publisher
#   + slam_gmapping + teleop_keyboard
# ============================================

WS_PATH="${HOME}/abot_ws"
MAP_NAME="${1:-my_lab}"

echo "=== ABOT 键盘控制建图 ==="
echo "地图: ${WS_PATH}/src/robot_slam/maps/${MAP_NAME}"
echo "完成后运行: rosrun map_server map_saver -f ${WS_PATH}/src/robot_slam/maps/${MAP_NAME}"

# 设置 DISPLAY（实车 GNOME 桌面需要）
export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

# 检查是否为 WSL 环境
if grep -qi microsoft /proc/version 2>/dev/null; then
    # ===== WSL 模式：后台启动，无图形界面 =====
    echo "[WSL] 后台启动模式..."

    roscore &
    sleep 2

    source /opt/ros/melodic/setup.bash
    source ${WS_PATH}/devel/setup.bash

    roslaunch abot_bringup robot.launch &
    sleep 5

    roslaunch robot_slam gmapping.launch &
    sleep 5

    echo "=== 全部节点已启动 ==="
    echo "在另一个终端运行键盘控制:"
    echo "  source ${WS_PATH}/devel/setup.bash"
    echo "  rosrun teleop_twist_keyboard teleop_twist_keyboard.py"
    echo "保存地图:"
    echo "  rosrun map_server map_saver -f ${WS_PATH}/src/robot_slam/maps/${MAP_NAME}"
    wait

else
    # ===== 实车模式：GNOME 终端分窗口启动 =====
    gnome-terminal -- bash -c '
        source /opt/ros/melodic/setup.bash
        roscore
        exec bash' &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 3
        roslaunch abot_bringup robot.launch
        exec bash" &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 8
        roslaunch robot_slam gmapping.launch
        exec bash" &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 10
        roslaunch robot_slam view_mapping.launch
        exec bash" &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 12
        rosrun teleop_twist_keyboard teleop_twist_keyboard.py
        exec bash" &

    echo "=== 5 个终端窗口已启动 ==="
    echo "1. roscore"
    echo "2. 底盘驱动 (abot_driver + IMU + LiDAR)"
    echo "3. Gmapping SLAM"
    echo "4. RViz 可视化"
    echo "5. 键盘控制"
    echo ""
    echo "保存地图: rosrun map_server map_saver -f ${WS_PATH}/src/robot_slam/maps/${MAP_NAME}"
fi
