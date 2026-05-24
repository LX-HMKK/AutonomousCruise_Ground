#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 上面这行是一个 shebang，用来告诉系统使用哪个解释器来执行这个脚本。在这里，它告诉系统使用环境中的Python解释器。
# 这一行指定了文件的编码格式为 UTF-8。这对于处理包含非英文字符的文本是很重要的。
import rospy
# 导入ROS的Python库
from ar_track_alvar_msgs.msg import AlvarMarkers
# 从ar_track_alvar_msgs模块中导入AlvarMarkers消息类型
id = 0
# 设置一个全局变量id并初始化为0
class ARTracker:
	def __init__(self):
		rospy.init_node('ar_tracker_node',anonymous=True)
        # 初始化ROS节点，节点名称为'ar_tracker_node'，并设置为匿名节点
		self.ar_sub = rospy.Subscriber('/ar_pose_marker', AlvarMarkers, self.ar_cb)
        # 创建一个订阅者对象，订阅名为'/ar_pose_marker'的话题，消息类型为AlvarMarkers，回调函数为self.ar_cb
	def ar_cb(self,data):
		global id
        # 声明使用全局变量id
		for marker in data.markers:
			id = marker.id
            # 将接收到的marker的id赋值给全局变量id
			print id
            # 打印id

        # 创建ARTracker类的一个实例
if __name__ == '__main__':
	try:
		ARTracker = ARTracker()
        # 进入ROS事件循环
		rospy.spin()
        # 如果遇到ROS的中断异常，则忽略，不做处理
    	except rospy.ROSInterruptException:
        	pass

