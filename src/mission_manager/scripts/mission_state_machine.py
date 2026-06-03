#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""地面巡航比赛任务状态机。统一管理比赛流程。"""
import os
import sys
# Python 2 中文兼容：设置默认编码为 UTF-8
reload(sys)
sys.setdefaultencoding('utf-8')
import rospy
import time
import json
import threading

from std_msgs.msg import String, Empty
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from actionlib_msgs.msg import GoalStatus
import actionlib
import tf.transformations as tft

# Add common scripts to path for imports
_common_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'common', 'scripts')
if os.path.isdir(_common_dir):
    sys.path.insert(0, _common_dir)

from config_loader import load_config, get_cell_center_xy
from mission_logger import MissionLogger


class MissionState(object):
    """Python 2 兼容的任务状态。支持 == 比较、.value 访问、set 成员。"""

    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        if isinstance(other, MissionState):
            return self.value == other.value
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return 'MissionState(%r)' % self.value


# 正常状态实例
MissionState.IDLE = MissionState('IDLE')
MissionState.WAIT_FOR_WAKEUP = MissionState('WAIT_FOR_WAKEUP')
MissionState.START_ANNOUNCE = MissionState('START_ANNOUNCE')
MissionState.NAVIGATE_TO_FINISH = MissionState('NAVIGATE_TO_FINISH')
MissionState.ARRIVE_FINISH = MissionState('ARRIVE_FINISH')
MissionState.FINISH_ANNOUNCE = MissionState('FINISH_ANNOUNCE')
MissionState.DONE = MissionState('DONE')
# 异常状态实例
MissionState.ABORT_COLLISION_RISK = MissionState('ABORT_COLLISION_RISK')
MissionState.ABORT_TIMEOUT = MissionState('ABORT_TIMEOUT')
MissionState.ABORT_LOCALIZATION_LOST = MissionState('ABORT_LOCALIZATION_LOST')
MissionState.ABORT_PERCEPTION_FAILED = MissionState('ABORT_PERCEPTION_FAILED')
MissionState.ABORT_NAVIGATION_FAILED = MissionState('ABORT_NAVIGATION_FAILED')
MissionState.MANUAL_STOP_REQUESTED = MissionState('MANUAL_STOP_REQUESTED')


def _task_image_state(cls, phase, step_name):
    """构建带序号的阶段状态，如 SEARCH_TASK_IMAGE_1"""
    return MissionState('{}_{}'.format(step_name, phase))


MissionState.task_image_state = classmethod(_task_image_state)


