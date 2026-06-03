#!/bin/bash
# WSL 完整比赛仿真测试 (带计时诊断)
WS="$HOME/abot_ws"
LOG="/tmp/sim_full.log"
SRC="/mnt/d/StudyWorks/3.2/MachineVision_Project/AutonomousCruise_Ground"

echo "========================================"
echo "  ABOT 地面巡航 — 完整仿真测试"
echo "========================================"

TOTAL_START=$(date +%s)

# 1. 清理
echo "[1/5] 清理旧进程..."
killall -9 rosmaster rosout roscore roslaunch rviz 2>/dev/null || true
sleep 2

# 2. 同步源码（不编译，Python 脚本直接运行）
echo "[2/5] 同步源码..."
T0=$(date +%s)
mkdir -p "$WS"/src/mission_manager/launch "$WS"/config
cp "$SRC"/src/mission_manager/scripts/*.py "$WS"/src/mission_manager/scripts/
cp "$SRC"/src/mission_manager/launch/*.launch "$WS"/src/mission_manager/launch/
cp "$SRC"/config/*.yaml "$WS"/config/ 2>/dev/null || true
cp "$SRC"/src/robot_slam/maps/game.* "$WS"/src/robot_slam/maps/ 2>/dev/null || true
T1=$(date +%s); echo "  sync: $((T1-T0))s"

# 3. 启动仿真 (roslaunch 自动管理 roscore，用 rostopic 检查比 rosnode list 更快)
echo "[3/5] 启动仿真..."
source /opt/ros/melodic/setup.bash
source "$WS"/devel/setup.bash
# 换随机端口避免 TIME_WAIT
export ROS_MASTER_URI=http://localhost:0
roslaunch mission_manager sim_full_mission.launch > "$LOG" 2>&1 &
sleep 20
T3=$(date +%s); echo "  launch wait: $((T3-T1))s (total)"

echo ""
echo "  === 节点进程 ==="
# 从 log 文件读节点列表（不依赖 rosnode，避免 XML-RPC 超时卡死）
grep "process\[" "$LOG" 2>/dev/null | grep "started with pid" | sed "s/.*process\[//;s/\].*//" || echo "(读取中...)"
echo ""

# 4. 初始位姿 (唤醒由 launch 文件自动触发)
echo "[4/5] 设置初始位姿 (x=0.0, y=0.0)..."
source /opt/ros/melodic/setup.bash
source "$WS"/devel/setup.bash
rostopic pub -1 /initialpose geometry_msgs/PoseWithCovarianceStamped '{header: {frame_id: map}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}, covariance: [0.25,0,0,0,0,0, 0,0.25,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0, 0,0,0,0,0,0.0685]}}' 2>&1
sleep 2
echo "  等待自动唤醒 (launch 文件延迟 8s 发送)..."

# 5. 监控
echo "[5/5] 监控任务进展 (60s)..."
echo "========================================"
for i in $(seq 1 15); do
    sleep 4
    T=$((i*4))
    echo ""
    echo "--- T+${T}s ---"
    grep -i "->\|Navigating\|Arrived\|Recogni\|cell.*target\|TTS\|speak\|DONE\|ABORT" "$LOG" 2>/dev/null | tail -6
    rostopic echo /odom -n 1 2>&1 | grep "position" | head -1 || true
done

TOTAL_END=$(date +%s)
echo ""
echo "========================================"
echo "  仿真测试报告 (总耗时: $((TOTAL_END-TOTAL_START))s)"
echo "========================================"
echo "节点进程:"
grep "process\[" "$LOG" 2>/dev/null | grep "started with pid" | sed "s/.*process\[//;s/\].*//"
echo ""
echo "任务日志 (最近 20 行):"
strings "$LOG" 2>/dev/null | grep -iE "->|Navigating|Arrived|Recogni|cell|DONE|ABORT|Mission|Phase|vision" | tail -20
echo ""
strings "$LOG" 2>/dev/null | grep -iE "ABORT|Traceback|FATAL|ERROR" | grep -v "Unable" | tail -10 || echo "(无严重错误)"
echo ""
echo "完整日志: $LOG"
echo "按 Enter 停止..."
read -r
pkill -f roscore 2>/dev/null; pkill -f roslaunch 2>/dev/null
echo "已停止"
