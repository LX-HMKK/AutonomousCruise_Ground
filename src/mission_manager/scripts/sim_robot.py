#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仿真机器人节点：发布 mock odometry、laser scan、TF，替代真实硬件。

使用方法:
  rosrun mission_manager sim_robot.py _init_x:=-1.6 _init_y:=1.6

发布的 Topic:
  /odom            (nav_msgs/Odometry)
  /scan_filtered   (sensor_msgs/LaserScan) — 含动态障碍物
  TF: odom -> base_footprint, map -> odom

障碍物:
  从 competition_field.yaml 的 obstacles 字段读取 cell 编号,
  在激光扫描中注入短距读数 (仿真 LiDAR 检测障碍物)
"""
import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import rospy
import math
import yaml
import tf
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist, Quaternion, TransformStamped

# config 路径
CONFIG_PATHS = [
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config'),
    os.path.expanduser('~/abot_ws/src/config'),
]


def _find_config(filename):
    for d in CONFIG_PATHS:
        p = os.path.join(os.path.abspath(d), filename)
        if os.path.isfile(p):
            return p
    return None


def _cell_to_xy(cell, rows=9, cols=9, cell_sz=0.4, field_sz=3.6):
    """网格编号 → map 坐标"""
    n = cell - 1
    row = n // cols
    col = n % cols
    x = (col - cols / 2.0) * cell_sz + cell_sz / 2.0
    y = (rows / 2.0 - row) * cell_sz - cell_sz / 2.0
    return x, y


class SimRobot(object):
    """仿真机器人：响应 /cmd_vel 更新位姿，发布 odom + laser(含障碍物) + TF。"""

    def __init__(self):
        init_x = rospy.get_param('~init_x', -1.6)
        init_y = rospy.get_param('~init_y', 1.6)
        init_yaw = rospy.get_param('~init_yaw', 0.0)

        self.x = init_x
        self.y = init_y
        self.yaw = init_yaw

        # 加载障碍物 (从 competition_field.yaml)
        self.obstacle_xy = []
        config_path = _find_config('competition_field.yaml')
        if config_path:
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f)
            field = cfg['field']
            for obs in (cfg.get('obstacles') or []):
                cx, cy = _cell_to_xy(obs['cell'],
                                     field['grid_rows'], field['grid_cols'],
                                     field['cell_size_m'], field['size_m'][0])
                self.obstacle_xy.append((cx, cy, field['cell_size_m'] * 0.4))
            if self.obstacle_xy:
                rospy.loginfo('[SimRobot] %d dynamic obstacles loaded', len(self.obstacle_xy))

        # 发布
        self.odom_pub = rospy.Publisher('/odom', Odometry, queue_size=10)
        self.scan_pub = rospy.Publisher('/scan_filtered', LaserScan, queue_size=10)
        self.tf_br = tf.TransformBroadcaster()

        # 订阅 cmd_vel 模拟运动
        rospy.Subscriber('/cmd_vel', Twist, self._on_cmd_vel)
        self.last_time = rospy.Time.now()

        rospy.loginfo('[SimRobot] Init at (%.2f, %.2f, %.2f)  obstacles=%d',
                      self.x, self.y, self.yaw, len(self.obstacle_xy))

    def _on_cmd_vel(self, msg):
        now = rospy.Time.now()
        dt = (now - self.last_time).to_sec()
        if dt <= 0 or dt > 0.5:
            dt = 0.05
        self.last_time = now

        self.x += msg.linear.x * math.cos(self.yaw) * dt
        self.y += msg.linear.x * math.sin(self.yaw) * dt
        self.x -= msg.linear.y * math.sin(self.yaw) * dt
        self.y += msg.linear.y * math.cos(self.yaw) * dt
        self.yaw += msg.angular.z * dt

    def _publish_odom(self):
        msg = Odometry()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = 'odom'
        msg.child_frame_id = 'base_footprint'
        msg.pose.pose.position.x = self.x
        msg.pose.pose.position.y = self.y
        q = tf.transformations.quaternion_from_euler(0, 0, self.yaw)
        msg.pose.pose.orientation = Quaternion(*q)
        msg.pose.covariance = [0.001, 0, 0, 0, 0, 0,
                               0, 0.001, 0, 0, 0, 0,
                               0, 0, 1e6, 0, 0, 0,
                               0, 0, 0, 1e6, 0, 0,
                               0, 0, 0, 0, 1e6, 0,
                               0, 0, 0, 0, 0, 0.001]
        self.odom_pub.publish(msg)

    def _publish_scan(self):
        msg = LaserScan()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = 'laser_link'
        msg.angle_min = -math.pi
        msg.angle_max = math.pi
        msg.angle_increment = math.pi / 180.0
        msg.time_increment = 0
        msg.scan_time = 0.1
        msg.range_min = 0.15
        msg.range_max = 12.0
        num_readings = 360
        ranges = [12.0] * num_readings

        # 注入障碍物: 对每个激光射线, 检查是否命中障碍物
        for ox, oy, orad in self.obstacle_xy:
            dx = ox - self.x
            dy = oy - self.y
            dist = math.hypot(dx, dy)
            if dist > 12.0:
                continue
            bearing = math.atan2(dy, dx) - self.yaw
            # 障碍物张角
            angular_half = math.atan2(orad, dist) if dist > orad else 0.3
            for i in range(num_readings):
                ray_angle = msg.angle_min + i * msg.angle_increment
                # 规范化角度差
                angle_diff = ray_angle - bearing
                while angle_diff > math.pi:
                    angle_diff -= 2 * math.pi
                while angle_diff < -math.pi:
                    angle_diff += 2 * math.pi
                if abs(angle_diff) < angular_half and ranges[i] > dist:
                    ranges[i] = dist - orad  # 障碍物表面距离

        msg.ranges = ranges
        msg.intensities = [0.0] * num_readings
        self.scan_pub.publish(msg)

    def _publish_tf(self):
        now = rospy.Time.now()
        q = tf.transformations.quaternion_from_euler(0, 0, self.yaw)

        t_map = TransformStamped()
        t_map.header.stamp = now
        t_map.header.frame_id = 'map'
        t_map.child_frame_id = 'odom'
        t_map.transform.translation.x = 0.0
        t_map.transform.translation.y = 0.0
        t_map.transform.translation.z = 0.0
        t_map.transform.rotation = Quaternion(0, 0, 0, 1)
        self.tf_br.sendTransformMessage(t_map)

        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation = Quaternion(*q)
        self.tf_br.sendTransformMessage(t)

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            self._publish_odom()
            self._publish_scan()
            self._publish_tf()
            rate.sleep()


if __name__ == '__main__':
    rospy.init_node('sim_robot')
    SimRobot().run()