class MissionStateMachine(object):
    """比赛任务状态机。统一管理比赛流程。"""

    ABORT_STATES = {
        MissionState.ABORT_COLLISION_RISK,
        MissionState.ABORT_TIMEOUT,
        MissionState.ABORT_LOCALIZATION_LOST,
        MissionState.ABORT_PERCEPTION_FAILED,
        MissionState.ABORT_NAVIGATION_FAILED,
        MissionState.MANUAL_STOP_REQUESTED,
    }

    TASK_PHASE_STEPS = ['SEARCH_TASK_IMAGE', 'RECOGNIZE_TASK_IMAGE',
                        'NAVIGATE_TO_TASK', 'ARRIVE_TASK', 'ANNOUNCE_TASK']

    def __init__(self, sim_mode=False):
        self.sim_mode = sim_mode
        self.logger = MissionLogger()

        # 加载配置
        self.field_cfg = load_config('competition_field.yaml')
        self.mission_cfg = load_config('mission.yaml')
        self.voice_cfg = load_config('voice_text.yaml')

        # 状态机
        self.state = MissionState.IDLE
        self.task_index = 0           # 当前任务序号 (0-3，共 4 个)
        self.target_cell = None        # 当前目标任务点网格号
        self.task_cells_done = []      # 已完成的任务点列表
        self.state_start_time = time.time()
        self.mission_start_time = time.time()
        self.perception_retry_count = 0
        self.navigation_retry_count = 0
        self.finish_nav_retry_count = 0
        self.recognition_in_progress = False
        self.rotation_attempt = 0
        self.seen_image_ids = []  # 已识别的图像 ID，防止重复

        # ROS 接口
        # 先创建 heartbeat publisher 并立刻发布，防止 safety 误判超时
        self.heartbeat_pub = rospy.Publisher('/mission_heartbeat', String, queue_size=1)
        self.heartbeat_pub.publish(String(data='init'))
        self.voice_pub = rospy.Publisher('/voiceWords', String, queue_size=10)
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)

        self.move_base_client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo('[Mission] Waiting for move_base action server...')
        connected = self.move_base_client.wait_for_server(rospy.Duration(10.0))
        if not connected:
            rospy.logwarn('[Mission] move_base not available, navigation disabled')

        # 识别结果跟踪
        self.vision_result = None
        self.vision_result_event = threading.Event()

        # 当前位姿（用于精准到点判定）
        self.current_pose = None  # (x, y, yaw) in map frame

        # 订阅
        rospy.Subscriber('/start', String, self._on_wakeup)
        rospy.Subscriber('/vision_result', String, self._on_vision_result)
        rospy.Subscriber('/safety_status', String, self._on_safety_status)
        rospy.Subscriber('/abot/pose', PoseStamped, self._on_pose)
        rospy.Subscriber('/odom', Odometry, self._on_odom)

        # 心跳定时器 (2s 间隔，独立于主循环，防止安全监控误判超时)
        self.heartbeat_timer = rospy.Timer(rospy.Duration(2.0), self._publish_heartbeat)

        rospy.loginfo('[Mission] State machine initialized, sim_mode=%s', sim_mode)

    def _publish_heartbeat(self, event):
        """心跳定时器回调。"""
        self.heartbeat_pub.publish(String(data='alive'))

    def transition(self, new_state):
        """状态跳转，记录日志。"""
        old = self.state.value
        self.state = new_state
        self.state_start_time = time.time()
        rospy.loginfo('[Mission] %s -> %s', old, new_state.value)
        self.logger.log_state_transition(old, new_state.value)

    # ========== 主循环 ==========

    def run(self):
        rate = rospy.Rate(10)  # 10 Hz
        self.mission_start_time = time.time()
        self.transition(MissionState.WAIT_FOR_WAKEUP)

        while not rospy.is_shutdown():
            try:
                # heartbeat 由 rospy.Timer 独立发布
                self._check_global_timeouts()

                if self.state == MissionState.WAIT_FOR_WAKEUP:
                    self._handle_wait_for_wakeup()
                elif self.state == MissionState.START_ANNOUNCE:
                    self._handle_start_announce()
                elif self.state == MissionState.NAVIGATE_TO_FINISH:
                    self._handle_navigate_to_finish()
                elif self.state == MissionState.ARRIVE_FINISH:
                    self._handle_arrive_finish()
                elif self.state == MissionState.FINISH_ANNOUNCE:
                    self._handle_finish_announce()
                elif self.state == MissionState.DONE:
                    rospy.loginfo('[Mission] All tasks completed successfully!')
                    break
                elif self.state in self.ABORT_STATES:
                    self._handle_abort()
                    break
                else:
                    self._handle_task_phase()

                rate.sleep()
            except Exception as e:
                import traceback
                rospy.logerr('[Mission] Unhandled exception: %s', str(e))
                rospy.logerr('[Mission] Traceback:\n%s', traceback.format_exc())
                rospy.sleep(1.0)
                raise

    # ========== Callbacks ==========

    def _on_wakeup(self, msg):
        if self.state == MissionState.WAIT_FOR_WAKEUP:
            if self.sim_mode and msg.data == 'sim_wakeup':
                rospy.loginfo('[Mission] Simulated wakeup received')
                self.transition(MissionState.START_ANNOUNCE)
            elif not self.sim_mode and msg.data == 'True':
                rospy.loginfo('[Mission] Wake word detected!')
                self.transition(MissionState.START_ANNOUNCE)

    def _on_vision_result(self, msg):
        if not self.recognition_in_progress:
            return
        try:
            result = json.loads(msg.data)
            confidence = result.get('confidence', 0)
            min_conf = self.mission_cfg['confidence']['min_confidence']
            image_id = result.get('image_id', '')

            rospy.loginfo('[Mission] Vision result: cell=%s, confidence=%.2f, id=%s',
                          result.get('target_cell'), confidence, image_id)

            # 检查是否已识别过同一张图像
            phase = self.task_index + 1
            if image_id and image_id in self.seen_image_ids:
                rospy.logwarn('[Mission] Phase %d: Image %s already recognized! Rotating...',
                              phase, image_id)
                self.rotation_attempt += 1
                if self.rotation_attempt < 4:
                    self._search_rotation(phase)
                else:
                    self._retry_perception(phase)
                return

            if confidence >= min_conf:
                self.target_cell = result['target_cell']
                if image_id:
                    self.seen_image_ids.append(image_id)
                self.logger.log_perception(result)
                self.perception_retry_count = 0
                self.rotation_attempt = 0
                self.recognition_in_progress = False
                self.vision_result = result
                self.vision_result_event.set()
            else:
                rospy.logwarn('[Mission] Low confidence %.2f < %.2f',
                              confidence, min_conf)
                self.rotation_attempt += 1
                if self.rotation_attempt < 4:
                    self._search_rotation(phase)
                else:
                    self._retry_perception(phase)
        except (ValueError, KeyError, TypeError) as e:
            rospy.logerr('[Mission] Invalid vision result: %s', str(e))

    def _on_pose(self, msg):
        """接收机器人当前位姿（/abot/pose topic）。"""
        q = msg.pose.orientation
        _, _, yaw = tft.euler_from_quaternion([q.x, q.y, q.z, q.w])
        self.current_pose = (msg.pose.position.x, msg.pose.position.y, yaw)

    def _on_odom(self, msg):
        """接收里程计数据，作为备选位姿来源（仿真用）。"""
        if self.current_pose is not None:
            return  # /abot/pose 优先级更高
        q = msg.pose.pose.orientation
        _, _, yaw = tft.euler_from_quaternion([q.x, q.y, q.z, q.w])
        self.current_pose = (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)

    def _get_current_pose(self):
        """返回最新的机器人位姿 (x, y, yaw)，若无数据则返回 (None, None, None)。"""
        if self.current_pose is not None:
            return self.current_pose
        return None, None, None

    def _on_safety_status(self, msg):
        """接收安全监控状态。"""
        if msg.data.startswith('ESTOP'):
            rospy.logerr('[Mission] Safety ESTOP received: %s', msg.data)
            data_lower = msg.data.lower()
            if 'collision' in data_lower:
                self.transition(MissionState.ABORT_COLLISION_RISK)
            elif 'manual' in data_lower:
                self.transition(MissionState.MANUAL_STOP_REQUESTED)
            else:
                self.transition(MissionState.ABORT_TIMEOUT)

    # ========== Phase Handlers ==========

    def _handle_wait_for_wakeup(self):
        rospy.loginfo_throttle(5, '[Mission] Waiting for wake word...')
        # 仿真模式下延迟 5s 自动触发
        if self.sim_mode and time.time() - self.state_start_time > 5.0:
            rospy.loginfo('[Mission] Auto-wakeup triggered (sim mode)')
            self.transition(MissionState.START_ANNOUNCE)

    def _handle_start_announce(self):
        text = self.voice_cfg['voice_text']['start']
        self._speak(text)
        self.logger.log_voice(text, 'start')
        self.task_index = 0
        self.perception_retry_count = 0
        phase = self.task_index + 1
        self.transition(MissionState.task_image_state(phase, 'SEARCH_TASK_IMAGE'))

    def _handle_task_phase(self):
        """处理 4 轮任务中的当前阶段。"""
        phase = self.task_index + 1

        current_step = None
        for step in self.TASK_PHASE_STEPS:
            expected_state = MissionState.task_image_state(phase, step)
            if self.state == expected_state:
                current_step = step
                break

        if current_step is None:
            rospy.logerr('[Mission] Unknown task state: %s', self.state.value)
            return

        if current_step == 'SEARCH_TASK_IMAGE':
            self._handle_search_task_image(phase)
        elif current_step == 'RECOGNIZE_TASK_IMAGE':
            self._handle_recognize_task_image(phase)
        elif current_step == 'NAVIGATE_TO_TASK':
            self._handle_navigate_to_task(phase)
        elif current_step == 'ARRIVE_TASK':
            self._handle_arrive_task(phase)
        elif current_step == 'ANNOUNCE_TASK':
            self._handle_announce_task(phase)

    def _search_rotation(self, phase):
        """旋转机器人扫描围栏不同方向，寻找任务图像。

        每旋转 90 度触发一次相机，最多 4 次（360 度）。
        找到图像后自动跳转 RECOGNIZE 状态。
        """
        self._stop_robot()
        rospy.sleep(0.5)

        # 旋转 90 度 (角速度 0.78 rad/s，仿真下缩短)
        twist = Twist()
        twist.angular.z = 0.78

        rospy.loginfo('[Mission] Phase %d: Rotating to scan fence (attempt %d/4)...',
                      phase, self.rotation_attempt + 1)

        # 清除之前的识别结果，防止中断旋转循环
        self.vision_result_event.clear()

        # 发布旋转指令
        rot_dur = 1.5 if self.sim_mode else 2.0
        end_time = rospy.Time.now() + rospy.Duration(rot_dur)
        while rospy.Time.now() < end_time and not rospy.is_shutdown():
            self.cmd_vel_pub.publish(twist)
            rospy.sleep(0.1)
            # 如果识别线程已经得到结果，提前停止旋转
            if self.vision_result_event.is_set():
                break

        # 停止旋转
        self._stop_robot()
        rospy.sleep(0.5)

        # 先标记识别进行中并清除事件，再触发相机，防止竞态导致结果丢失
        self.recognition_in_progress = True
        self.vision_result_event.clear()

        # 触发相机拍照
        rospy.set_param('/top_view_shot_node/im_flag', 1)
        rospy.loginfo('[Mission] Phase %d: Camera triggered at orientation %d/4',
                      phase, self.rotation_attempt + 1)

        # 等待识别结果（在 _handle_recognize_task_image 中处理超时）
        self.transition(MissionState.task_image_state(phase, 'RECOGNIZE_TASK_IMAGE'))

    def _handle_search_task_image(self, phase):
        text = self.voice_cfg['voice_text']['task_image_searching'].format(index=phase)
        self._speak(text)
        rospy.loginfo('[Mission] Phase %d: Searching for task image...', phase)

        self.rotation_attempt = 0
        self._search_rotation(phase)

    def _handle_recognize_task_image(self, phase):
        timeout = 10.0  # 每个方向等 10 秒
        detected = self.vision_result_event.wait(timeout=timeout)

        if not detected or self.recognition_in_progress:
            rospy.logwarn('[Mission] Phase %d: No recognition at rotation %d/4',
                          phase, self.rotation_attempt + 1)

            self.rotation_attempt += 1
            if self.rotation_attempt < 4:
                # 旋转到下一个方向继续搜索
                rospy.loginfo('[Mission] Phase %d: Rotating to next direction...', phase)
                self._search_rotation(phase)
                return
            else:
                # 4 个方向都扫过了，触发重试
                rospy.logwarn('[Mission] Phase %d: All 4 orientations scanned, retrying...', phase)
                self._retry_perception(phase)
                return

        rospy.loginfo('[Mission] Phase %d: Recognition successful, target cell=%d',
                      phase, self.target_cell)
        self.rotation_attempt = 0
        self.transition(MissionState.task_image_state(phase, 'NAVIGATE_TO_TASK'))

    def _handle_navigate_to_task(self, phase):
        if self.target_cell is None:
            rospy.logerr('[Mission] Phase %d: No target cell set!', phase)
            self.transition(MissionState.ABORT_PERCEPTION_FAILED)
            return

        x, y = get_cell_center_xy(self.target_cell, self.field_cfg)
        rospy.loginfo('[Mission] Phase %d: Navigating to cell %d (%.3f, %.3f)',
                      phase, self.target_cell, x, y)

        self._stop_robot()
        self._send_nav_goal(x, y)
        self.logger.log_navigation(
            {'cell': self.target_cell, 'x': x, 'y': y}, None, True)

        self.transition(MissionState.task_image_state(phase, 'ARRIVE_TASK'))

    def _handle_arrive_task(self, phase):
        timeout = rospy.Duration(self.mission_cfg['timeouts'].get('navigation_goal_timeout_s', 60))
        arrived = self.move_base_client.wait_for_result(timeout)

        if not arrived:
            rospy.logwarn('[Mission] Phase %d: Navigation timeout', phase)
            self.navigation_retry_count += 1
            max_retries = self.mission_cfg['timeouts']['navigation_retry_limit']
            if self.navigation_retry_count <= max_retries:
                rospy.loginfo('[Mission] Nav retry %d/%d', self.navigation_retry_count, max_retries)
                self.transition(MissionState.task_image_state(phase, 'NAVIGATE_TO_TASK'))
                return
            else:
                rospy.logerr('[Mission] Max nav retries exceeded')
                self.transition(MissionState.ABORT_NAVIGATION_FAILED)
                return

        # Check if navigation succeeded
        if self.move_base_client.get_state() != GoalStatus.SUCCEEDED:
            rospy.logwarn('[Mission] Phase %d: Navigation did not succeed (state=%d)',
                          phase, self.move_base_client.get_state())
            self.navigation_retry_count += 1
            max_retries = self.mission_cfg['timeouts']['navigation_retry_limit']
            if self.navigation_retry_count <= max_retries:
                rospy.loginfo('[Mission] Nav retry %d/%d', self.navigation_retry_count, max_retries)
                self.transition(MissionState.task_image_state(phase, 'NAVIGATE_TO_TASK'))
                return
            else:
                rospy.logerr('[Mission] Max nav retries exceeded')
                self.transition(MissionState.ABORT_NAVIGATION_FAILED)
                return

        self.navigation_retry_count = 0
        self._stop_robot()
        rospy.sleep(1.0)  # 等待位姿稳定

        # 精准到点判定：检查 footprint 是否完全进入任务点区域
        rx, ry, ryaw = self._get_current_pose()
        footprint = [[-0.175, -0.15], [-0.175, 0.15], [0.175, 0.15], [0.175, -0.15]]

        if rx is None:
            rospy.logwarn('[Mission] Phase %d: No pose available, skipping footprint check', phase)
        else:
            from config_loader import check_footprint_in_region
            in_region, detail = check_footprint_in_region(
                rx, ry, ryaw, footprint, self.target_cell, self.field_cfg)

            if not in_region:
                rospy.logwarn('[Mission] Phase %d: Footprint NOT fully inside task region! '
                              'Outside points: %d, task_center=(%.3f,%.3f), robot=(%.3f,%.3f,%.2f)',
                              phase, len(detail['points_outside']),
                              detail['task_center'][0], detail['task_center'][1],
                              rx, ry, ryaw)
                # 尝试精细靠拢：发送到任务点中心的微小修正
                cx, cy = detail['task_center']
                self._send_nav_goal(cx, cy, 0.0)
                return  # 再次等待 arrive

            rospy.loginfo('[Mission] Phase %d: Footprint verified inside task region', phase)

        self.task_cells_done.append(self.target_cell)
        rospy.loginfo('[Mission] Phase %d: Arrived at task point %d', phase, self.target_cell)
        self.transition(MissionState.task_image_state(phase, 'ANNOUNCE_TASK'))

    def _handle_announce_task(self, phase):
        text = self.voice_cfg['voice_text']['task_arrived'].format(target_cell=self.target_cell)
        self._speak(text)
        self.logger.log_voice(text, 'task_arrived')

        if self.task_index >= 3:  # 4 个任务全部完成
            rospy.loginfo('[Mission] All 4 tasks done, heading to finish')
            self.transition(MissionState.NAVIGATE_TO_FINISH)
        else:
            self.task_index += 1
            self.perception_retry_count = 0
            next_phase = self.task_index + 1
            self.target_cell = None
            self.transition(MissionState.task_image_state(next_phase, 'SEARCH_TASK_IMAGE'))

    # ========== Finish Phase Handlers ==========

    def _handle_navigate_to_finish(self):
        finish_cell = self.field_cfg['finish_cell']
        x, y = get_cell_center_xy(finish_cell, self.field_cfg)
        rospy.loginfo('[Mission] Navigating to finish cell %d (%.3f, %.3f)', finish_cell, x, y)

        text = self.voice_cfg['voice_text']['navigating_to_finish']
        self._speak(text)

        self._stop_robot()
        self._send_nav_goal(x, y)
        self.transition(MissionState.ARRIVE_FINISH)

    def _handle_arrive_finish(self):
        timeout = rospy.Duration(self.mission_cfg['timeouts'].get('navigation_goal_timeout_s', 60))
        arrived = self.move_base_client.wait_for_result(timeout)

        if not arrived:
            rospy.logwarn('[Mission] Finish navigation timeout')
            self.finish_nav_retry_count += 1
            max_retries = self.mission_cfg['timeouts']['navigation_retry_limit']
            if self.finish_nav_retry_count <= max_retries:
                rospy.loginfo('[Mission] Finish nav retry %d/%d',
                              self.finish_nav_retry_count, max_retries)
                self.transition(MissionState.NAVIGATE_TO_FINISH)
                return
            else:
                rospy.logwarn('[Mission] Max finish nav retries exceeded, proceeding anyway')
        elif self.move_base_client.get_state() != GoalStatus.SUCCEEDED:
            rospy.logwarn('[Mission] Finish navigation did not succeed (state=%d)',
                          self.move_base_client.get_state())
            self.finish_nav_retry_count += 1
            max_retries = self.mission_cfg['timeouts']['navigation_retry_limit']
            if self.finish_nav_retry_count <= max_retries:
                rospy.loginfo('[Mission] Finish nav retry %d/%d',
                              self.finish_nav_retry_count, max_retries)
                self.transition(MissionState.NAVIGATE_TO_FINISH)
                return
            else:
                rospy.logwarn('[Mission] Max finish nav retries exceeded, proceeding anyway')
        else:
            self.finish_nav_retry_count = 0

        self._stop_robot()
        self.transition(MissionState.FINISH_ANNOUNCE)

    def _handle_finish_announce(self):
        text = self.voice_cfg['voice_text']['finish']
        self._speak(text)
        self.logger.log_voice(text, 'finish')
        self.transition(MissionState.DONE)

    # ========== Abort ==========

    def _handle_abort(self):
        rospy.logerr('[Mission] ABORT: %s', self.state.value)
        self.logger.log_system('abort', self.state.value)
        self.move_base_client.cancel_all_goals()
        self._stop_robot()

        # Speak appropriate abort message
        abort_texts = {
            MissionState.ABORT_TIMEOUT: self.voice_cfg['voice_text']['abort_timeout'],
            MissionState.ABORT_COLLISION_RISK: self.voice_cfg['voice_text']['abort_collision'],
        }
        text = abort_texts.get(self.state, '任务终止')
        self._speak(text)

    # ========== Helpers ==========

    def _speak(self, text):
        """发送 TTS 播报。播报前强制停车，等待稳定后播报。"""
        self._stop_robot()
        hold_s = self.mission_cfg['mission'].get('voice_static_hold_s', 0.5)
        rospy.sleep(hold_s)
        try:
            msg = String()
            msg.data = text
            self.voice_pub.publish(msg)
        except Exception as e:
            rospy.logerr('[Mission] TTS publish failed: %s', str(e))
        rospy.loginfo('[Mission] TTS: %s', text)
        # 等待播报完成（仿真下缩短）
        sleep_s = 1.0 if self.sim_mode else 2.0
        rospy.sleep(sleep_s)

    def _stop_robot(self):
        """确保机器人完全停止。"""
        self.cmd_vel_pub.publish(Twist())

    def _send_nav_goal(self, x, y, yaw=0.0):
        """通过 move_base actionlib 发送导航目标。"""
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = 'map'
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        quat = tft.quaternion_from_euler(0, 0, yaw)
        goal.target_pose.pose.orientation.z = quat[2]
        goal.target_pose.pose.orientation.w = quat[3]
        self.move_base_client.send_goal(goal)
        rospy.loginfo('[Mission] Nav goal sent: (%.3f, %.3f, %.2f rad)', x, y, yaw)

    def _check_global_timeouts(self):
        """检查比赛全局超时。"""
        mission_elapsed = time.time() - self.mission_start_time
        max_time = self.mission_cfg['mission']['max_time_s']
        if mission_elapsed > max_time:
            rospy.logerr('[Mission] Mission timeout: %.1fs > %ds', mission_elapsed, max_time)
            self.transition(MissionState.ABORT_TIMEOUT)
            return

        state_elapsed = time.time() - self.state_start_time
        max_state_time = self.mission_cfg['timeouts']['no_state_change_s']
        if state_elapsed > max_state_time:
            rospy.logwarn('[Mission] State timeout in %s: %.1fs > %ds',
                          self.state.value, state_elapsed, max_state_time)
            self.transition(MissionState.ABORT_TIMEOUT)

    def _retry_perception(self, phase):
        """处理识别重试：重置旋转计数器，从头开始搜索。"""
        max_retries = self.mission_cfg['timeouts']['perception_retry_limit']
        self.perception_retry_count += 1
        if self.perception_retry_count > max_retries:
            rospy.logerr('[Mission] Max perception retries (%d) exceeded', max_retries)
            self.transition(MissionState.ABORT_PERCEPTION_FAILED)
            return
        rospy.loginfo('[Mission] Perception retry %d/%d, restarting rotation search',
                      self.perception_retry_count, max_retries)
        self.rotation_attempt = 0
        self.recognition_in_progress = False
        self.vision_result_event.clear()
        # 回到搜索状态，从第一个方向重新开始
        self.transition(MissionState.task_image_state(phase, 'SEARCH_TASK_IMAGE'))


if __name__ == '__main__':
    rospy.init_node('mission_state_machine')
    sim_mode = rospy.get_param('~sim_mode', False)
    fsm = MissionStateMachine(sim_mode=sim_mode)
    fsm.run()
