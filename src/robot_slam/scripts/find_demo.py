#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 上面这行是一个shebang，用来告诉系统使用哪个解释器来执行这个脚本。在这里，它告诉系统使用环境中的Python解释器。
#UTF-8 是一种通用的字符编码方案，支持多种语言中的字符集。指定文件编码格式可以确保正确地处理文件中的特殊字符和非英文文本。
import rospy
# 导入ROS的Python库
from geometry_msgs.msg import Point
# 从geometry_msgs模块导入Point消息类型
find_id = 0
# 设置一个全局变量find_id并初始化为0
class object_position:
	def __init__(self):
		rospy.init_node('object_position_node',anonymous=True)
        # 初始化ROS节点，节点名称为'object_position_node'，并设置为匿名节点
		self.ar_sub = rospy.Subscriber('/object_position', Point, self.find_cb)
        # 创建一个订阅者对象，订阅名为'/object_position'的话题，消息类型为Point，回调函数为self.find_cb
	def find_cb(self,data):
		global find_id
        # 声明使用全局变量find_id
		point_msg = data
        # 获取订阅到的消息数据，并赋值给point_msg
		if(point_msg.z>=1 and point_msg.z<=10):
			find_id = 1
            # 如果point_msg的z值在1到10之间，则将find_id设为1
			print find_id
            # 打印find_id的值
		if(point_msg.z>=60 and point_msg.z<=70):
			find_id = 2
			print find_id
            # 如果point_msg的z值在60到70之间，则将find_id设为2

            # 打印find_id的值
if __name__ == '__main__':
        # 创建object_position类的一个实例
	try:
		object_position = object_position()
        # 进入ROS事件循环
		rospy.spin()
        # 如果遇到ROS的中断异常，则忽略，不做处理
    	except rospy.ROSInterruptException:
        	pass

