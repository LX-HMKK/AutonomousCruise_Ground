#!/bin/bash
# ============================================
# WSL 完整比赛仿真测试
# 打开 WSL 终端，执行:
#   bash /mnt/d/StudyWorks/3.2/MachineVision_Project/AutonomousCruise_Ground/scripts/sim_full_test.sh
# ============================================

WS="$HOME/abot_ws"
LOG="/tmp/sim_full.log"
SRC="/mnt/d/StudyWorks/3.2/MachineVision_Project/AutonomousCruise_Ground"

echo "========================================"
echo "  ABOT 地面巡航 — 完整仿真测试"
echo "========================================"

# 1. 清理（必须杀掉 rosmaster，不能只杀 roscore 外壳脚本）
echo "[1/6] 清理旧进程..."
killall -9 rosmaster rosout roscore roslaunch rviz 2>/dev/null || true
sleep 1
# 确保 11311 端口释放
fuser -k 11311/tcp 2>/dev/null || true
sleep 1

# 2. 同步 + 编译
echo "[2/6] 同步源码 + 编译..."
mkdir -p "$WS"/src/mission_manager/launch
cp "$SRC"/src/mission_manager/scripts/*.py "$WS"/src/mission_manager/scripts/
cp "$SRC"/src/mission_manager/launch/*.launch "$WS"/src/mission_manager/launch/
cp "$SRC"/src/mission_manager/CMakeLists.txt "$WS"/src/mission_manager/
cp "$SRC"/config/*.yaml "$WS"/config/ 2>/dev/null || true

source /opt/ros/melodic/setup.bash
cd "$WS"
catkin_make 2>&1 | grep -E "Error|FAILED|Built target" | tail -3
echo "  编译完成"

# 3. 启动完整仿真 (roslaunch 自动管理 roscore)
echo "[3/6] 启动仿真 (roslaunch 自动启动 roscore)..."
source /opt/ros/melodic/setup.bash
source "$WS"/devel/setup.bash
roslaunch mission_manager sim_full_mission.launch > "$LOG" 2>&1 &
sleep 20  # 10 个节点启动需要时间

echo ""
echo "  === 运行中节点 ==="
rosnode list 2>&1
echo ""

NODE_COUNT=$(rosnode list 2>&1 | wc -l)
echo "  节点数: $NODE_COUNT"

# 5. 设置初始位姿 + 触发唤醒
echo "[4/6] 设置初始位姿 (x=1.0, y=1.0)..."
# 单行格式，避免多行 heredoc 卡住
rostopic pub -1 /initialpose geometry_msgs/PoseWithCovarianceStamped '{header: {frame_id: map}, pose: {pose: {position: {x: 1.0, y: 1.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}, covariance: [0.25,0,0,0,0,0, 0,0.25,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0.0685]}}' 2>&1
sleep 5

echo "  触发唤醒..."
rostopic pub -1 /start std_msgs/String "data: 'sim_wakeup'" 2>&1
echo "  唤醒已发送"

# 6. 监控进展
echo "[5/6] 监控任务进展 (60s)..."
echo "========================================"

for i in $(seq 1 15); do
    sleep 4
    T=$((i*4))
    echo ""
    echo "--- T+${T}s ---"
    # 状态跳转
    grep -i "->\|Navigating\|Arrived\|Recogni\|cell.*target\|TTS\|speak\|DONE\|ABORT" "$LOG" 2>/dev/null | tail -8
    # 当前位置
    rostopic echo /odom -n 1 2>&1 | grep "position" | head -1 || true
done

echo ""
echo "========================================"
echo "  仿真测试报告"
echo "========================================"
echo ""
echo "节点状态:"
rosnode list 2>&1
echo ""
echo "完整任务日志:"
grep -i "->\|Navigating\|Arrived\|Recogni\|Phase\|cell\|TTS\|DONE\|ABORT\|ERROR\|vision_result\|speak" "$LOG" 2>/dev/null
echo ""
echo "错误检查:"
grep -i "error\|fatal\|ABORT\|Traceback" "$LOG" 2>/dev/null | head -10 || echo "  (无错误)"
echo ""
echo "完整日志: $LOG"
echo "========================================"
echo "  测试完成。按 Enter 停止所有节点"
echo "========================================"
read -r
pkill -f roscore 2>/dev/null
pkill -f roslaunch 2>/dev/null
echo "已停止"
