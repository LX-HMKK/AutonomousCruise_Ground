#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豆包 TTS 节点：订阅 /voiceWords，调用豆包语音合成 HTTP API，mplayer 播放。

认证: Bearer Token (分号分隔), 资源 ID: volc.tts_async.default
输出 /tts_done 通知状态机播报完成。
"""

import rospy
import os
import sys
import tempfile
import requests
from std_msgs.msg import String

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'abot_vlm', 'scripts'))
from API_KEY_DOUBAO import SPEECH_APPID, SPEECH_TOKEN

# ---- TTS 配置 ----
TTS_RESOURCE_ID = "volc.tts_async.default"  # 豆包语音合成 (长文本)
TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts_async/submit"
TTS_QUERY_URL = "https://openspeech.bytedance.com/api/v1/tts_async/query"


class DoubaoTTS(object):
    """豆包语音合成 + mplayer 播放。"""

    def __init__(self):
        self.tts_done_pub = rospy.Publisher('/tts_done', String, queue_size=10)
        rospy.Subscriber('/voiceWords', String, self._on_voice)
        self.appid = SPEECH_APPID
        self.token = SPEECH_TOKEN
        rospy.loginfo('[DoubaoTTS] Ready. resource=%s', TTS_RESOURCE_ID)

    def _on_voice(self, msg):
        text = msg.data.strip()
        if not text:
            return
        rospy.loginfo('[DoubaoTTS] Speaking: %s', text[:50])

        if self.token:
            try:
                self._speak_async(text)
            except Exception as e:
                rospy.logerr('[DoubaoTTS] TTS failed: %s', e)
        else:
            os.system('espeak -v zh "%s" 2>/dev/null' % text)

        self.tts_done_pub.publish(String(data='done'))
        rospy.loginfo('[DoubaoTTS] Done: %s', text[:30])

    def _speak_async(self, text):
        """提交异步 TTS 任务 → 轮询 → 下载 → mplayer 播放。"""
        import uuid as _uuid
        headers = {
            'Authorization': 'Bearer; ' + self.token,
            'Resource-Id': TTS_RESOURCE_ID,
            'Content-Type': 'application/json',
        }
        body = {
            'appid': self.appid,
            'reqid': str(_uuid.uuid4()),
            'text': text,
            'format': 'mp3',
            'voice_type': 'BV701_streaming',
            'sample_rate': 24000,
        }
        resp = requests.post(TTS_API_URL, headers=headers, json=body, timeout=10)
        if resp.status_code != 200:
            rospy.logerr('[DoubaoTTS] Submit failed: %d %s', resp.status_code, resp.text[:200])
            return
        data = resp.json()
        task_id = data.get('task_id', '')

        # 轮询等待合成完成
        import time
        for _ in range(30):
            time.sleep(0.3)
            qresp = requests.get(TTS_QUERY_URL,
                                 headers=headers,
                                 params={'appid': self.appid, 'task_id': task_id},
                                 timeout=5)
            if qresp.status_code == 200:
                qdata = qresp.json()
                if qdata.get('status') == 'success':
                    audio_url = qdata.get('audio_url', '')
                    if audio_url:
                        self._download_and_play(audio_url)
                    return

        rospy.logwarn('[DoubaoTTS] TTS timeout for task %s', task_id)

    def _download_and_play(self, url):
        """下载音频文件并用 mplayer 播放。"""
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            tmp_path = f.name
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open(tmp_path, 'wb') as f:
                f.write(r.content)
            os.system('mplayer -really-quiet %s 2>/dev/null' % tmp_path)
        os.unlink(tmp_path)


if __name__ == '__main__':
    rospy.init_node('doubao_tts')
    DoubaoTTS()
    rospy.spin()
