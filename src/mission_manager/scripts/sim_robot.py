#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仿真机器人节点：发布 mock odometry、laser scan、TF，替代真实硬件。

使用方法:
  rosrun mission_manager sim_robot.py _init_x:=0.0 _init_y:=0.0 _init_yaw:=0.0

发布的 Topic:
  /odom            (nav_msgs/Odometry) - 里程计
  /scan_filtered   (sensor_msgs/LaserScan) - 模拟空场地激光数据
  TF: odom -> base_footprint -> base_link
"""
import rospy
import math
import tf
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist, Quaternion, TransformStamped


class SimRobot(object):
    """仿真机器人：响应 /cmd_vel 更新位姿，发布 odom + laser + TF。"""

    def __init__(self):
        init_x = rospy.get_param('~init_x', -1.5)
        init_y = rospy.get_param('~init_y', 1.5)
        init_yaw = rospy.get_param('~init_yaw', 0.0)

        self.x = init_x
        self.y = init_y
        self.yaw = init_yaw

        # 发布
        self.odom_pub = rospy.Publisher('/odom', Odometry, queue_size=10)
        self.scan_pub = rospy.Publisher('/scan_filtered', LaserScan, queue_size=10)
        self.tf_br = tf.TransformBroadcaster()

        # 订阅 cmd_vel 模拟运动
        rospy.Subscriber('/cmd_vel', Twist, self._on_cmd_vel)

        self.last_time = rospy.Time.now()

        rospy.loginfo('[SimRobot] Robot at (%.2f, %.2f, %.2f)', self.x, self.y, self.yaw)

    def _on_cmd_vel(self, msg):
        """接收 cmd_vel，更新模拟位姿。"""
        now = rospy.Time.now()
        dt = (now - self.last_time).to_sec()
        if dt <= 0 or dt > 0.5:
            dt = 0.05
        self.last_time = now

        # 麦克纳姆轮全向模型（简化：独立 x/y/theta 位移）
        self.x += msg.linear.x * math.cos(self.yaw) * dt
        self.y += msg.linear.x * math.sin(self.yaw) * dt
        # y 方向（全向横移）
        self.x -= msg.linear.y * math.sin(self.yaw) * dt
        self.y += msg.linear.y * math.cos(self.yaw) * dt
        self.yaw += msg.angular.z * dt

    def _publish_odom(self):
        """发布里程计消息。"""
        msg = Odometry()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = 'odom'
        msg.child_frame_id = 'base_footprint'
        msg.pose.pose.position.x = self.x
        msg.pose.pose.position.y = self.y
        q = tf.transformations.quaternion_from_euler(0, 0, self.yaw)
        msg.pose.pose.orientation = Quaternion(*q)
        # 设置 covariance 为合理值
        msg.pose.covariance = [0.001, 0, 0, 0, 0, 0,
                               0, 0.001, 0, 0, 0, 0,
                               0, 0, 1e6, 0, 0, 0,
                               0, 0, 0, 1e6, 0, 0,
                               0, 0, 0, 0, 1e6, 0,
                               0, 0, 0, 0, 0, 0.001]
        msg.twist.twist.linear.x = 0
        msg.twist.twist.angular.z = 0
        self.odom_pub.publish(msg)

    def _publish_scan(self):
        """发布模拟激光数据（空场地 = 全部最大量程 12m）。"""
        msg = LaserScan()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = 'laser_link'
        msg.angle_min = -math.pi
        msg.angle_max = math.pi
        msg.angle_increment = math.pi / 180.0  # 1 度分辨率
        msg.time_increment = 0
        msg.scan_time = 0.1
        msg.range_min = 0.15
        msg.range_max = 12.0
        num_readings = 360
        msg.ranges = [12.0] * num_readings  # 全部最大量程 = 空场地
        msg.intensities = [0.0] * num_readings
        self.scan_pub.publish(msg)

    def _publish_tf(self):
        """发布 TF：odom -> base_footprint -> base_link。"""
        now = rospy.Time.now()
        q = tf.transformations.quaternion_from_euler(0, 0, self.yaw)

        # odom -> base_footprint
        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation = Quaternion(*q)
        self.tf_br.sendTransformMessage(t)

        # base_footprint -> base_link (identity)
        t2 = TransformStamped()
        t2.header.stamp = now
        t2.header.frame_id = 'base_footprint'
        t2.child_frame_id = 'base_link'
        t2.transform.translation.x = 0.0
        t2.transform.translation.y = 0.0
        t2.transform.translation.z = 0.0
        t2.transform.rotation = Quaternion(0, 0, 0, 1)
        self.tf_br.sendTransformMessage(t2)

    def run(self):
        """主循环：20 Hz。"""
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            self._publish_odom()
            self._publish_scan()
            self._publish_tf()
            rate.sleep()


if __name__ == '__main__':
    rospy.init_node('sim_robot')
    sim = SimRobot()
    sim.run()
