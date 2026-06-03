#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""地图可视化标点工具：直接在 PGM 图片上点击标注，自动换算 map 坐标。

用法 (Windows 端直接运行):
  python tools/mark_map_gui.py
  python tools/mark_map_gui.py -m game
  python tools/mark_map_gui.py -m game -o my_points.yaml

操作:
  左键点击        = 添加点
  右键点击        = 删除最近点
  鼠标滚轮        = 缩放 (以光标为中心)
  中键/Shift+左键拖拽 = 平移
  R 键            = 重置视图
  输入名称 + 回车  = 为最新点命名
  S 键            = 保存 YAML
  ESC             = 退出

依赖: pip install pillow pyyaml
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


class ZoomPanCanvas(tk.Canvas):
    """可缩放/平移的 Canvas 封装。"""

    def __init__(self, parent, img_width, img_height, **kwargs):
        super().__init__(parent, **kwargs)
        self.img_w = img_width
        self.img_h = img_height
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        # 拖拽状态
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_pan_x = 0.0
        self._drag_pan_y = 0.0
        self._dragging = False

        # 绑定
        self.bind('<MouseWheel>', self._on_mousewheel)       # Windows
        self.bind('<Button-4>', self._on_mousewheel_up)      # Linux scroll up
        self.bind('<Button-5>', self._on_mousewheel_down)    # Linux scroll down
        self.bind('<Button-2>', self._on_pan_start)           # 中键按下
        self.bind('<B2-Motion>', self._on_pan_move)           # 中键拖拽
        self.bind('<ButtonRelease-2>', self._on_pan_stop)
        self.bind('<Shift-Button-1>', self._on_pan_start)     # Shift+左键
        self.bind('<Shift-B1-Motion>', self._on_pan_move)
        self.bind('<Shift-ButtonRelease-1>', self._on_pan_stop)

    def reset_view(self):
        """重置缩放和平移到初始状态。"""
        cw = self.winfo_width()
        ch = self.winfo_height()
        self.zoom = min(cw / self.img_w, ch / self.img_h, 1.0)
        self.pan_x = (cw - self.img_w * self.zoom) / 2.0
        self.pan_y = (ch - self.img_h * self.zoom) / 2.0

    # ---- 坐标变换 ----
    def canvas_to_img(self, cx, cy):
        """Canvas 坐标 -> 原图像素坐标"""
        px = (cx - self.pan_x) / self.zoom
        py = (cy - self.pan_y) / self.zoom
        return px, py

    def img_to_canvas(self, px, py):
        """原图像素坐标 -> Canvas 坐标"""
        cx = px * self.zoom + self.pan_x
        cy = py * self.zoom + self.pan_y
        return cx, cy

    # ---- 缩放 ----
    def _on_mousewheel(self, event):
        """Windows 鼠标滚轮。"""
        self._zoom_at(event.x, event.y, 1.1 if event.delta > 0 else 0.9)

    def _on_mousewheel_up(self, event):
        self._zoom_at(event.x, event.y, 1.1)

    def _on_mousewheel_down(self, event):
        self._zoom_at(event.x, event.y, 0.9)

    def _zoom_at(self, cx, cy, factor):
        """以画布坐标 (cx, cy) 为中心缩放。"""
        new_zoom = self.zoom * factor
        new_zoom = max(0.1, min(new_zoom, 20.0))  # 限制范围
        factor = new_zoom / self.zoom

        self.pan_x = cx - (cx - self.pan_x) * factor
        self.pan_y = cy - (cy - self.pan_y) * factor
        self.zoom = new_zoom

    # ---- 平移 ----
    def _on_pan_start(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._drag_pan_x = self.pan_x
        self._drag_pan_y = self.pan_y
        self._dragging = True
        self.config(cursor='fleur')

    def _on_pan_move(self, event):
        if not self._dragging:
            return
        self.pan_x = self._drag_pan_x + (event.x - self._drag_start_x)
        self.pan_y = self._drag_pan_y + (event.y - self._drag_start_y)

    def _on_pan_stop(self, event):
        self._dragging = False
        self.config(cursor='crosshair')


class MapMarker(tk.Tk):
    """在地图 PGM 上交互式标点。"""

    def __init__(self, map_name='game', output_file=None):
        super().__init__()

        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_dir = os.path.join(repo_dir, 'src', 'robot_slam', 'maps')

        # 加载 YAML
        yaml_path = os.path.join(maps_dir, map_name + '.yaml')
        if not os.path.isfile(yaml_path):
            raise IOError('Map YAML not found: %s' % yaml_path)
        with open(yaml_path, 'r') as f:
            self.meta = yaml.safe_load(f)

        pgm_basename = self.meta.get('image', map_name + '.pgm')
        pgm_path = os.path.join(maps_dir, pgm_basename if not os.path.isabs(pgm_basename) else '')
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

        # 数据：存储原图像素坐标 + map 坐标
        # points: [(img_px, img_py, map_x, map_y, name), ...]
        self.points = []
        self.counter = 0
        self.dot_radius = 3

        # ---- UI ----
        self.title('Map Marker: %s  (%.3f m/px | %dx%d px | origin [%.2f, %.2f])' % (
            map_name, self.resolution, self.img_w, self.img_h,
            self.origin_x, self.origin_y))
        self.geometry('1400x950')
        self.minsize(800, 600)

        # 工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=4)

        ttk.Label(toolbar, text='名称:').pack(side=tk.LEFT, padx=(0, 3))
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(toolbar, textvariable=self.name_var, width=14)
        self.name_entry.pack(side=tk.LEFT, padx=(0, 4))
        self.name_entry.bind('<Return>', lambda e: self._rename_last())

        ttk.Button(toolbar, text='重命名', command=self._rename_last).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text='撤销', command=self._undo).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text='清空', command=self._clear).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(toolbar, text='保存 YAML', command=self._save).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text='点列表', command=self._show_list).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(toolbar, text='重置视图 (R)', command=self._reset_view).pack(side=tk.LEFT, padx=2)

        zoom_label = ttk.Label(toolbar, text='  滚轮缩放 | Shift+左键平移 | 中键平移')
        zoom_label.pack(side=tk.RIGHT, padx=5)

        # 状态栏
        self.status_var = tk.StringVar(
            value='滚轮=缩放  Shift+拖拽=平移  R=重置  左键=加标点  S=保存')
        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status.pack(side=tk.BOTTOM, fill=tk.X)

        # 可缩放画布
        self.canvas = ZoomPanCanvas(self, self.img_w, self.img_h,
                                     cursor='crosshair', bg='#2b2b2b',
                                     highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 画布初始化后加载图片并重置视图
        self.canvas.bind('<Configure>', self._on_canvas_configure, add='+')
        self._img_loaded = False
        self._load_image()

        # 点图层
        self._dot_ovals = []
        self._dot_labels = []

        # 键盘事件
        self.bind('<KeyPress-s>', lambda e: self._save())
        self.bind('<KeyPress-S>', lambda e: self._save())
        self.bind('<KeyPress-r>', lambda e: self._reset_view())
        self.bind('<KeyPress-R>', lambda e: self._reset_view())
        self.bind('<Control-z>', lambda e: self._undo())
        self.bind('<Escape>', lambda e: self.destroy())

        # 左键/右键点击（画布级）
        self.canvas.bind('<Button-1>', self._on_left_click)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self.canvas.bind('<Motion>', self._on_mouse_move)

        self.protocol('WM_DELETE_WINDOW', self._on_close)

        # 打印信息
        print('')
        print('=' * 60)
        print('  地图标点工具 — %s' % map_name)
        print('  分辨率: %.4f m/px | 图片: %d×%d px' % (self.resolution, self.img_w, self.img_h))
        print('  地图范围: x=[%.2f, %.2f]  y=[%.2f, %.2f]' % (
            self.origin_x, self.origin_x + self.img_w * self.resolution,
            self.origin_y, self.origin_y + self.img_h * self.resolution))
        print('')
        print('  滚轮=缩放  Shift+拖拽=平移  中键拖拽=平移  R=重置视图')
        print('  左键=添加点  右键=撤销  S=保存  ESC=退出')
        print('=' * 60)

    def _load_image(self):
        """渲染原图到 Canvas（作为背景）。"""
        # 用原始图片，通过缩放和平移显示
        self._tk_img = ImageTk.PhotoImage(self.pil_img_orig)
        self._bg_img_id = self.canvas.create_image(0, 0, anchor=tk.NW,
                                                     image=self._tk_img, tags=('bg',))
        self._img_loaded = True

    def _on_canvas_configure(self, event):
        """窗口尺寸变化时重置视图。"""
        if self._img_loaded and event.width > 10 and event.height > 10:
            self.canvas.reset_view()
            self._update_bg_transform()
            self._redraw_points()

    def _update_bg_transform(self):
        """更新背景图片的缩放/平移。"""
        scale_x = self.img_w * self.canvas.zoom
        scale_y = self.img_h * self.canvas.zoom
        self.canvas.coords(self._bg_img_id, self.canvas.pan_x, self.canvas.pan_y)
        self.canvas.itemconfig(self._bg_img_id,
                                image=ImageTk.PhotoImage(
                                    self.pil_img_orig.resize(
                                        (max(1, int(scale_x)), max(1, int(scale_y))),
                                        Image.NEAREST)))

    def _reset_view(self):
        self.canvas.reset_view()
        self._update_bg_transform()
        self._redraw_points()
        self.status_var.set('视图已重置  zoom=%.2fx' % self.canvas.zoom)

    # ---- 坐标换算 ----
    def _img_to_map(self, px, py):
        """原图像素坐标 -> map 坐标"""
        mx = px * self.resolution + self.origin_x
        my = (self.img_h - py) * self.resolution + self.origin_y
        return round(mx, 4), round(my, 4)

    def _map_to_img(self, mx, my):
        """map 坐标 -> 原图像素坐标"""
        px = (mx - self.origin_x) / self.resolution
        py = self.img_h - (my - self.origin_y) / self.resolution
        return px, py

    # ---- 事件 ----
    def _on_left_click(self, event):
        """左键点击画布 = 在图像像素位置添加点。"""
        # 检查是否在背景图区域内
        ipx, ipy = self.canvas.canvas_to_img(event.x, event.y)
        if not (0 <= ipx < self.img_w and 0 <= ipy < self.img_h):
            return

        self.counter += 1
        mx, my = self._img_to_map(ipx, ipy)
        name = 'P%d' % self.counter
        self.points.append((ipx, ipy, mx, my, name))
        self._redraw_points()
        self.status_var.set('添加 %s:  map=(%.4f, %.4f)  像素=(%.1f, %.1f)  zoom=%.1fx' %
                            (name, mx, my, ipx, ipy, self.canvas.zoom))
        print('[+] %s: map=(%.4f, %.4f)' % (name, mx, my))

    def _on_right_click(self, event):
        self._undo()

    def _on_mouse_move(self, event):
        ipx, ipy = self.canvas.canvas_to_img(event.x, event.y)
        in_img = 0 <= ipx < self.img_w and 0 <= ipy < self.img_h
        if in_img:
            mx, my = self._img_to_map(ipx, ipy)
            self.status_var.set(
                '像素:(%.1f, %.1f)  map:(%.4f, %.4f)  |  已标 %d 点  zoom=%.1fx  |  滚轮缩放 Shift拖拽平移' %
                (ipx, ipy, mx, my, len(self.points), self.canvas.zoom))
        else:
            self.status_var.set('鼠标在地图外  |  已标 %d 点  zoom=%.1fx' % (len(self.points), self.canvas.zoom))

    def _on_close(self):
        if self.points:
            if messagebox.askyesno('保存', '退出前保存 %d 个点到 YAML？' % len(self.points)):
                self._save()
        self.destroy()

    # ---- 点操作（坐标都是原图像素） ----
    def _clear_canvas_dots(self):
        for o in self._dot_ovals:
            self.canvas.delete(o)
        for t in self._dot_labels:
            self.canvas.delete(t)
        self._dot_ovals = []
        self._dot_labels = []

    def _redraw_points(self):
        self._clear_canvas_dots()
        z = self.canvas.zoom
        r = max(2, int(self.dot_radius * z))  # 圆点大小随缩放
        font_size = max(7, int(10 * z))
        for ipx, ipy, mx, my, name in self.points:
            cx, cy = self.canvas.img_to_canvas(ipx, ipy)
            oval = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                            fill='#ff4444', outline='#ffff00',
                                            width=max(1, int(1.5 * z)),
                                            tags=('dot',))
            self._dot_ovals.append(oval)
            txt = self.canvas.create_text(cx + r + 2, cy - r - 2,
                                           text=name, anchor=tk.NW,
                                           fill='#00ff88',
                                           font=('Consolas', font_size, 'bold'),
                                           tags=('label',))
            self._dot_labels.append(txt)

    def _rename_last(self):
        new_name = self.name_var.get().strip()
        if not new_name:
            self.status_var.set('请先在名称框输入新名字')
            return
        if not self.points:
            self.status_var.set('没有点可重命名')
            return
        ipx, ipy, mx, my, _ = self.points[-1]
        self.points[-1] = (ipx, ipy, mx, my, new_name)
        self._redraw_points()
        self.name_var.set('')
        self.status_var.set('已重命名为 "%s"' % new_name)
        print('[*] Renamed last -> "%s"' % new_name)

    def _undo(self):
        if self.points:
            removed = self.points.pop()
            self._redraw_points()
            self.status_var.set('撤销 %s (剩余 %d 点)' % (removed[4], len(self.points)))
            print('[-] Removed %s, %d remaining' % (removed[4], len(self.points)))
        else:
            self.status_var.set('没有点可撤销')

    def _clear(self):
        if self.points and messagebox.askyesno('确认', '清空全部 %d 个点？' % len(self.points)):
            self.points = []
            self.counter = 0
            self._redraw_points()
            self.status_var.set('已清空全部点')

    def _save(self):
        if not self.points:
            self.status_var.set('没有点可保存!')
            return

        data = {
            'description': 'Points marked on %s map using mark_map_gui.py' % self.map_name,
            'timestamp': datetime.now().isoformat(),
            'map': self.map_name,
            'resolution': self.resolution,
            'origin': [self.origin_x, self.origin_y,
                       self.meta['origin'][2] if len(self.meta['origin']) > 2 else 0.0],
            'count': len(self.points),
            'points': [],
        }
        for ipx, ipy, mx, my, name in self.points:
            data['points'].append({'name': name, 'x': mx, 'y': my, 'z': 0.0})

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
        for p in data['points']:
            print('    %s: [%.4f, %.4f, 0.0]' % (p['name'], p['x'], p['y']))
        print('=' * 60)

    def _show_list(self):
        if not self.points:
            messagebox.showinfo('点列表', '还没有标记任何点')
            return
        win = tk.Toplevel(self)
        win.title('已标记的点 (%d)' % len(self.points))
        win.geometry('560x400')
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        ttk.Label(frame, text='%-4s  %-14s  %12s  %12s  %s' % ('#', 'Name', 'x', 'y', 'z'),
                  font=('Consolas', 10, 'bold')).pack(anchor=tk.W, pady=2)
        text = tk.Text(frame, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=True)
        for i, (ipx, ipy, mx, my, name) in enumerate(self.points):
            text.insert(tk.END, '%-4d  %-14s  %12.4f  %12.4f  0.0\n' % (i + 1, name, mx, my))
        text.config(state=tk.DISABLED)

        def _copy():
            lines = ['%s: [%.4f, %.4f, 0.0]' % (n, x, y) for _, _, x, y, n in self.points]
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
            self.status_var.set('已复制 %d 个点到剪贴板' % len(self.points))

        ttk.Button(win, text='复制到剪贴板', command=_copy).pack(pady=5)


def main():
    parser = argparse.ArgumentParser(description='PGM 地图可视化标点工具（支持缩放平移）')
    parser.add_argument('-m', '--map', default='game', help='地图名 (默认: game)')
    parser.add_argument('-o', '--output', default=None, help='输出 YAML 文件名')
    args = parser.parse_args()
    app = MapMarker(map_name=args.map, output_file=args.output)
    app.mainloop()


if __name__ == '__main__':
    main()
