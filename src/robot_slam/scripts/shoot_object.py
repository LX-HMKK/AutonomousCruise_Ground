#!/usr/bin/env python

#coding: utf-8

import rospy
import math
import actionlib
import serial
import time
from std_msgs.msg import String
serialPort = "/dev/shoot"
baudRate = 9600
ser = serial.Serial(port=serialPort, baudrate=baudRate, parity="N", bytesize=8, stopbits=1)

from actionlib_msgs.msg import *
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from nav_msgs.msg import Path
from geometry_msgs.msg import PoseWithCovarianceStamped
from tf_conversions import transformations
from math import pi
from std_msgs.msg import String

from ar_track_alvar_msgs.msg import AlvarMarkers
from ar_track_alvar_msgs.msg import AlvarMarker
from geometry_msgs.msg import Twist
from geometry_msgs.msg  import Point
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import os
music_path="~/'07.mp3'"
id = 255
flog0 = 255
flog1 = 255
flog2 = 255
flog3 = 255
flog4 = 255
count = 0
time = 0
move_flog = 0
Yaw_th = 0.0040
Min_y = -0.36
Max_y = -0.30
ar_flog=255
case = 255
case1 = 255
case2 = 255
case3 = 255
class navigation_demo:
    def __init__(self):
        self.set_pose_pub = rospy.Publisher('/initialpose', PoseWithCovarianceStamped, queue_size=5)
        self.arrive_pub = rospy.Publisher('/voiceWords',String,queue_size=10)
        self.find_sub = rospy.Subscriber('/object_position', Point, self.find_cb);
        self.ar_sub = rospy.Subscriber('/ar_pose_marker', AlvarMarkers, self.ar_cb);
        self.move_base = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        self.move_base.wait_for_server(rospy.Duration(60))
	self.pub = rospy.Publisher("/cmd_vel",Twist,queue_size=1000)
    def end(self):
        global time
    	msg = Twist()
    	msg.linear.x = -0.3
    	msg.linear.y = -0.3
    	msg.linear.z = 0.0
    	msg.angular.x = 0.0
    	msg.angular.y = 0.0
    	msg.angular.z = 0.0
	while(time <= 15):
            self.pub.publish(msg)
            rospy.sleep(0.1)
            time = time + 1

    def ar_cb(self, data):
        global id  
        global flog,qr_x,msg,ar_flog,ar_x,point_msg,ar_x_abs,flog4,ar_x_0_abs,ar_y_0,Min_y,Max_y,case
        
        ar_markers = data
        for marker in data.markers:
            if marker.id ==0 and case == 1 :
              ar_x_0 = marker.pose.pose.position.x
              ar_y_0 = marker.pose.pose.position.y
              #print ar_x_0
	      #print "Y"
              #print ar_y_0
	      ar_x_0_abs = abs(ar_x_0)
	      if ar_x_0_abs >= Yaw_th :
		msg = Twist()
                msg.angular.z = -1 * ar_x_0
                self.pub.publish(msg)
	        if ar_y_0 <= Max_y   and ar_y_0>= Min_y :
	           ser.write(b'\x55\x01\x12\x00\x00\x00\x01\x69')
           	   print "shoot"
           	   rospy.sleep(0.08)
           	   ser.write(b'\x55\x01\x11\x00\x00\x00\x01\x68')
                   rospy.sleep(2)
                   case = 2
                   print case
                   self.goto(goals[2])
                   rospy.sleep(2)
            if marker.id ==0 and case == 2 :
               ar_x_0 = marker.pose.pose.position.x
               #print ar_x_0
               #print ar_x_0
	       ar_x_0_abs = abs(ar_x_0)
	       #print ar_x_0_abs
	       if ar_x_0_abs >= Yaw_th :
		   msg = Twist()
                   msg.angular.z = -1 * ar_x_0
                   self.pub.publish(msg)
	       elif ar_x_0_abs < Yaw_th :
	           ser.write(b'\x55\x01\x12\x00\x00\x00\x01\x69')
           	   print "shoot"
           	   rospy.sleep(0.07)
           	   ser.write(b'\x55\x01\x11\x00\x00\x00\x01\x68')
                   case = 3   
		   navi.goto(goals[3])
        	   rospy.sleep(2)
		   navi.end()
    
    def find_cb(self, data):
        global id  
        global flog0 , flog1 ,flog2,count,move_flog,point_msg,case
        id =255
        point_msg = data
        flog0 = point_msg.x -320
        flog1 = abs(flog0)
