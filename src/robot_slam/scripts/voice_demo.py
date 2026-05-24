#!/usr/bin/env python
# -*- coding: utf-8 -*-
import rospy
import os
#指定的音乐路径
music_path = "/home/abot/01.mp3"
#使用播放器播放
os.system('mplayer %s' % music_path)
