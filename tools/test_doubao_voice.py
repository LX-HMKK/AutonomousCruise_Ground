#!/usr/bin/env python3
"""WSL 环境下测试豆包 ASR/TTS API 连通性。"""

import os
import sys
import requests
import json
import wave
import struct
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'abot_vlm', 'scripts'))
from API_KEY_DOUBAO import DOUBAO_KEY

API_KEY = DOUBAO_KEY
AUTH_HEADER = 'Bearer; ' + API_KEY  # 火山引擎要求分号

# ---- TTS 测试 ----
TTS_RESOURCE_ID = "volc.tts_async.default"
TTS_SUBMIT_URL = "https://openspeech.bytedance.com/api/v1/tts_async/submit"
TTS_QUERY_URL = "https://openspeech.bytedance.com/api/v1/tts_async/query"
TTS_APPID = "594a7b46"

# ---- ASR 测试 ----
ASR_RESOURCE_ID = "volc.seedasr.auc"
ASR_URL = "https://openspeech.bytedance.com/api/v1/asr"


def test_tts():
    """测试豆包 TTS API。"""
    print("\n=== 测试 TTS 语音合成 ===")
    headers = {
        'Authorization': AUTH_HEADER,
        'Resource-Id': TTS_RESOURCE_ID,
        'Content-Type': 'application/json',
    }
    body = {
        'appid': TTS_APPID,
        'text': '比赛开始',
        'speaker': 'zh_female_qingxin',
        'audio_params': {'format': 'mp3', 'sample_rate': 16000},
    }
    print(f"  URL: {TTS_SUBMIT_URL}")
    print(f"  Auth: Bearer; {API_KEY[:20]}...")
    print(f"  Resource-Id: {TTS_RESOURCE_ID}")
    print(f"  Text: {body['text']}")

    try:
        resp = requests.post(TTS_SUBMIT_URL, headers=headers, json=body, timeout=10)
        print(f"  Status: {resp.status_code}")
        print(f"  Body: {resp.text[:300]}")
        if resp.status_code == 200:
            data = resp.json()
            task_id = data.get('task_id', '')
            print(f"  task_id: {task_id}")
            if task_id:
                import time
                for i in range(30):
                    time.sleep(0.3)
                    qresp = requests.get(TTS_QUERY_URL, headers=headers,
                                         params={'appid': TTS_APPID, 'task_id': task_id}, timeout=5)
                    if qresp.status_code == 200:
                        qdata = qresp.json()
                        status = qdata.get('status', '')
                        print(f"  Poll {i}: status={status}")
                        if status == 'success':
                            audio_url = qdata.get('audio_url', '')
                            print(f"  audio_url: {audio_url[:80]}...")
                            print("  ✅ TTS 测试通过!")
                            return True
                    if i > 5:
                        break
        else:
            print(f"  ❌ TTS HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ TTS Exception: {e}")
    return False


def test_asr():
    """测试豆包 ASR API (用简单正弦波模拟语音)。"""
    print("\n=== 测试 ASR 语音识别 ===")

    # 生成一个简单的 WAV 文件 (1kHz 正弦波, 3秒, 模拟语音)
    wav_path = '/tmp/test_asr.wav'
    sample_rate = 16000
    duration = 3
    num_samples = sample_rate * duration
    with wave.open(wav_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            value = int(16000 * math.sin(2 * math.pi * 1000 * i / sample_rate))
            wf.writeframes(struct.pack('<h', value))

    print(f"  WAV: {wav_path} ({duration}s, {sample_rate}Hz)")

    headers = {
        'Authorization': AUTH_HEADER,
        'Resource-Id': ASR_RESOURCE_ID,
        'Content-Type': 'audio/wav; codec=pcm; rate=%d' % sample_rate,
    }
    print(f"  URL: {ASR_URL}")
    print(f"  Resource-Id: {ASR_RESOURCE_ID}")

    try:
        with open(wav_path, 'rb') as f:
            audio_data = f.read()
        resp = requests.post(ASR_URL, headers=headers, data=audio_data, timeout=10)
        print(f"  Status: {resp.status_code}")
        print(f"  Body: {resp.text[:300]}")
        if resp.status_code == 200:
            print("  ✅ ASR API 可达 (但正弦波无有效文字属于正常)")
            return True
        else:
            print(f"  ❌ ASR HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ ASR Exception: {e}")
    finally:
        os.unlink(wav_path)
    return False


if __name__ == '__main__':
    print("豆包语音 API 连通性测试")
    print("API Key:", API_KEY[:20] + "..." if API_KEY else "NOT SET")

    tts_ok = test_tts()
    asr_ok = test_asr()

    print(f"\n结果: TTS={'✅' if tts_ok else '❌'}  ASR={'✅' if asr_ok else '❌'}")
