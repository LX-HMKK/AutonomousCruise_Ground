#!/bin/bash
# Full end-to-end competition simulation test
# Runs inside WSL Ubuntu 18.04
set -e

source /opt/ros/melodic/setup.bash
source /home/lx_hm/abot_ws/devel/setup.bash

RUN_LOG=/tmp/full_test_run.log
echo "" > $RUN_LOG

# ========================
echo "=== STEP 1: Start roscore ===" | tee -a $RUN_LOG
# ========================
roscore &
ROSCORE_PID=$!
sleep 6

for i in 1 2 3 4 5; do
    if rostopic list >/dev/null 2>&1; then
        echo "roscore ready (attempt $i)" | tee -a $RUN_LOG
        break
    fi
    sleep 2
done

# ========================
echo "=== STEP 2: Launch simulation ===" | tee -a $RUN_LOG
# ========================
roslaunch mission_manager sim_full_mission.launch --screen >> /tmp/mission_nodes.log 2>&1 &
MISSION_PID=$!
echo "Mission PID: $MISSION_PID" | tee -a $RUN_LOG

sleep 20

# ========================
echo "=== STEP 3: Check nodes ===" | tee -a $RUN_LOG
# ========================
rosnode list 2>&1 | tee -a $RUN_LOG

# Find mission log
MISSION_LOG=$(ls $HOME/.ros/log/*/mission_state_machine-*.log 2>/dev/null | tail -1)
echo "Mission log: $MISSION_LOG" | tee -a $RUN_LOG

if [ -n "$MISSION_LOG" ]; then
    echo "=== Mission State (initial) ===" | tee -a $RUN_LOG
    grep -i "State\|Wake\|IDLE\|Waiting\|Ready\|init" "$MISSION_LOG" | tail -15 | tee -a $RUN_LOG
fi

# ========================
echo "=== STEP 4: Set AMCL pose ===" | tee -a $RUN_LOG
# ========================
rostopic pub /initialpose geometry_msgs/PoseWithCovarianceStamped \
    "{header: {frame_id: map}, pose: {pose: {position: {x: 1.0, y: 1.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}}" -1 2>&1 | tee -a $RUN_LOG

sleep 8

# ========================
echo "=== STEP 5: Trigger wakeup ===" | tee -a $RUN_LOG
# ========================
rostopic pub /start std_msgs/String "sim_wakeup" -1 2>&1 | tee -a $RUN_LOG

sleep 5

# ========================
echo "=== STEP 6: Progress after wakeup ===" | tee -a $RUN_LOG
# ========================
if [ -n "$MISSION_LOG" ]; then
    grep -i "mission\|State\|Navigat\|Recogn\|Arrive\|Phase\|TTS\|vision\|cell\|ABORT\|DONE\|wake\|goal\|mock" "$MISSION_LOG" | tail -40 | tee -a $RUN_LOG
fi

sleep 15

# ========================
echo "=== STEP 7: Final progress ===" | tee -a $RUN_LOG
# ========================
if [ -n "$MISSION_LOG" ]; then
    grep -i "mission\|State\|Navigat\|Recogn\|Arrive\|Phase\|TTS\|vision\|cell\|ABORT\|DONE" "$MISSION_LOG" | tail -50 | tee -a $RUN_LOG
fi

# ========================
echo "=== STEP 8: Nodes still running ===" | tee -a $RUN_LOG
# ========================
rosnode list 2>&1 | tee -a $RUN_LOG

# ========================
echo "=== STEP 9: Errors ===" | tee -a $RUN_LOG
# ========================
if [ -n "$MISSION_LOG" ]; then
    grep -i "error\|fatal\|traceback\|ABORT\|crash\|ERROR\|died" "$MISSION_LOG" | head -20 | tee -a $RUN_LOG
fi

echo "=== TEST COMPLETE ===" | tee -a $RUN_LOG
