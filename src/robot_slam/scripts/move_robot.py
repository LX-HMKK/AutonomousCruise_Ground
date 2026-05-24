#!/usr/bin/env python
#coding: utf-8
# 上面两行是为了告诉操作系统，这是一个Python脚本，并且使用UTF-8编码

import rospy
from geometry_msgs.msg import Twist

class move_robot:
    def __init__(self):
        # 初始化ROS节点，命名为'move_robot_node'，并设置为匿名节点
        rospy.init_node('move_robot_node', anonymous=True)
        # 创建一个发布者，用于发布Twist类型的消息到/cmd_vel话题
        self.pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1000)

    # 控制机器人移动的回调函数
    def move_cb(self):
        global time
        # 初始化时间变量
        time = 0
        # 创建一个Twist消息
        msg = Twist()
        msg.linear.x = 1.0
        msg.linear.y = 0.0
        msg.linear.z = 0.0
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = 0.0
        # 控制机器人移动，持续1秒
        while time < 10:
            self.pub.publish(msg)
            rospy.sleep(0.1)
            time += 1

if __name__ == '__main__':
    try:
        # 创建move_robot对象
        move = move_robot()
        # 调用move_cb函数，控制机器人移动
        move.move_cb()
    except rospy.ROSInterruptException:
        pass




