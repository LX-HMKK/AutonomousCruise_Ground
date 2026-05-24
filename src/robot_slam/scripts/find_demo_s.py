#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 上面这行是为了告诉操作系统，这是一个Python脚本，可以直接运行

import rospy
from geometry_msgs.msg import Point

class object_position:
    def __init__(self):
        # 初始化ROS节点，命名为'object_position_node'，并设置为匿名节点
        rospy.init_node('object_position_node', anonymous=True)
        # 创建一个订阅者，订阅/object_position话题，消息类型为Point，回调函数为find_cb
        self.find_sub = rospy.Subscriber('/object_position', Point, self.find_cb)

    # /object_position话题的回调函数
    def find_cb(self, data):
        # 获取接收到的Point消息
        point_msg = data
        # 打印接收到的点的x坐标
        print('x:', point_msg.x)
        # 打印接收到的点的y坐标
        print('y:', point_msg.y)
        # 打印接收到的点的z坐标
        print('z:', point_msg.z)

if __name__ == '__main__':
    try:
        # 创建object_position对象
        object_position = object_position()
        # 进入ROS事件循环
        rospy.spin()
    except rospy.ROSInterruptException:
        pass

