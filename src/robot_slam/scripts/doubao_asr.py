#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 ASR 节点：录音 → 豆包语音识别 → 检测到"开始比赛" → 发布 /start。

豆包 ASR 使用火山引擎语音服务 (非方舟 Ark SDK)，模型 ID: volc.seedasr.auc。
认证: Bearer Token (Ark API Key 通用)。
"""

import rospy
import os
import sys
import time
import json
import tempfile
import pyaudio
import wave
import requests
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'abot_vlm', 'scripts'))
from API_KEY_DOUBAO import SPEECH_APPID, SPEECH_TOKEN, SPEECH_ASR_RESOURCE_ID

# ---- ASR 配置 ----
ASR_API_URL = "https://openspeech.bytedance.com/api/v1/asr"

# ---- 录音参数 ----
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024
RECORD_SECONDS = 4
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
        self.appid = SPEECH_APPID
        self.token = SPEECH_TOKEN
        self.resource_id = SPEECH_ASR_RESOURCE_ID
        rospy.loginfo('[DoubaoASR] Ready. resource=%s appid=%s',
                      self.resource_id, self.appid)

    def run(self):
        rate = rospy.Rate(0.5)
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
        """调用豆包语音识别 HTTP API。"""
        if not self.token:
            rospy.logerr('[DoubaoASR] API key not set')
            return None
        try:
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            headers = {
                'Authorization': 'Bearer; ' + self.token,
                'Resource-Id': self.resource_id,
                'Content-Type': 'application/json',
            }
            import base64, uuid as _uuid
            body = {
                'appid': self.appid,
                'reqid': str(_uuid.uuid4()),
                'audio': base64.b64encode(audio_data).decode('utf-8'),
                'audio_format': 'wav',
                'sample_rate': SAMPLE_RATE,
            }
            resp = requests.post(ASR_API_URL, headers=headers, json=body, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # 火山引擎 ASR 返回格式: {"result": [{"text": "..."}]}
                if 'result' in data and data['result']:
                    return data['result'][0].get('text', '').strip()
                elif 'text' in data:
                    return data['text'].strip()
                return str(data)
            else:
                rospy.logwarn('[DoubaoASR] HTTP %d: %s', resp.status_code, resp.text[:200])
                return None
        except Exception as e:
            rospy.logerr('[DoubaoASR] Recognition failed: %s', e)
            return None


if __name__ == '__main__':
    rospy.init_node('doubao_asr')
    DoubaoASR().run()
