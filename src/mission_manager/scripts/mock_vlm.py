#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仿真用 Mock VLM 节点。模拟豆包大模型图像识别，返回预设任务序列。

使用方式 (WSL):
  rosrun mission_manager mock_vlm.py _task_sequence:="[41,33,50,31]"

参数:
  task_sequence: 预设的 4 个任务点编号列表 (JSON)
  confidence: 模拟置信度 (默认 0.9)
  trigger_param: 触发参数名 (默认 /top_view_shot_node/im_flag)
"""
import rospy
import json
from std_msgs.msg import String


class MockVLM(object):
    """模拟 VLM 识别节点。"""

    def __init__(self):
        task_seq = rospy.get_param('~task_sequence', '[41, 33, 50, 31]')
        if isinstance(task_seq, str):
            self.task_sequence = json.loads(task_seq)
        else:
            self.task_sequence = task_seq
        self.confidence = rospy.get_param('~confidence', 0.9)
        self.trigger_param = rospy.get_param('~trigger_param',
                                             '/top_view_shot_node/im_flag')

        self.current_index = 0
        self.result_pub = rospy.Publisher('/vision_result', String, queue_size=10)

        rospy.loginfo('[MockVLM] Ready. Task sequence: %s, confidence: %.2f',
                      self.task_sequence, self.confidence)
        rospy.loginfo('[MockVLM] Watching param: %s', self.trigger_param)

    def run(self):
        """主循环：监控触发参数变化。"""
        rate = rospy.Rate(5)  # 5 Hz
        last_flag = 0

        while not rospy.is_shutdown():
            current_flag = rospy.get_param(self.trigger_param, 0)

            if current_flag == 1 and last_flag == 0:
                # 上升沿触发
                self._do_recognition()

            last_flag = current_flag
            rate.sleep()

    def _do_recognition(self):
        """模拟识别流程。"""
        if self.current_index >= len(self.task_sequence):
            rospy.logwarn('[MockVLM] All %d tasks already recognized!',
                          len(self.task_sequence))
            self._publish_result(None, 0, 'no more tasks')
            return

        target_cell = self.task_sequence[self.current_index]
        content = 'mock_task_image_{}'.format(self.current_index + 1)

        rospy.loginfo('[MockVLM] Task %d/%d: recognized cell=%d, confidence=%.2f',
                      self.current_index + 1, len(self.task_sequence),
                      target_cell, self.confidence)

        self._publish_result(target_cell, self.confidence, content)
        self.current_index += 1

        # 重置触发标志
        rospy.set_param(self.trigger_param, 0)

    def _publish_result(self, target_cell, confidence, content):
        """发布 JSON 格式识别结果到 /vision_result。"""
        result = {
            'target_cell': target_cell,
            'content': content,
            'confidence': confidence,
            'image_id': content,
            'timestamp': rospy.Time.now().to_sec(),
        }
        msg = String(data=json.dumps(result))
        self.result_pub.publish(msg)
        rospy.loginfo('[MockVLM] Published: %s', json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    rospy.init_node('mock_vlm')
    mock = MockVLM()
    mock.run()
