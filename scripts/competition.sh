#!/bin/bash
# ============================================
# 模式 1 / 模式 3：完整比赛 / 导航+视觉+语音
#
# 模式 1 (sim_mode=false): 完整比赛 — Snowboy 唤醒 + 导航 + 豆包VLM + TTS播报
#   用法: bash scripts/competition.sh game false
#   节点: roscore + bringup(IMU) + nav(AMCL+map+move_base) + GameStart(Snowboy)
#         + VLM(doubao) + TTS(doubao) + state_machine(sim_mode=false) + safety
#
# 模式 3 (sim_mode=true):  导航+视觉+语音 — 无唤醒词, 5s 自动开始
#   用法: bash scripts/competition.sh game true
#   节点: 同上但不启动 GameStart, 状态机 5s 后自动进入流程
#
# SSH 启动: 自动检测 SSH_TTY，使用 setsid 后台模式替代 GNOME 终端
#   用法: ssh abot@IP 'bash ~/abot_dev_ws/scripts/competition.sh competition_field true'
#
# 数据流:
#   game_node --/start--> mission_state_machine  (仅模式1)
#   vlm_node  --/vision_result--> mission_state_machine
#   mission_state_machine --/voiceWords--> doubao_tts → /tts_done
#   mission_state_machine --move_base action--> 导航
#   safety_monitor --/safety_status--> mission_state_machine
# ============================================

WS_PATH="${HOME}/abot_dev_ws"
MAP_NAME="${1:-competition_field}"
# 地图名不带 .yaml 则自动补全 (navigation.launch 的 map_server 需指向 .yaml 文件)
[[ "$MAP_NAME" != *.yaml ]] && MAP_NAME="${MAP_NAME}.yaml"
SIM_MODE="${2:-false}"  # false=模式1(唤醒词)  true=模式3(自动开始)

MODE_NAME="模式1: 完整比赛"
[ "${SIM_MODE}" = "true" ] && MODE_NAME="模式3: 导航+视觉+语音"

echo "========================================"
echo "  ABOT 地面巡航 — ${MODE_NAME}"
echo "========================================"
echo "地图:     ${MAP_NAME}"
echo "节点数:   $([ "${SIM_MODE}" = "true" ] && echo '11 (无唤醒词)' || echo '13')"
echo "========================================"

export DISPLAY=:0
export XAUTHORITY=/run/user/1000/gdm/Xauthority

# ============================================
# ROS 网络环境锁定
# ============================================
export ROS_MASTER_URI=http://localhost:11311
export ROS_HOSTNAME=localhost

# ===== 解释器隔离 (B3/B4) =====
# 不砍 anaconda，只让 /usr/bin 排最前保证 python→py2.7，anaconda site-packages 保留可 import
ENV_PY2='export PATH="/usr/bin:/opt/ros/melodic/bin:$PATH"'
ENV_PY39='export PATH="/opt/ros/melodic/bin:$(echo "$PATH" | sed -e "s#/home/abot/anaconda3[^:]*:##g" -e "s#:/home/abot/anaconda3[^:]*##g")"
__PY39SHIM=/tmp/abot_py39_shim; mkdir -p "$__PY39SHIM"; ln -sf /home/abot/anaconda3/envs/py39/bin/python3.9 "$__PY39SHIM/python3"; export PATH="$__PY39SHIM:$PATH"'

READY_HELPERS='
wait_master() { for i in $(seq 1 40); do timeout 2 rostopic list >/dev/null 2>&1 && return 0; sleep 1; done; echo "[warn] roscore 未就绪, 继续"; }
wait_topic() { for i in $(seq 1 ${2:-40}); do timeout 2 rostopic list 2>/dev/null | grep -qx "$1" && return 0; sleep 1; done; echo "[warn] 等待 $1 超时, 继续"; }
'

if grep -qi microsoft /proc/version 2>/dev/null; then
    # ===== WSL 仿真模式 =====
    echo "[WSL] 仿真后台启动..."

    roscore &
    sleep 2

    source /opt/ros/melodic/setup.bash
    source ${WS_PATH}/devel/setup.bash

    # 1. 底盘 + 传感器层
    echo "[1/5] 启动底盘驱动..."
    roslaunch abot_bringup robot_with_imu.launch &
    sleep 5

    # 2. 导航层
    echo "[2/5] 启动导航栈..."
    roslaunch robot_slam navigation.launch map_name:=${MAP_NAME} &
    sleep 8

    # 3. 唤醒词检测
    echo "[3/5] 启动唤醒词检测..."
    roslaunch robot_slam GameStart.launch &
    sleep 2

    # 4. VLM 图像识别
    echo "[4/5] 启动 VLM 视觉识别..."
    roslaunch abot_vlm vlm_node.launch &
    sleep 2

    # 5. 任务状态机 + 安全监控
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
    echo "  [定位] map_server, amcl"
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

