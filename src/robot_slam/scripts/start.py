#!/usr/bin/env python
'''
Copyright (c) [Zachary]
本代码受版权法保护，未经授权禁止任何形式的复制、分发、修改等使用行为。
Author:Zachary
'''
import rospy
from std_msgs.msg import String
import decoder
import sys
import signal

interrupted = False

def signal_handler(signal, frame):
    global interrupted
    interrupted = True

def interrupt_callback():
    global interrupted
    return interrupted

def detected_callback():
    decoder.play_audio_file()  # 播放音频文件
    rospy.set_param('start',True )

if __name__ == '__main__':
    # 初始化ROS节点
    rospy.init_node('game_node', anonymous=True)
    
    # 设置模型路径
    model = '/home/abot/abot_ws/src/robot_slam/resources/models/startGame.pmdl'
    
    # 捕获SIGINT信号，例如Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建热词检测器
    detector = decoder.HotwordDetector(model, sensitivity=0.5)
    print('Listening... Press Ctrl+C to exit')
    
    # 主循环
    detector.start(detected_callback=detected_callback,
                   interrupt_check=interrupt_callback,
                   sleep_time=0.03)
    
    # 保持ROS节点运行
    rospy.spin()
    
    # 终止检测器
    detector.terminate()
