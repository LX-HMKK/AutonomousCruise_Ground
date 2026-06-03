#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""地图可视化标点工具：直接在 PGM 图片上点击标注，自动换算 map 坐标。

用法 (Windows 端直接运行):
  python tools/mark_map_gui.py
  python tools/mark_map_gui.py -m game
  python tools/mark_map_gui.py -m game -o my_points.yaml

操作:
  左键点击  = 添加点
  右键点击  = 删除最近点
  输入名称  = 为最新点命名（底部输入框）
  Save 按钮  = 保存 YAML
  ESC 键     = 退出

依赖: pip install pillow pyyaml (无 matplotlib 依赖)
"""

import os
import sys
import argparse
import yaml
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

try:
    from PIL import Image, ImageTk
except ImportError:
    print('Missing dependency: pillow')
    print('Install: pip install pillow pyyaml')
    sys.exit(1)


class MapMarker(tk.Tk):
    """在地图 PGM 上交互式标点。"""

    def __init__(self, map_name='game', output_file=None):
        super().__init__()

        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_dir = os.path.join(repo_dir, 'src', 'robot_slam', 'maps')

        # 加载 YAML 元数据
        yaml_path = os.path.join(maps_dir, map_name + '.yaml')
        if not os.path.isfile(yaml_path):
            raise IOError('Map YAML not found: %s' % yaml_path)
        with open(yaml_path, 'r') as f:
            self.meta = yaml.safe_load(f)

        pgm_basename = self.meta.get('image', map_name + '.pgm')
        if not os.path.isabs(pgm_basename):
            pgm_path = os.path.join(maps_dir, pgm_basename)
        else:
            pgm_path = pgm_basename
        if not os.path.isfile(pgm_path):
            raise IOError('Map PGM not found: %s' % pgm_path)

        self.resolution = float(self.meta['resolution'])
        self.origin_x = float(self.meta['origin'][0])
        self.origin_y = float(self.meta['origin'][1])
        self.map_name = map_name

        if output_file is None:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = 'marked_%s_%s.yaml' % (map_name, ts)
        self.output_file = os.path.join(maps_dir, output_file)

        # 加载图片
        self.pil_img_orig = Image.open(pgm_path)
        self.img_w, self.img_h = self.pil_img_orig.size

        # 缩放显示（最大 1400x900）
        max_w, max_h = 1400, 900
        scale = min(max_w / self.img_w, max_h / self.img_h, 1.0)
        self.display_w = int(self.img_w * scale)
        self.display_h = int(self.img_h * scale)
        self.scale = scale

        self.pil_img = self.pil_img_orig.resize((self.display_w, self.display_h), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(self.pil_img)

        # 数据
        self.points = []  # [(display_x, display_y, map_x, map_y, name), ...]
        self.counter = 0
        self.dot_radius = 4

        # ---- UI 布局 ----
        self.title('Map Marker: %s  (%.3f m/px | %dx%d px | origin [%.2f, %.2f])' % (
            map_name, self.resolution, self.img_w, self.img_h,
            self.origin_x, self.origin_y))

        # 工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(toolbar, text='名称:').pack(side=tk.LEFT, padx=(0, 3))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(toolbar, textvariable=self.name_var, width=15)
        self.name_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.name_entry.bind('<Return>', lambda e: self._rename_last())

        ttk.Button(toolbar, text='重命名最新点', command=self._rename_last).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text='撤销 (Undo)', command=self._undo).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text='清空全部', command=self._clear).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text='保存 YAML', command=self._save).pack(side=tk.LEFT, padx=3)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(toolbar, text='点列表', command=self._show_list).pack(side=tk.LEFT, padx=3)

        # 状态栏
        self.status_var = tk.StringVar(value='就绪 — 左键点击地图添加点 | 右键撤销 | S=保存')
        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status.pack(side=tk.BOTTOM, fill=tk.X)

        # 画布
        self.canvas = tk.Canvas(self, width=self.display_w, height=self.display_h,
                                 cursor='crosshair', bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)

        # 点标记图层
        self.dot_items = []   # canvas oval ids
        self.label_items = []  # canvas text ids

        # 事件绑定
        self.canvas.bind('<Button-1>', self._on_left_click)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self.canvas.bind('<Motion>', self._on_mouse_move)
        self.bind('<KeyPress-s>', lambda e: self._save())
        self.bind('<KeyPress-S>', lambda e: self._save())
        self.bind('<Control-z>', lambda e: self._undo())
        self.bind('<Escape>', lambda e: self.destroy())
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        # 提示
        print('')
        print('=' * 60)
        print('  地图标点工具 — %s' % map_name)
        print('  分辨率: %.4f m/px | 图片: %d×%d px' % (self.resolution, self.img_w, self.img_h))
        print('  地图范围: x=[%.2f, %.2f]  y=[%.2f, %.2f]' % (
            self.origin_x, self.origin_x + self.img_w * self.resolution,
            self.origin_y, self.origin_y + self.img_h * self.resolution))
        print('')
        print('  左键=添加点  右键=撤销  S=保存  ESC=退出')
        print('=' * 60)

    # ---- 坐标换算 ----
    def _display_to_map(self, dx, dy):
        """显示坐标 -> map 坐标"""
        px = dx / self.scale
        py = dy / self.scale
        mx = px * self.resolution + self.origin_x
        my = (self.img_h - py) * self.resolution + self.origin_y
        return round(mx, 4), round(my, 4)

    def _map_to_display(self, mx, my):
        """map 坐标 -> 显示坐标"""
        px = (mx - self.origin_x) / self.resolution
        py = self.img_h - (my - self.origin_y) / self.resolution
        return px * self.scale, py * self.scale

    # ---- 事件处理 ----
    def _on_left_click(self, event):
        self.counter += 1
        dx, dy = event.x, event.y
        mx, my = self._display_to_map(dx, dy)
        name = 'P%d' % self.counter
        self.points.append((dx, dy, mx, my, name))
        self._draw_point(dx, dy, name=name)
        self.status_var.set('添加 %s: display=(%d,%d) map=(%.4f, %.4f)' % (name, dx, dy, mx, my))
        print('[+] %s: map=(%.4f, %.4f)  display=(%d, %d)' % (name, mx, my, dx, dy))

    def _on_right_click(self, event):
        self._undo()

    def _on_mouse_move(self, event):
        dx, dy = event.x, event.y
        mx, my = self._display_to_map(dx, dy)
        self.status_var.set('光标: display=(%d,%d) map=(%.4f, %.4f) | 已标 %d 个点 | 左键添加 右键撤销 S保存'
                            % (dx, dy, mx, my, len(self.points)))

    def _on_close(self):
        if self.points:
            if messagebox.askyesno('保存', '退出前保存 %d 个点到 YAML？' % len(self.points)):
                self._save()
        self.destroy()

    # ---- 点操作 ----
    def _draw_point(self, dx, dy, name=None):
        r = self.dot_radius
        oval = self.canvas.create_oval(dx - r, dy - r, dx + r, dy + r,
                                        fill='red', outline='yellow', width=1)
        self.dot_items.append(oval)
        # 编号标签
        label_text = name if name else str(len(self.points))
        txt = self.canvas.create_text(dx + r + 3, dy - r - 3, text=label_text,
                                       anchor=tk.NW, fill='yellow',
                                       font=('Consolas', 9, 'bold'))
        self.label_items.append(txt)

    def _redraw_all(self):
        for o in self.dot_items:
            self.canvas.delete(o)
        for t in self.label_items:
            self.canvas.delete(t)
        self.dot_items = []
        self.label_items = []
        for dx, dy, mx, my, name in self.points:
            self._draw_point(dx, dy, name=name)

    def _rename_last(self):
        new_name = self.name_var.get().strip()
        if not new_name:
            self.status_var.set('请先在名称框输入新名字')
            return
        if not self.points:
            self.status_var.set('没有点可重命名')
            return
        dx, dy, mx, my, _ = self.points[-1]
        self.points[-1] = (dx, dy, mx, my, new_name)
        self._redraw_all()
        self.name_var.set('')
        self.status_var.set('已重命名为 "%s"' % new_name)
        print('[*] Renamed last point -> "%s"' % new_name)

    def _undo(self):
        if self.points:
            removed = self.points.pop()
            if self.dot_items:
                self.canvas.delete(self.dot_items.pop())
            if self.label_items:
                self.canvas.delete(self.label_items.pop())
            self.status_var.set('撤销 %s (剩余 %d 个点)' % (removed[4], len(self.points)))
            print('[-] Removed %s (map=%.4f, %.4f), %d remaining' % (removed[4], removed[2], removed[3], len(self.points)))
        else:
            self.status_var.set('没有点可撤销')

    def _clear(self):
        if self.points and messagebox.askyesno('确认', '清空全部 %d 个点？' % len(self.points)):
            self.points = []
            for o in self.dot_items:
                self.canvas.delete(o)
            for t in self.label_items:
                self.canvas.delete(t)
            self.dot_items = []
            self.label_items = []
            self.counter = 0
            self.status_var.set('已清空')

    def _save(self):
        if not self.points:
            self.status_var.set('没有点可保存!')
            return

        data = {
            'description': 'Points marked on %s map using mark_map_gui.py' % self.map_name,
            'timestamp': datetime.now().isoformat(),
            'map': self.map_name,
            'resolution': self.resolution,
            'origin': [self.origin_x, self.origin_y, self.meta['origin'][2] if len(self.meta['origin']) > 2 else 0.0],
            'count': len(self.points),
            'points': [],
        }
        for dx, dy, mx, my, name in self.points:
            data['points'].append({
                'name': name,
                'x': mx,
                'y': my,
                'z': 0.0,
            })

        # 同时保存 YAML 和 JSON
        yaml_path = self.output_file
        json_path = yaml_path.replace('.yaml', '.json').replace('.yml', '.json')

        with open(yaml_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.status_var.set('已保存 %d 个点 -> %s' % (len(self.points), yaml_path))
        print('')
        print('=' * 60)
        print('  Saved: %s' % yaml_path)
        print('         %s' % json_path)
        print('  Copy-ready:')
        for p in data['points']:
            print('    %s: [%.4f, %.4f, 0.0]' % (p['name'], p['x'], p['y']))
        print('=' * 60)

    def _show_list(self):
        """弹窗显示所有点列表。"""
        if not self.points:
            messagebox.showinfo('点列表', '还没有标记任何点')
            return

        win = tk.Toplevel(self)
        win.title('已标记的点 (%d)' % len(self.points))
        win.geometry('500x350')

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(frame, text='序号  | 名称        | map_x      | map_y      | z').pack(anchor=tk.W, pady=2)

        text = tk.Text(frame, font=('Consolas', 10), wrap=tk.NONE)
        text.pack(fill=tk.BOTH, expand=True)

        for i, (dx, dy, mx, my, name) in enumerate(self.points):
            text.insert(tk.END, '%-4d  %-12s  %10.4f  %10.4f  0.0\n' % (i + 1, name, mx, my))

        text.config(state=tk.DISABLED)

        def _copy():
            lines = []
            for dx, dy, mx, my, name in self.points:
                lines.append('%s: [%.4f, %.4f, 0.0]' % (name, mx, my))
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            self.status_var.set('已复制到剪贴板')

        ttk.Button(win, text='复制到剪贴板', command=_copy).pack(pady=5)


def main():
    parser = argparse.ArgumentParser(description='PGM 地图可视化标点工具')
    parser.add_argument('-m', '--map', default='game', help='地图名 (默认: game)')
    parser.add_argument('-o', '--output', default=None, help='输出 YAML 文件名')
    args = parser.parse_args()

    app = MapMarker(map_name=args.map, output_file=args.output)
    app.mainloop()


if __name__ == '__main__':
    main()
