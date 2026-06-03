#!/bin/bash
# WSL 验证脚本：测试导航栈 + RViz 可视化
set -e
source /opt/ros/melodic/setup.bash
source /home/lx_hm/abot_ws/devel/setup.bash

echo "=== ROS Environment ==="
echo "ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH"
echo "ROS_MASTER_URI=$ROS_MASTER_URI"

echo "=== Killing old processes ==="
pkill -f roscore 2>/dev/null || true
pkill -f rosout 2>/dev/null || true
sleep 1

echo "=== Starting roscore ==="
roscore &
sleep 3

echo "=== Checking roscore ==="
rosnode list

echo "=== Starting navigation stack with my_lab map ==="
roslaunch robot_slam navigation.launch map_name:=my_lab &
sleep 8

echo "=== Checking navigation nodes ==="
rosnode list

echo "=== Starting RViz ==="
roslaunch robot_slam view_nav.launch &
sleep 5

echo "=== All nodes running ==="
rosnode list

echo "=== System ready. Press Ctrl+C to stop. ==="
wait
