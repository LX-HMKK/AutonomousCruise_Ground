#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from volcenginesdkarkruntime import Ark
import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image as ROSImage
from std_msgs.msg import String
import sys
from PIL import Image, ImageFont, ImageDraw
import time
import base64
from API_KEY_DOUBAO import *


client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=DOUBAO_KEY 
)

def imgmsg_to_cv2(img_msg):
    dtype = np.dtype("uint8")  # Hardcode to 8 bits...
    dtype = dtype.newbyteorder('>' if img_msg.is_bigendian else '<')
    image_opencv = np.ndarray(shape=(img_msg.height, img_msg.width, 3), dtype=dtype, buffer=img_msg.data)

    # If the byte order is different between the message and the system.
    if img_msg.is_bigendian == (sys.byteorder == 'little'):
        image_opencv = image_opencv.byteswap().newbyteorder()

    # Convert to BGR if the encoding is not already BGR
    if img_msg.encoding == "rgb8":
        image_opencv = cv2.cvtColor(image_opencv, cv2.COLOR_RGB2BGR)
    elif img_msg.encoding == "mono8":
        image_opencv = cv2.cvtColor(image_opencv, cv2.COLOR_GRAY2BGR)
    elif img_msg.encoding != "bgr8":
        rospy.logerr("Unsupported encoding: %s", img_msg.encoding)
        return None

    return image_opencv

def doubao_vision_api(PROMPT=None, img_path='/home/abot/abot_ws/src/abot_vlm/temp/vl_now.jpg'):
    '''
    豆包大模型视觉语言多模态功能
    '''
    if PROMPT is None:
        PROMPT = rospy.get_param('/perception/prompt_template',
            '你是一个机器人比赛的视觉识别系统。'
            '请识别图中围栏上的任务信息图像，'
            '输出图像内容和对应的任务点编号（31-33, 40-42, 49-51 之一）。'
            '回复格式必须是 JSON：'
            '{"target_cell": <数字>, "content": "<图像内容描述>", "confidence": <0-1之间的浮点数>}'
            '如果无法识别，设置 confidence 为 0。')
    # 编码为base64数据
    with open(img_path, 'rb') as image_file:
        image = 'data:image/jpeg;base64,' + base64.b64encode(image_file.read()).decode('utf-8')
    
    # 向豆包大模型发起请求
    response = client.chat.completions.create(
        model="doubao-1-5-vision-pro-32k-250115",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image
                        }
                    },
                ]
            }
        ],
    )
    
    # 解析大模型返回结果
    result_str = response.choices[0].message.content.strip()
    result = str(result_str)
        
    print('豆包大模型调用成功！')
    print('结果:', result)
            
    return result

def top_view_shot(image_msg):
    global im_flag
    '''
    这里接收来自话题/usb_cam/image_raw的ROS图像格式的消息，并保存图像，是否拍照用的参数服务器，然后设置参数就行，注意要加命名空间路径
    '''
    # 将ROS图像消息转换为OpenCV格式
    img_bgr = imgmsg_to_cv2(image_msg)
    # 从参数服务器获取im_flag的值
    im_flag = rospy.get_param('/top_view_shot_node/im_flag', 255)
    
    if im_flag == 1:
        # 保存图像
        rospy.loginfo('保存至temp/vl_now.jpg')
        cv2.imwrite('/home/abot/abot_ws/src/abot_vlm/temp/vl_now.jpg', img_bgr)
        # 将im_flag重置为255
        rospy.set_param('/top_view_shot_node/im_flag', 255)
        # # 屏幕上展示图像
        # cv2.imshow('vlm', img_bgr)
        cv2.waitKey(1)

        # 调用豆包视觉大模型API
        result_str = doubao_vision_api()
        
        # 提取结果中的数字部分
        rospy.loginfo(f"结果: {result_str}")
    
        # 创建发布者
        pub = rospy.Publisher('vision_result', String, queue_size=10)
    
        # 发布结果五次
        for _ in range(1):
            pub.publish(result_str)
            rospy.sleep(0.1)  # 等待一小段时间，确保消息能够被接收

def main():
    global im_flag
    rospy.init_node('top_view_shot_node', anonymous=True)
    rospy.Subscriber('/usb_cam/image_raw', ROSImage, top_view_shot)
    rospy.loginfo('视觉大模型模块导入成功！')
    rospy.loginfo('准备识别...')
    # 从参数服务器获取im_flag的值
    im_flag = rospy.get_param('/top_view_shot_node/im_flag', 255)
    
    # # 参考这种赋值方式哈，注意加入命名空间路径
    # rospy.set_param('/top_view_shot_node/im_flag', 1)
    
    rospy.spin()

if __name__ == '__main__':
    main()

