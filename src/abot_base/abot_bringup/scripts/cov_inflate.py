#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""将 /wheel_odom 协方差放大 factor 倍后重新发布为 /wheel_odom_inflated。

robot_pose_ekf 没有内置传感器权重参数，仅使用消息中的协方差矩阵决定
各数据源信任度。本节点将轮式里程计协方差整体放大，让 EKF 更依赖 IMU
（麦克纳姆轮横移/转弯打滑导致轮式里程计不可信）。
"""
import rospy
from nav_msgs.msg import Odometry


class CovInflate(object):
    def __init__(self):
        self.factor = rospy.get_param('~factor', 5.0)
        self.pub = rospy.Publisher('/wheel_odom_inflated', Odometry, queue_size=5)
        self.sub = rospy.Subscriber('/wheel_odom', Odometry, self._cb)
        rospy.loginfo('[CovInflate] /wheel_odom covariance x%.1f -> /wheel_odom_inflated',
                      self.factor)

    def _cb(self, msg):
        msg.pose.covariance = [c * self.factor for c in msg.pose.covariance]
        msg.twist.covariance = [c * self.factor for c in msg.twist.covariance]
        self.pub.publish(msg)


if __name__ == '__main__':
    rospy.init_node('cov_inflate')
    CovInflate()
    rospy.spin()
