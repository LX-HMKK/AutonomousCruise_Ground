#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 TTS 节点：订阅 /voiceWords，调用豆包语音合成 API，mplayer 播放。

实车使用，替代仿真 mock_tts.py。
"""
import rospy
import os
import sys
import time
import tempfile
from std_msgs.msg import String

# 添加 abot_vlm 路径以导入 API key
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'abot_vlm', 'scripts'))
from API_KEY_DOUBAO import DOUBAO_KEY

try:
    from volcenginesdkarkruntime import Ark
    HAS_ARK = True
except ImportError:
    HAS_ARK = False
    rospy.logwarn('[DoubaoTTS] volcenginesdkarkruntime not installed, TTS disabled')


class DoubaoTTS(object):
    """豆包语音合成 + mplayer 播放。"""

    def __init__(self):
        self.tts_done_pub = rospy.Publisher('/tts_done', String, queue_size=10)
        rospy.Subscriber('/voiceWords', String, self._on_voice)
        if HAS_ARK and DOUBAO_KEY:
            self.client = Ark(
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=DOUBAO_KEY)
        else:
            self.client = None
        rospy.loginfo('[DoubaoTTS] Ready. HAS_ARK=%s KEY=%s',
                      HAS_ARK, bool(DOUBAO_KEY))

    def _on_voice(self, msg):
        text = msg.data.strip()
        if not text:
            return
        rospy.loginfo('[DoubaoTTS] Speaking: %s', text[:50])

        if self.client is not None:
            try:
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                    tmp_path = f.name
                response = self.client.audio.speech.create(
                    model="doubao-seed-tts-1.0",
                    input=text,
                    voice="zh_female_qingxin",
                    response_format="mp3",
                )
                response.stream_to_file(tmp_path)
                os.system('mplayer -really-quiet %s 2>/dev/null' % tmp_path)
                os.unlink(tmp_path)
            except Exception as e:
                rospy.logerr('[DoubaoTTS] TTS failed: %s', e)
        else:
            # fallback: 用 espeak 念出来
            os.system('espeak -v zh "%s" 2>/dev/null' % text)

        # 通知状态机播报完成
        self.tts_done_pub.publish(String(data='done'))
        rospy.loginfo('[DoubaoTTS] Done: %s', text[:30])


if __name__ == '__main__':
    rospy.init_node('doubao_tts')
    DoubaoTTS()
    rospy.spin()
