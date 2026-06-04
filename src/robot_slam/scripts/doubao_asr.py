#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 ASR 节点：录音 → 豆包语音识别 → 检测到"开始比赛" → 发布 /start。

替代 Snowboy 唤醒词方案，满足比赛"语音输出'开始比赛'指令"要求。
"""
import rospy
import os
import sys
import time
import tempfile
import pyaudio
import wave
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'abot_vlm', 'scripts'))
from API_KEY_DOUBAO import DOUBAO_KEY

try:
    from volcenginesdkarkruntime import Ark
    HAS_ARK = True
except ImportError:
    HAS_ARK = False

# 录音参数
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024
RECORD_SECONDS = 4          # 每次录音时长
FORMAT = pyaudio.paInt16


def record_audio(filename, duration=RECORD_SECONDS):
    """PyAudio 录音，保存为 WAV。"""
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE,
                    input=True, frames_per_buffer=CHUNK)
    frames = []
    for _ in range(int(SAMPLE_RATE / CHUNK * duration)):
        frames.append(stream.read(CHUNK, exception_on_overflow=False))
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(b''.join(frames))
    wf.close()


class DoubaoASR(object):
    """豆包语音识别，检测比赛开始指令。"""

    def __init__(self):
        self.start_pub = rospy.Publisher('/start', String, queue_size=10)
        if HAS_ARK and DOUBAO_KEY:
            self.client = Ark(
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=DOUBAO_KEY)
        else:
            self.client = None
        rospy.loginfo('[DoubaoASR] Ready. Waiting for "开始比赛"...')

    def run(self):
        rate = rospy.Rate(0.5)  # 每 2 秒检查一次
        while not rospy.is_shutdown():
            if rospy.get_param('/start', False):
                rospy.loginfo('[DoubaoASR] /start already set, exiting')
                break

            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    tmp_path = f.name
                record_audio(tmp_path, duration=3)
                result = self._recognize(tmp_path)
                os.unlink(tmp_path)

                if result and '开始比赛' in result:
                    rospy.loginfo('[DoubaoASR] "开始比赛" detected! → /start')
                    self.start_pub.publish(String(data='wakeup'))
                    rospy.set_param('/start', True)
                    break
                elif result:
                    rospy.loginfo('[DoubaoASR] Heard: %s', result[:60])
            except Exception as e:
                rospy.logwarn('[DoubaoASR] %s', e)
            rate.sleep()

    def _recognize(self, audio_path):
        if self.client is None:
            return None
        try:
            with open(audio_path, 'rb') as f:
                # 豆包语音识别模型: 火山引擎 Ark STT 模型
                # 具体模型名以火山引擎控制台为准, 备选: doubao-pro-32k-stt / doubao-lite-stt
                response = self.client.audio.transcriptions.create(
                    model="doubao-pro-32k-stt",
                    file=f,
                    language="zh",
                )
            return response.text.strip()
        except Exception as e:
            rospy.logerr('[DoubaoASR] Recognition failed: %s', e)
            return None


if __name__ == '__main__':
    rospy.init_node('doubao_asr')
    DoubaoASR().run()
