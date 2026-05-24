#!/usr/bin/env python
#coding: utf-8
# 上面两行是为了告诉操作系统，这是一个Python脚本，并且使用UTF-8编码

import rospy
from geometry_msgs.msg import Twist

# 定义移动机器人的函数
def move_robot(linear_x, angular_z):
    # 初始化ROS节点，命名为'move_robot_node'，并设置为匿名节点
    rospy.init_node('move_robot_node', anonymous=True)
    # 创建一个发布者，用于发布Twist类型的消息到/cmd_vel话题
    velocity_publisher = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
    # 设置ROS发布频率为10Hz
    rate = rospy.Rate(10)  

    # 创建一个Twist消息，设置线速度和角速度
    vel_msg = Twist()
    vel_msg.linear.x = linear_x
    vel_msg.angular.z = angular_z

    # 循环发布消息，直到节点被关闭
    while not rospy.is_shutdown():
        velocity_publisher.publish(vel_msg)
        rate.sleep()

if __name__ == '__main__':
    try:
        # 设置线速度和角速度
        linear_x = 0.2   # 线速度
        angular_z = 0.5  # 角速度
        # 调用move_robot函数，控制机器人移动
        move_robot(linear_x, angular_z)
    except rospy.ROSInterruptException:
        pass

