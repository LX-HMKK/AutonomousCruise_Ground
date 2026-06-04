#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 TTS 节点：订阅 /voiceWords，调用豆包语音合成 V1 HTTP API，mplayer 播放。

认证: Bearer;token (分号分隔，无空格)。
API: https://openspeech.bytedance.com/api/v1/tts (V1 非流式)
输出 /tts_done 通知播报完成。
"""

import rospy
import os
import sys
import base64
import tempfile
import requests
import uuid as _uuid
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'abot_vlm', 'scripts'))
from API_KEY_DOUBAO import SPEECH_APPID, SPEECH_TOKEN

# ---- TTS 配置 ----
TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"
# 已确认可用的音色
TTS_VOICE_TYPE = "zh_male_M392_conversation_wvae_bigtts"


class DoubaoTTS(object):
    """豆包语音合成 + mplayer 播放。"""

    def __init__(self):
        self.tts_done_pub = rospy.Publisher('/tts_done', String, queue_size=10)
        rospy.Subscriber('/voiceWords', String, self._on_voice)
        self.appid = SPEECH_APPID
        self.token = SPEECH_TOKEN
        rospy.loginfo('[DoubaoTTS] Ready. voice=%s', TTS_VOICE_TYPE)

    def _on_voice(self, msg):
        text = msg.data.strip()
        if not text:
            return
        rospy.loginfo('[DoubaoTTS] Speaking: %s', text[:50])

        if self.token:
            try:
                self._speak(text)
            except Exception as e:
                rospy.logerr('[DoubaoTTS] TTS failed: %s', e)
        else:
            os.system('espeak -v zh "%s" 2>/dev/null' % text)

        self.tts_done_pub.publish(String(data=text))
        rospy.loginfo('[DoubaoTTS] Done: %s', text[:30])

    def _speak(self, text):
        """调用豆包 TTS V1 HTTP API，直接返回 base64 编码的 MP3 音频。"""
        headers = {
            'Authorization': 'Bearer;' + self.token,
            'Content-Type': 'application/json',
        }
        body = {
            'app': {
                'appid': self.appid,
                'token': 'access_token',  # doc: 无实际鉴权作用的 Fake token
                'cluster': 'volcano_tts',
            },
            'user': {
                'uid': 'abot_robot',
            },
            'audio': {
                'voice_type': TTS_VOICE_TYPE,
                'encoding': 'mp3',
                'speed_ratio': 1.0,
            },
            'request': {
                'reqid': str(_uuid.uuid4()),
                'text': text,
                'operation': 'query',
            },
        }
        resp = requests.post(TTS_API_URL, headers=headers, json=body, timeout=10)
        if resp.status_code != 200:
            rospy.logerr('[DoubaoTTS] HTTP %d: %s', resp.status_code, resp.text[:200])
            return

        data = resp.json()
        if data.get('code') != 3000:
            rospy.logerr('[DoubaoTTS] API error code=%d: %s',
                         data.get('code'), data.get('message', ''))
            return

        audio_b64 = data.get('data', '')
        if not audio_b64:
            rospy.logerr('[DoubaoTTS] No audio data in response')
            return

        mp3 = base64.b64decode(audio_b64)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmp_path = f.name
        with open(tmp_path, 'wb') as f:
            f.write(mp3)

        duration_ms = data.get('addition', {}).get('duration', '?')
        rospy.loginfo('[DoubaoTTS] Synthesized %d bytes, %sms', len(mp3), duration_ms)

        os.system('mplayer -really-quiet %s 2>/dev/null' % tmp_path)
        os.unlink(tmp_path)


if __name__ == '__main__':
    rospy.init_node('doubao_tts')
    DoubaoTTS()
    rospy.spin()