elif [ -n "$SSH_CONNECTION" ] || ! command -v gnome-terminal >/dev/null 2>&1; then
    # ===== SSH 后台模式 (无 GNOME 桌面) =====
    echo "[SSH] 清理旧进程..."
    pkill -f 'roscore|roslaunch|rosrun|rplidarNode|move_base|amcl|mission_state_machine|safety_monitor|doubao_tts|top_view_shot_node|usb_cam_node' 2>/dev/null || true
    sleep 3
    # 确保 ROS master 端口释放
    while lsof -ti:11311 >/dev/null 2>&1; do
        echo "  等待端口 11311 释放..."
        sleep 1
    done
    rm -f /tmp/comp_*.log

    echo "[SSH] 后台启动 (模式: ${MODE_NAME})..."
    setsid bash -c "
        # Python: /usr/bin first → python=py2.7(ROS); anaconda py39 在 PATH 供 worker 显式调用
        export PATH=\"/usr/bin:/opt/ros/melodic/bin:/home/abot/anaconda3/envs/py39/bin:\$PATH\"
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash

        echo '[1/5] roscore...'
        roscore > /tmp/comp_roscore.log 2>&1 &
        sleep 5

        echo '[2/5] 底盘驱动...'
        roslaunch abot_bringup robot_with_imu.launch > /tmp/comp_bringup.log 2>&1 &
        sleep 12

        echo '[3/5] 导航栈...'
        roslaunch robot_slam navigation.launch map_name:=${MAP_NAME} > /tmp/comp_nav.log 2>&1 &
        sleep 15

        echo '[3.5] 发送初始位姿...'
        sleep 3
        rostopic pub -1 /initialpose geometry_msgs/PoseWithCovarianceStamped \"{header: {frame_id: map}, pose: {pose: {position: {x: -1.6, y: 1.6, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}, covariance: [0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.068]}}\"
        # 等待 AMCL 收敛 (不阻塞: 最多等 10s)

        echo '[4/5] VLM + TTS...'
        roslaunch abot_vlm vlm_node.launch > /tmp/comp_vlm.log 2>&1 &
        sleep 3
        rosrun robot_slam doubao_tts.py > /tmp/comp_tts.log 2>&1 &
        sleep 2

        echo '[5/5] 状态机 + 安全...'
        roslaunch mission_manager sim_mission.launch sim_mode:=${SIM_MODE} > /tmp/comp_mission.log 2>&1 &

        echo '=== 全部启动完成 ==='
        rostopic list 2>/dev/null | wc -l | xargs -I{} echo '话题数: {}'
        echo '日志: /tmp/comp_*.log'
        while true; do sleep 60; done
    " > /tmp/comp_startup.log 2>&1 &
    disown
    echo "后台已启动，等待节点就绪..."
    sleep 35
    source /opt/ros/melodic/setup.bash
    source ${WS_PATH}/devel/setup.bash
    echo ""
    echo "=== 节点 ==="
    timeout 3 rosnode list 2>/dev/null || echo "(等待中...)"
    echo ""
    echo "=== 关键话题 ==="
    timeout 3 rostopic list 2>/dev/null | grep -E "/scan_filtered|/amcl_pose|/map\b|/vision_result|/voiceWords|/tts_done|/mission_state" || echo "(等待中...)"
    echo ""
    echo "========================================"
    [ "${SIM_MODE}" = "false" ] && echo "说出'开始比赛'启动..." || echo "模式3: 5s 后自动开始. 监控: rosrun robot_slam nav_monitor.py"

else
    # ===== GNOME 桌面模式 (原有逻辑) =====
    # 窗口 1: roscore
    gnome-terminal -- bash -c '
        source /opt/ros/melodic/setup.bash
        roscore
        exec bash' &
    sleep 1

    # 窗口 2: 底盘 + IMU + LiDAR + EKF + 模型
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        $ENV_PY2
        $READY_HELPERS
        wait_master
        roslaunch abot_bringup robot_with_imu.launch
        exec bash" &
    sleep 1

    # 窗口 3: 导航栈
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        $ENV_PY2
        $READY_HELPERS
        wait_master
        wait_topic /scan_filtered 40
        roslaunch robot_slam navigation.launch map_name:=${MAP_NAME}
        exec bash" &
    sleep 1

    # 窗口 4: ASR + VLM + TTS
    if [ "${SIM_MODE}" = "false" ]; then
        gnome-terminal -- bash -c "
            source /opt/ros/melodic/setup.bash
            source ${WS_PATH}/devel/setup.bash
            $ENV_PY39
            $READY_HELPERS
            wait_master
            rosrun robot_slam doubao_asr.py &
            sleep 2
            roslaunch abot_vlm vlm_node.launch &
            sleep 2
            rosrun robot_slam doubao_tts.py &
            exec bash" &
    else
        gnome-terminal -- bash -c "
            source /opt/ros/melodic/setup.bash
            source ${WS_PATH}/devel/setup.bash
            $ENV_PY39
            $READY_HELPERS
            wait_master
            roslaunch abot_vlm vlm_node.launch &
            sleep 2
            rosrun robot_slam doubao_tts.py &
            exec bash" &
    fi
    sleep 1

    # 窗口 5: 状态机 + 安全
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        $ENV_PY2
        $READY_HELPERS
        wait_master
        wait_topic /move_base/status 60
        roslaunch mission_manager sim_mission.launch sim_mode:=${SIM_MODE}
        exec bash" &
    sleep 1

    # 窗口 6: RViz
    gnome-terminal -- bash -c "
        source /opt/ros/melodic/setup.bash
        source ${WS_PATH}/devel/setup.bash
        $ENV_PY2
        $READY_HELPERS
        wait_master
        wait_topic /map 30
        roslaunch robot_slam view_nav.launch
        exec bash" &

    echo "========================================"
    echo "  6 个终端窗口已启动"
    echo "========================================"
    echo "窗1: roscore"
    echo "窗2: 底盘驱动 (abot_driver + IMU + LiDAR + EKF)"
    echo "窗3: 导航栈 (map_server + AMCL + move_base)"
    echo "窗4: $([ "${SIM_MODE}" = "false" ] && echo '豆包 ASR 语音识别 + ')/VLM 视觉 + TTS 语音"
    echo "窗5: 任务状态机 + 安全监控"
    echo "窗6: RViz 可视化"
    echo ""
    [ "${SIM_MODE}" = "false" ] && echo "说出'开始比赛'启动..." || echo "模式3: 5s 后自动开始"
fi
