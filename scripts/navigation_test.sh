#!/bin/bash
# ============================================
# 模式 2：纯导航测试
# 用途: 加载先验地图, 按预设路径点顺序导航, 验证导航精度
#   用法: bash scripts/navigation_test.sh [地图名] [路径脚本]
#   节点: roscore + bringup(IMU) + nav(AMCL+map+move_base) + multi_goals + RViz
#   无视觉/语音/唤醒词
# ============================================

WS_PATH="${HOME}/abot_ws"
MAP_NAME="${1:-game}"
GOALS_SCRIPT="${2:-navigation_multi_goals_4.py}"

echo "=== ABOT 预设路径导航测试 ==="
echo "地图: ${MAP_NAME}"
echo "路径脚本: ${GOALS_SCRIPT}"

export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

if grep -qi microsoft /proc/version 2>/dev/null; then
    # ===== WSL 模式 =====
    echo "[WSL] 后台启动模式..."

    roscore &
    sleep 2

    source /opt/ros/melodic/setup.bash
    source ${WS_PATH}/devel/setup.bash

    roslaunch abot_bringup robot_with_imu.launch &
    sleep 5

    roslaunch robot_slam navigation.launch map_name:=${MAP_NAME} &
    sleep 8

    echo "=== 导航栈已启动 (AMCL) ==="
    echo "启动预设路径导航..."
    rosrun robot_slam ${GOALS_SCRIPT}
    wait

else
    # ===== 实车模式 =====
    gnome-terminal -- bash -c '
        source /opt/ros/melodic/setup.bash
        roscore
        exec bash' &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 3
        roslaunch abot_bringup robot_with_imu.launch
        exec bash" &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 8
        roslaunch robot_slam navigation.launch map_name:=${MAP_NAME}
        exec bash" &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 10
        roslaunch robot_slam view_nav.launch
        exec bash" &
    sleep 2

    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        sleep 14
        rosrun robot_slam ${GOALS_SCRIPT}
        exec bash" &

    echo "=== 5 个终端窗口已启动 ==="
    echo "1. roscore"
    echo "2. 底盘驱动 (abot_driver + IMU + LiDAR + EKF)"
    echo "3. 导航栈 (map_server + AMCL + move_base)"
    echo "4. RViz 可视化"
    echo "5. 预设路径导航 (${GOALS_SCRIPT})"
    echo ""
    echo "可用的路径脚本:"
    echo "  navigation_multi_goals_4.py  - 13 个路径点 (推荐)"
    echo "  navigation_multi_goals.py    - 8 个路径点 (旧版, 待迁移)"
fi
