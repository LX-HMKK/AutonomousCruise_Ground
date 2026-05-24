#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 上面这行是为了告诉操作系统，这是一个Python脚本，可以直接运行

import rospy
from geometry_msgs.msg import Point, Twist
import serial
import time
from std_msgs.msg import String

# 设置串口和波特率
serialPort = "/dev/shoot"
baudRate = 9600

# 打开串口
ser = serial.Serial(port=serialPort, baudrate=baudRate, parity="N", bytesize=8, stopbits=1)

class object_position:
    def __init__(self):
        # 初始化ROS节点，命名为'object_position_node'，并设置为匿名节点
        rospy.init_node('object_position_node', anonymous=True)
        # 创建一个订阅者，订阅/object_position话题，消息类型为Point，回调函数为find_cb
        self.find_sub = rospy.Subscriber('/object_position', Point, self.find_cb)
        # 创建一个发布者，用于发布Twist类型的消息到/cmd_vel话题
        self.pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1000)

    # /object_position话题的回调函数
    def find_cb(self, data):
        global flog0, flog1
        # 获取接收到的Point消息
        point_msg = data
        # 计算目标点与图像中心的偏差
        flog0 = point_msg.x - 320
        # 计算偏差的绝对值
        flog1 = abs(flog0)
        # 如果偏差的绝对值大于0.5
        if abs(flog1) > 0.5:
            # 创建一个Twist消息
            msg = Twist()
            # 设置消息的角速度为偏差乘以0.01
            msg.angular.z = -0.01 * flog0
            # 发布Twist消息
            self.pub.publish(msg)
        # 如果偏差的绝对值小于等于0.5
        elif abs(flog1) <= 0.5:
            # 发送射击指令
            ser.write(b'\x55\x01\x12\x00\x00\x00\x01\x69')
            print ('打印射击')
            # 等待0.1秒
            time.sleep(0.08)
            # 发送停止射击指令
            ser.write(b'\x55\x01\x11\x00\x00\x00\x01\x68')

if __name__ == '__main__':
    try:
        # 创建object_position对象
        object_position = object_position()
        # 进入ROS事件循环
        rospy.spin()
    except rospy.ROSInterruptException:
        pass

