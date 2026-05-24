#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""安全监控：watchdog、heartbeat、碰撞检测、超时检查。"""
import os
import sys
import rospy
import time

from std_msgs.msg import String, Empty
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan

# Add common scripts to path
_common_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'common', 'scripts')
if os.path.isdir(_common_dir):
    sys.path.insert(0, _common_dir)

from mission_logger import MissionLogger


class SafetyMonitor(object):
    """安全监控器。独立节点，监控硬件和任务健康状态。"""

    def __init__(self):
        self.logger = MissionLogger()

        # 参数（从 ROS param server 读取，支持运行时调整）
        self.collision_range_m = rospy.get_param('~collision_range_m', 0.10)
        self.heartbeat_timeout_s = rospy.get_param('~heartbeat_timeout_s', 5.0)
        self.no_motion_timeout_s = rospy.get_param('~no_motion_timeout_s', 20.0)

        # 状态
        self.last_heartbeat_time = time.time()
        self.last_motion_time = time.time()
        self.last_odom = None
        self.motion_started = False
        self.estop_active = False

        # 订阅
        rospy.Subscriber('/scan_filtered', LaserScan, self._on_scan)
        rospy.Subscriber('/odom', Odometry, self._on_odom)
        rospy.Subscriber('/mission_heartbeat', String, self._on_heartbeat)
        rospy.Subscriber('/mission_estop', Empty, self._on_estop)

        # 发布
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.status_pub = rospy.Publisher('/safety_status', String, queue_size=10)

        rospy.loginfo('[Safety] Monitor initialized. collision=%.2fm, heartbeat=%.1fs, motion_timeout=%.1fs',
                      self.collision_range_m, self.heartbeat_timeout_s, self.no_motion_timeout_s)

    def _on_scan(self, msg):
        """激光数据回调：检测近距离障碍物（碰撞风险）。"""
        if self.estop_active:
            return
        for i, dist in enumerate(msg.ranges):
            if msg.range_min < dist < self.collision_range_m:
                rospy.logerr('[Safety] COLLISION RISK! Range[%d]=%.3fm < %.3fm',
                             i, dist, self.collision_range_m)
                self.logger.log_system('collision_risk',
                                       'range[{}]={:.3f}m'.format(i, dist))
                self._emergency_stop('collision_risk')
                return

    def _on_odom(self, msg):
        """里程计回调：检测机器人是否在运动。"""
        if self.last_odom is None:
            self.last_odom = msg
            return

        dx = msg.pose.pose.position.x - self.last_odom.pose.pose.position.x
        dy = msg.pose.pose.position.y - self.last_odom.pose.pose.position.y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist > 0.01:  # 移动超过 1cm 则认为在运动
            self.last_motion_time = time.time()
            if not self.motion_started:
                self.motion_started = True
                self.logger.log_system('motion_started', 'first movement detected')

        self.last_odom = msg

    def _on_heartbeat(self, msg):
        """任务状态机心跳回调。"""
        self.last_heartbeat_time = time.time()

    def _on_estop(self, msg):
        """手动急停指令回调。"""
        rospy.logwarn('[Safety] Manual ESTOP requested!')
        self._emergency_stop('manual')

    def _emergency_stop(self, reason):
        """执行紧急停止。"""
        self.estop_active = True
        self.cmd_vel_pub.publish(Twist())
        self.logger.log_system('emergency_stop', reason)
        self.status_pub.publish(String(data='ESTOP:{}'.format(reason)))
        rospy.logerr('[Safety] EMERGENCY STOP: %s', reason)

    def check_timeouts(self):
        """检查超时条件（在主循环中调用）。"""
        now = time.time()

        # 检查启动后是否长时间未运动
        if not self.motion_started:
            if now - self.last_heartbeat_time > self.no_motion_timeout_s:
                rospy.logerr('[Safety] No motion after start (%.1fs > %.1fs)!',
                             now - self.last_heartbeat_time, self.no_motion_timeout_s)
                self._emergency_stop('no_motion_after_start')
                return

        # 检查心跳是否丢失
        heartbeat_elapsed = now - self.last_heartbeat_time
        if heartbeat_elapsed > self.heartbeat_timeout_s:
            rospy.logerr('[Safety] Heartbeat lost! Last: %.1fs ago (timeout: %.1fs)',
                         heartbeat_elapsed, self.heartbeat_timeout_s)
            self._emergency_stop('heartbeat_lost')
            return

    def run(self):
        """主循环：10 Hz 运行，持续检查超时。"""
        rate = rospy.Rate(10)
        while not rospy.is_shutdown():
            self.check_timeouts()
            if not self.estop_active:
                self.status_pub.publish(String(data='OK'))
            rate.sleep()


if __name__ == '__main__':
    rospy.init_node('safety_monitor')
    monitor = SafetyMonitor()
    monitor.run()
