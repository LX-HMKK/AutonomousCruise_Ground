#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 ASR 节点：录音 → 豆包语音识别 → 检测到"开始比赛" → 发布 /start。

豆包 ASR 使用火山引擎语音识别大模型极速版 HTTP API。
认证: X-Api-App-Key + X-Api-Access-Key。
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
import base64
import uuid as _uuid
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'abot_vlm', 'scripts'))
from API_KEY_DOUBAO import SPEECH_APPID, SPEECH_TOKEN, SPEECH_ASR_RESOURCE_ID

# ---- ASR 配置 ----
ASR_API_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
ASR_RESOURCE_ID = "volc.bigasr.auc_turbo"

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
        rospy.loginfo('[DoubaoASR] Ready. instance=%s api_resource=%s appid=%s',
                      self.resource_id, ASR_RESOURCE_ID, self.appid)

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
                    # 状态机 _on_wakeup 在非仿真模式只认 data=='True'
                    self.start_pub.publish(String(data='True'))
                    rospy.set_param('/start', True)
                    break
                elif result:
                    rospy.loginfo('[DoubaoASR] Heard: %s', result[:60])
            except Exception as e:
                rospy.logwarn('[DoubaoASR] %s', e)
            rate.sleep()

    def _recognize(self, audio_path):
        """调用豆包语音识别大模型极速版 HTTP API。"""
        if not self.token:
            rospy.logerr('[DoubaoASR] API key not set')
            return None
        try:
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            headers = {
                'X-Api-App-Key': self.appid,
                'X-Api-Access-Key': self.token,
                'X-Api-Resource-Id': ASR_RESOURCE_ID,
                'X-Api-Request-Id': str(_uuid.uuid4()),
                'X-Api-Sequence': '-1',
                'Content-Type': 'application/json',
            }
            body = {
                'user': {'uid': 'abot_robot'},
                'audio': {
                    'format': 'wav',
                    'data': base64.b64encode(audio_data).decode('utf-8'),
                },
                'request': {
                    'model_name': 'bigmodel',
                    'enable_itn': True,
                    'enable_punc': True,
                },
            }
            resp = requests.post(ASR_API_URL, headers=headers, json=body, timeout=10)
            status_code = resp.headers.get('X-Api-Status-Code', '')
            message = resp.headers.get('X-Api-Message', '')
            logid = resp.headers.get('X-Tt-Logid', '')
            if status_code != '20000000':
                rospy.logwarn('[DoubaoASR] ASR failed: http=%d code=%s msg=%s logid=%s',
                              resp.status_code, status_code, message, logid)
                return None

            data = resp.json()
            result = data.get('result', {})
            if isinstance(result, dict):
                return result.get('text', '').strip()
            if isinstance(result, list) and result:
                return result[0].get('text', '').strip()
            return data.get('text', '').strip()
        except Exception as e:
            rospy.logerr('[DoubaoASR] Recognition failed: %s', e)
            return None


if __name__ == '__main__':
    rospy.init_node('doubao_asr')
    DoubaoASR().run()
