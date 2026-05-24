#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 上面这行指定了Python解释器路径，使得脚本可以直接在命令行中执行
import rospy
import serial
import time
from std_msgs.msg import String

# 设置串口和波特率
serialPort = "/dev/shoot"
baudRate = 9600

# 打开串口
ser = serial.Serial(port=serialPort, baudrate=baudRate, parity="N", bytesize=8, stopbits=1)

if __name__ == '__main__':
    try:
        # 发送射击指令
        ser.write(b'\x55\x01\x12\x00\x00\x00\x01\x69')
        print ('打印射击')
        # 等待0.1秒
        time.sleep(0.08)
        # 发送停止射击指令
        ser.write(b'\x55\x01\x11\x00\x00\x00\x01\x68')
        # 进入ROS的spin循环，保持节点持续运行
        rospy.spin()
    except:
        pass

