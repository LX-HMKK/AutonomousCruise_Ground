#!/usr/bin/env python
import rospy
from std_msgs.msg import String

def publish_audio():
    # 初始化节点
    rospy.init_node('audio_publisher', anonymous=True)
    
    # 创建发布者对象，发布到audio_topic主题，消息类型为String
    publisher = rospy.Publisher('audio_topic', String, queue_size=10)
    
    # 消息发布次数
    publish_count = 2
    
    # 循环直到发布次数达到设定值
    while not rospy.is_shutdown() and publish_count > 0:
        # 创建要发布的字符串消息
        audio_data = ""
        
        # 发布消息
        publisher.publish(audio_data)
        
        # 打印消息发布状态
        rospy.loginfo("Published: %s", audio_data)
        
        # 减少发布次数
        publish_count -= 1
        
        # 保持循环频率
        rate = rospy.Rate(1)  # 确保rate在循环内部定义，以便每次循环都能更新频率
        rate.sleep()

if __name__ == '__main__':
    try:
        publish_audio()
    except rospy.ROSInterruptException:
        pass