#        print '************************'
#        print case
#        print '************************'
        if abs(flog1) > 0.5 and point_msg.z == 34 and flog2 >= 255 and case == 0:
           msg = Twist()
           msg.angular.z = -0.01 * flog0
           self.pub.publish(msg)
           print flog0 * 0.01
        elif abs(flog1) <= 0.5 and point_msg.z == 34 and flog2 >= 255:
           ser.write(b'\x55\x01\x12\x00\x00\x00\x01\x69')
           print "shoot"
           rospy.sleep(0.08)
           ser.write(b'\x55\x01\x11\x00\x00\x00\x01\x68')
           self.goto(goals[1])
           rospy.sleep(2)
           case = 1
           flog2 = flog2 - 1

    def set_pose(self, p):
        if self.move_base is None:
            return False

        x, y, th = p

        pose = PoseWithCovarianceStamped()
        pose.header.stamp = rospy.Time.now()
        pose.header.frame_id = 'map'
        pose.pose.pose.position.x = x
        pose.pose.pose.position.y = y
        q = transformations.quaternion_from_euler(0.0, 0.0, th/180.0*pi)
        pose.pose.pose.orientation.x = q[0]
        pose.pose.pose.orientation.y = q[1]
        pose.pose.pose.orientation.z = q[2]
        pose.pose.pose.orientation.w = q[3]

        self.set_pose_pub.publish(pose)
        return True

    def _done_cb(self, status, result):
        rospy.loginfo("navigation done! status:%d result:%s"%(status, result))
        arrive_str = "arrived to traget point"
        self.arrive_pub.publish(arrive_str)

    def _active_cb(self):
        rospy.loginfo("[Navi] navigation has be actived")

    def _feedback_cb(self, feedback):
        msg = feedback
        #rospy.loginfo("[Navi] navigation feedback\r\n%s"%feedback)

    def goto(self, p):
        rospy.loginfo("[Navi] goto %s"%p)
        #arrive_str = "going to next point"
        #self.arrive_pub.publish(arrive_str)
        goal = MoveBaseGoal()

        goal.target_pose.header.frame_id = 'map'
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = p[0]
        goal.target_pose.pose.position.y = p[1]
        q = transformations.quaternion_from_euler(0.0, 0.0, p[2]/180.0*pi)
        goal.target_pose.pose.orientation.x = q[0]
        goal.target_pose.pose.orientation.y = q[1]
        goal.target_pose.pose.orientation.z = q[2]
        goal.target_pose.pose.orientation.w = q[3]

        self.move_base.send_goal(goal, self._done_cb, self._active_cb, self._feedback_cb)
        result = self.move_base.wait_for_result(rospy.Duration(60))
        if not result:
            self.move_base.cancel_goal()
            rospy.loginfo("Timed out achieving goal")
        else:
            state = self.move_base.get_state()
            if state == GoalStatus.SUCCEEDED:
                rospy.loginfo("reach goal %s succeeded!"%p)
        return True

    def cancel(self):
        self.move_base.cancel_all_goals()
        return True
if __name__ == "__main__":
    rospy.init_node('navigation_demo',anonymous=True)
    goalListX = rospy.get_param('~goalListX', '2.0, 2.0,2.0')
    goalListY = rospy.get_param('~goalListY', '2.0, 4.0,2.0')
    goalListYaw = rospy.get_param('~goalListYaw', '0, 90.0,2.0')

    goals = [[float(x), float(y), float(yaw)] for (x, y, yaw) in zip(goalListX.split(","),goalListY.split(","),goalListYaw.split(","))]
    print ('Please 1 to continue: ')
    input = raw_input()
    print (goals)
    r = rospy.Rate(1)
    r.sleep()
    navi = navigation_demo()
    navi.goto(goals[0])
    rospy.sleep(2)
    case = 0

    while not rospy.is_shutdown():
          r.sleep()
