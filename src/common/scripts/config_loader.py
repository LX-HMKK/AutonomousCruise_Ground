#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置加载工具：从 config/ YAML 文件加载比赛参数。"""
import os
import yaml
import rospy

CONFIG_SEARCH_PATHS = [
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config'),
    '/home/abot/abot_ws/src/config',
    os.path.expanduser('~/abot_ws/src/config'),
]


def _find_config_dir():
    for path in CONFIG_SEARCH_PATHS:
        abs_path = os.path.abspath(path)
        if os.path.isdir(abs_path):
            return abs_path
    raise IOError('Cannot find config directory. Searched: {}'.format(CONFIG_SEARCH_PATHS))


def load_config(filename):
    """加载一个 YAML 配置文件，返回 dict。"""
    config_dir = _find_config_dir()
    filepath = os.path.join(config_dir, filename)
    if not os.path.isfile(filepath):
        raise IOError('Config file not found: {}'.format(filepath))
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
    rospy.loginfo('[config_loader] Loaded: %s', filepath)
    return data


def load_all_configs():
    """加载全部 6 个配置文件，返回合并后的 dict。"""
    files = [
        'competition_field.yaml',
        'mission.yaml',
        'robot.yaml',
        'navigation.yaml',
        'perception.yaml',
        'voice_text.yaml',
    ]
    configs = {}
    for f in files:
        configs[f.replace('.yaml', '')] = load_config(f)
    return configs


def get_cell_center_xy(cell_number, field_config):
    """
    将网格编号 (1-81) 转换为 map 坐标系的 (x, y) 中心点。
    网格 1 在左上角，9 在右上角。
    map 坐标系原点在场地中心，x 轴向东，y 轴向北。
    """
    gc = field_config['cell_index_convention']
    rows = field_config['field']['grid_rows']
    cols = field_config['field']['grid_cols']
    cell_size = field_config['field']['cell_size_m']

    n = cell_number - 1
    row = n // cols  # 0 为最北
    col = n % cols   # 0 为最西

    x = (col - cols / 2.0) * cell_size + cell_size / 2.0
    y = (rows / 2.0 - row) * cell_size - cell_size / 2.0
    return x, y
