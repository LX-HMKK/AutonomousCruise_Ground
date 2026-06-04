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
try:
    from visualization_msgs.msg import Marker, MarkerArray
    HAS_MARKER = True
except ImportError:
    HAS_MARKER = False

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

        # 加载障碍物 (从 competition_field.yaml) — 建模为线段(纸板)
        self.obstacle_segments = []
        try:
            config_path = _find_config('competition_field.yaml')
            if config_path:
                with open(config_path, 'r') as f:
                    cfg = yaml.safe_load(f)
                field = cfg['field']
                board_w = 0.40
                for obs in (cfg.get('obstacles') or []):
                    cx, cy = _cell_to_xy(obs['cell'],
                                         field['grid_rows'], field['grid_cols'],
                                         field['cell_size_m'], field['size_m'][0])
                    yaw = math.radians(obs.get('yaw_deg', 45))
                    half = board_w / 2.0
                    ax = cx - half * math.cos(yaw)
                    ay = cy - half * math.sin(yaw)
                    bx = cx + half * math.cos(yaw)
                    by = cy + half * math.sin(yaw)
                    self.obstacle_segments.append((ax, ay, bx, by, cx, cy))
                if self.obstacle_segments:
                    rospy.loginfo('[SimRobot] %d board obstacles loaded', len(self.obstacle_segments))
        except Exception as e:
            rospy.logwarn('[SimRobot] Failed to load obstacles: %s (continuing without)', e)
            self.obstacle_segments = []

        # 发布
        self.odom_pub = rospy.Publisher('/odom', Odometry, queue_size=10)
        self.scan_pub = rospy.Publisher('/scan_filtered', LaserScan, queue_size=10)
        if HAS_MARKER:
            self.obs_marker_pub = rospy.Publisher('/sim_obstacles', MarkerArray, queue_size=10)
            self._publish_obstacle_markers()
        self.tf_br = tf.TransformBroadcaster()

        # 订阅 cmd_vel 模拟运动
        rospy.Subscriber('/cmd_vel', Twist, self._on_cmd_vel)
        self.last_time = rospy.Time.now()

        rospy.loginfo('[SimRobot] Init at (%.2f, %.2f, %.2f)  obstacles=%d',
                      self.x, self.y, self.yaw, len(self.obstacle_segments))

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

        # 线段障碍物: 射线-线段求交 (纸板, 不是圆桶)
        for ax, ay, bx, by, cx, cy in self.obstacle_segments:
            # 线段向量
            sx = bx - ax
            sy = by - ay
            seg_len_sq = sx * sx + sy * sy
            if seg_len_sq < 1e-10:
                continue

            for i in range(num_readings):
                ray_angle = msg.angle_min + i * msg.angle_increment + self.yaw
                rdx = math.cos(ray_angle)
                rdy = math.sin(ray_angle)
                rx = self.x
                ry = self.y

                # 射线-线段求交 (2D cross product)
                cross_rs = rdx * sy - rdy * sx
                if abs(cross_rs) < 1e-10:
                    continue  # 平行

                # t = 射线参数, u = 线段参数
                dx_ar = rx - ax
                dy_ar = ry - ay
                t = (dx_ar * sy - dy_ar * sx) / (-cross_rs)
                u = (dx_ar * rdy - dy_ar * rdx) / cross_rs

                if t > 0.01 and 0.0 <= u <= 1.0:
                    if t < ranges[i]:
                        ranges[i] = t

        msg.ranges = ranges
        msg.intensities = [0.0] * num_readings
        self.scan_pub.publish(msg)

    def _publish_obstacle_markers(self):
        """发布障碍物可视化 Marker (薄板, RViz 可看到纸板形状和朝向)。"""
        ma = MarkerArray()
        for i, (ax, ay, bx, by, cx, cy) in enumerate(self.obstacle_segments):
            m = Marker()
            m.header.frame_id = 'map'
            m.header.stamp = rospy.Time.now()
            m.ns = 'sim_obstacles'
            m.id = i
            m.type = Marker.CUBE
            m.action = Marker.ADD
            m.pose.position.x = cx
            m.pose.position.y = cy
            m.pose.position.z = 0.15
            # 朝向: 线段方向
            yaw = math.atan2(by - ay, bx - ax)
            q = tf.transformations.quaternion_from_euler(0, 0, yaw)
            m.pose.orientation = Quaternion(*q)
            # 挡板尺寸: 宽40cm × 厚1cm × 高30cm
            m.scale.x = 0.40
            m.scale.y = 0.01
            m.scale.z = 0.30
            m.color.r = 1.0
            m.color.g = 0.3
            m.color.b = 0.1
            m.color.a = 0.85
            m.lifetime = rospy.Duration(0.5)
            ma.markers.append(m)
        self.obs_marker_pub.publish(ma)

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
        tick = 0
        while not rospy.is_shutdown():
            self._publish_odom()
            self._publish_scan()
            self._publish_tf()
            tick += 1
            if HAS_MARKER and tick % 10 == 0:
                self._publish_obstacle_markers()
            rate.sleep()


if __name__ == '__main__':
    rospy.init_node('sim_robot')
    SimRobot().run()
