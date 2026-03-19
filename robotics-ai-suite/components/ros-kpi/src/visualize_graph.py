#!/usr/bin/env python3
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
"""
ROS2 Pipeline Graph Visualizer  -  rqt_graph-style directed view
================================================================
Renders the ROS2 computation graph as a top-down directed graph:

  [Node] --publish--> [/topic] --subscribe--> [Node]

Nodes are coloured by pipeline role (Sensor / Perception / Planning /
Controls / Other).  Topic boxes carry live KPI metrics (frequency,
latency mean/std-dev, message count, spike count) and are coloured
by latency health (green / amber / red).

Two data sources are used:
  1. graph_topology.json  (written by ros2_graph_monitor.py --topology)
     Provides the real Node -> Topic -> Node edges – needed for a true
     directed-graph view.  Generated alongside every monitoring session.
  2. graph_timing.csv     (always present)
     Provides per-topic KPI metrics when topology JSON is absent, and
     enriches the topology view with rolling latency stats.

Usage
-----
  # Interactive window (requires display)
  python src/visualize_graph.py <session_dir>/graph_timing.csv

  # Non-interactive (headless / CI)
  python src/visualize_graph.py <csv> --no-show --output pipeline.png

  # Explicit topology file
  python src/visualize_graph.py <csv> --topology <session_dir>/graph_topology.json

  # Per-session via Makefile
  make pipeline-graph [SESSION=<name>] [SHOW=no-show]
"""

import argparse
import csv
import json
import os
import sys
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
#  Pipeline category helpers  (mirrors ros2_graph_monitor.py)
# ──────────────────────────────────────────────────────────────────────────────

CATEGORIES = ['Sensor', 'Perception', 'Motion Planning', 'Controls', 'Other']

# Horizontal position (0‥1) for node columns
CAT_NODE_X = {
    'Sensor':          0.06,
    'Perception':      0.30,
    'Motion Planning': 0.54,
    'Controls':        0.78,
    'Other':           0.94,
}

# Midpoint topic lanes (between node columns) – topics that bridge two stages land here
TOPIC_LANE_X = {
    ('Sensor',          'Perception'):      0.18,
    ('Perception',      'Motion Planning'): 0.42,
    ('Motion Planning', 'Controls'):        0.66,
}

# Node box style per category
CAT_NODE_FC   = {
    'Sensor':          '#cce5ff',
    'Perception':      '#e2ccff',
    'Motion Planning': '#ccffe5',
    'Controls':        '#ffcccc',
    'Other':           '#eeeeee',
}
CAT_NODE_EC   = {
    'Sensor':          '#1f77b4',
    'Perception':      '#9467bd',
    'Motion Planning': '#2ca02c',
    'Controls':        '#d62728',
    'Other':           '#7f7f7f',
}
CAT_HEADER_COLOR = {
    'Sensor':          '#1f77b4',
    'Perception':      '#9467bd',
    'Motion Planning': '#2ca02c',
    'Controls':        '#d62728',
    'Other':           '#7f7f7f',
}

# ──────────────────────────────────────────────────────────────────────────────
#  Internal / system topic filter
# ──────────────────────────────────────────────────────────────────────────────

import re as _re

# Topics matching this pattern carry no pipeline-level information and only
# add visual clutter (ROS2 service interfaces, lifecycle events, action
# status/feedback introspection topics, the global clock, etc.).
INTERNAL_TOPIC_RE = _re.compile(
    r'(rosout'
    r'|parameter_events'
    r'|describe_parameters'
    r'|get_parameters'
    r'|list_parameters'
    r'|set_parameters'
    r'|rcl_interfaces'
    r'|/bond'
    r'|/_action'
    r'|/transition_event'
    r'|/tf_static'
    r'|/clock'
    r')'
)

# Nodes whose sole role is to observe (subscribe to everything).  They create
# massive star-shaped fan-out that obscures the real pipeline edges.
# transform_listener_impl_* are internal TF2 library threads – not real nodes.
MONITOR_NODE_RE = _re.compile(
    r'(ros2_graph_monitor'
    r'|ros2_monitor'
    r'|rviz2'
    r'|rviz'
    r'|rqt'
    r'|transform_listener_impl'
    r')'
)


SENSOR_PATTERNS    = ['/scan', '/laser', '/lidar', '/camera', '/image', '/imu',
                      '/gps', '/gnss', '/odom', '/odometry', '/depth', '/pointcloud',
                      '/point_cloud', '/ultrasonic', '/sonar', '/range', '/battery',
                      '/joint_states', '/tf', '/clock']
SENSOR_TYPES       = ['sensor_msgs', 'tf2_msgs']
PERCEPTION_PATTERNS = ['/map', '/costmap', '/obstacles', '/detections', '/tracked',
                        '/classification', '/semantic', '/occupancy', '/global_costmap',
                        '/local_costmap', '/voxel', '/footprint', '/markers',
                        '/visualization', '/labels', '/cloud', '/grid', '/localization']
PERCEPTION_TYPES    = ['nav_msgs/msg/occupancygrid', 'nav_msgs/msg/odometry',
                       'visualization_msgs']
PLANNING_PATTERNS   = ['/plan', '/path', '/global_plan', '/local_plan', '/trajectory',
                        '/goal', '/waypoint', '/route', '/planner', '/planning', '/navigate']
PLANNING_TYPES      = ['nav_msgs/msg/path', 'nav2_msgs', 'action']
CONTROL_PATTERNS    = ['/cmd_vel', '/cmd', '/control', '/velocity', '/speed',
                        '/steering', '/throttle', '/brake', '/motor', '/actuator',
                        '/joint_command']
CONTROL_TYPES       = ['geometry_msgs/msg/twist', 'ackermann_msgs', 'control_msgs']


def categorize_topic(topic: str, msg_type: str = '') -> str:
    tl = topic.lower()
    mt = (msg_type or '').lower()
    if any(p in tl for p in SENSOR_PATTERNS)    or any(t in mt for t in SENSOR_TYPES):
        return 'Sensor'
    if any(p in tl for p in PERCEPTION_PATTERNS) or any(t in mt for t in PERCEPTION_TYPES):
        return 'Perception'
    if any(p in tl for p in PLANNING_PATTERNS)   or any(t in mt for t in PLANNING_TYPES):
        return 'Motion Planning'
    if any(p in tl for p in CONTROL_PATTERNS)    or any(t in mt for t in CONTROL_TYPES):
        return 'Controls'
    return 'Other'


def _infer_node_category(node_name: str, publishes: list, topic_meta: dict) -> str:
    """Infer a node's pipeline category from its published topic set."""
    cats = [categorize_topic(t, topic_meta.get(t, {}).get('msg_type', ''))
            for t in publishes]
    if not cats:
        # Fall back to subscribed topics if nothing published
        return 'Other'
    # Weighted vote: Controls > Planning > Perception > Sensor > Other
    priority = {'Controls': 4, 'Motion Planning': 3, 'Perception': 2, 'Sensor': 1, 'Other': 0}
    return max(cats, key=lambda c: priority.get(c, 0))


# ──────────────────────────────────────────────────────────────────────────────
#  Colour helpers for topic health
# ──────────────────────────────────────────────────────────────────────────────

def _topic_health_colors(td: dict):
    """Return (face, edge, label) based on latency / spike data."""
    spikes = td.get('spikes', 0) or td.get('spike_count', 0)
    if spikes and spikes > 0:
        return '#ffd0d0', '#d62728', 'spike'
    mean_ms = td.get('latency_mean_ms') or td.get('avg_delta_ms')
    std_ms  = td.get('latency_std_dev_ms')
    val = max(filter(None, [mean_ms, std_ms]), default=None)
    if val is None:
        return '#f5f5f5', '#aaaaaa', 'no-data'
    if val < 20:
        return '#d5f5d5', '#2ca02c', 'good'
    if val < 100:
        return '#fff3cc', '#e6a817', 'warn'
    return '#ffe0cc', '#e05a00', 'high'


def _fmt_hz(v):
    if v is None: return 'N/A'
    if v >= 100:  return f'{v:.0f} Hz'
    if v >= 10:   return f'{v:.1f} Hz'
    return f'{v:.2f} Hz'

def _fmt_ms(v):
    if v is None: return 'N/A'
    if v < 1:     return f'{v*1000:.0f} us'
    return f'{v:.1f} ms'


# ──────────────────────────────────────────────────────────────────────────────
#  CSV parser  (metrics only, no topology)
# ──────────────────────────────────────────────────────────────────────────────

def _flt(v):
    try:
        return float(v) if v and v.strip() not in ('', 'None') else None
    except (ValueError, AttributeError):
        return None


def parse_csv_metrics(csv_file: str) -> dict:
    """
    Read graph_timing.csv and return per-topic KPI snapshots.

    Each CSV row is already a rolling-window snapshot written by the monitor
    on every message.  Re-averaging all rows would give a mean-of-means.
    Instead we take the LAST row per topic, which is the most up-to-date
    rolling state at session end.
    """
    last: dict = {}   # topic_name -> last row dict
    start = end = None
    with open(csv_file) as f:
        for row in csv.DictReader(f):
            last[row['topic_name']] = row
            ts = _flt(row.get('timestamp'))
            if ts:
                if start is None or ts < start: start = ts
                if end   is None or ts > end:   end   = ts

    result = {}
    for name, row in last.items():
        result[name] = {
            'msg_type':          row.get('msg_type', ''),
            'is_input':          row.get('is_input',  'False') == 'True',
            'is_output':         row.get('is_output', 'False') == 'True',
            'msg_count':         int(_flt(row.get('message_count')) or 0),
            'avg_freq_hz':       _flt(row.get('frequency_hz')),
            'latency_mean_ms':   _flt(row.get('latency_mean_ms')),
            'latency_std_dev_ms': _flt(row.get('latency_std_dev_ms')),
            'publishers':  [],
            'subscribers': [],
        }
    return result, {'start': start, 'end': end,
                    'duration': (end - start) if (start and end) else None}


def _csv_meta_only(csv_file: str) -> dict:
    """Fast single-pass over the CSV to get just the session duration."""
    start = end = None
    try:
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = _flt(row.get('timestamp'))
                if ts:
                    if start is None or ts < start: start = ts
                    if end   is None or ts > end:   end   = ts
    except Exception:
        pass
    return {'start': start, 'end': end,
            'duration': (end - start) if (start and end) else None}


# ──────────────────────────────────────────────────────────────────────────────
#  Layout engine
# ──────────────────────────────────────────────────────────────────────────────

class GraphLayout:
    """
    Compute (x, y) positions for every node and topic element so the picture
    flows left-to-right through the Sensor → Perception → Planning → Controls
    pipeline, matching rqt_graph conventions.

    Rules
    -----
    * Nodes are placed in vertical columns at the x-position of their inferred
      pipeline category.
    * Topics that *bridge* two adjacent pipeline stages (their publisher nodes
      are in stage N and subscriber nodes are in stage N+1) are placed in the
      topic-lane gap between those stages.
    * All other topics fall back to their own category x-lane (offset slightly
      from the node column).
    * Within each x-column, elements are distributed evenly along the y-axis.
    """

    # Usable drawing area in axes-fraction coordinates
    X0, X1 = 0.01, 0.99
    Y0, Y1 = 0.02, 0.95

    def __init__(self, nodes: dict, topics: dict, topic_meta: dict):
        """
        Parameters
        ----------
        nodes       : {node_name: {'publishes': [...], 'subscribes': [...]}}
        topics      : {topic_name: {'publishers': [...], 'subscribers': [...], ...metrics}}
        topic_meta  : additional per-topic metadata (msg_type etc.) merged from CSV
        """
        self.nodes = nodes
        self.topics = topics
        self.topic_meta = topic_meta

        # Assign node categories
        self.node_cat: dict[str, str] = {}
        for n, nd in nodes.items():
            self.node_cat[n] = _infer_node_category(n, nd.get('publishes', []), topic_meta)

        # Assign topic x-lanes
        self.topic_lane: dict[str, float] = {}
        self._assign_topic_lanes()

        # Compute final (x, y) positions
        self.pos: dict[str, tuple[float, float]] = {}
        self._compute_positions()

    # ------------------------------------------------------------------
    def _assign_topic_lanes(self):
        """Determine the x-lane (0‥1) for each topic."""
        for tname, td in self.topics.items():
            pub_cats  = {self.node_cat.get(n) for n in td.get('publishers', [])
                         if n in self.node_cat}
            sub_cats  = {self.node_cat.get(n) for n in td.get('subscribers', [])
                         if n in self.node_cat}

            # Try to find a bridging lane between adjacent stages
            lane = None
            for (c1, c2), x in TOPIC_LANE_X.items():
                if c1 in pub_cats and c2 in sub_cats:
                    lane = x
                    break
                if c2 in pub_cats and c1 in sub_cats:   # reverse flow
                    lane = x
                    break

            if lane is None:
                # Place topic in the same column as its category's nodes.
                # This keeps self-loop topics co-located with their nodes and
                # avoids the previous ±0.10 offset that collided with bridge lanes.
                cat = categorize_topic(tname,
                                       self.topic_meta.get(tname, {}).get('msg_type', ''))
                lane = CAT_NODE_X.get(cat, CAT_NODE_X['Other'])

            self.topic_lane[tname] = lane

    # ------------------------------------------------------------------
    def _compute_positions(self):
        """Stack nodes/topics within each x-column and assign y positions."""
        # Build buckets: x_lane -> [element_id (prefixed)]
        buckets: dict[float, list] = defaultdict(list)

        for n in self.nodes:
            x = CAT_NODE_X.get(self.node_cat.get(n, 'Other'), 0.94)
            buckets[round(x, 3)].append(('node', n))

        for t in self.topics:
            x = self.topic_lane.get(t, 0.50)
            buckets[round(x, 3)].append(('topic', t))

        # Track the densest column so callers can scale figure height
        self.max_bucket_size = max((len(v) for v in buckets.values()), default=1)

        # Assign y within each bucket
        for x_key, items in buckets.items():
            n = len(items)
            ys = np.linspace(self.Y1, self.Y0, n + 2)[1:-1]  # avoid edges
            for (kind, name), y in zip(items, ys):
                self.pos[f'{kind}::{name}'] = (x_key, float(y))

    # ------------------------------------------------------------------
    def get(self, kind: str, name: str):
        return self.pos.get(f'{kind}::{name}', (0.5, 0.5))


# ──────────────────────────────────────────────────────────────────────────────
#  Drawing
# ──────────────────────────────────────────────────────────────────────────────

NODE_W  = 0.085   # axes-fraction width of a node box
NODE_H  = 0.045
TOPIC_W = 0.088
TOPIC_H = 0.038


def _draw_node(ax, x, y, label, category, is_target=False, fontsize=7.5,
               w=None, h=None, sublabel=None):
    nw = w if w is not None else NODE_W
    nh = h if h is not None else NODE_H
    fc = CAT_NODE_FC.get(category, '#eeeeee')
    ec = CAT_NODE_EC.get(category, '#555555')
    lw = 2.5 if is_target else 1.2
    patch = FancyBboxPatch(
        (x - nw/2, y - nh/2), nw, nh,
        boxstyle='round,pad=0.004',
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ax.transAxes, zorder=4, picker=True,
    )
    ax.add_patch(patch)
    disp = label.lstrip('/')
    if len(disp) > 18:
        disp = disp[:15] + '...'
    # Shift name up slightly when there's a delay sublabel beneath it
    label_y = y + nh * 0.14 if sublabel else y
    ax.text(x, label_y, disp,
            ha='center', va='center', fontsize=fontsize,
            fontweight='bold', color='#111111',
            transform=ax.transAxes, zorder=5, clip_on=True)
    if sublabel:
        ax.text(x, y - nh * 0.28, sublabel,
                ha='center', va='center',
                fontsize=max(fontsize - 1.5, 4.5),
                color='#444466', style='italic',
                transform=ax.transAxes, zorder=5, clip_on=True)
    return patch


def _draw_topic(ax, x, y, name, td, fontsize=6.5, w=None, h=None):
    tw = w if w is not None else TOPIC_W
    th = h if h is not None else TOPIC_H
    fc, ec, _health = _topic_health_colors(td)
    lw = 2.0 if (td.get('is_input') or td.get('is_output')) else 1.0

    patch = FancyBboxPatch(
        (x - tw/2, y - th/2), tw, th,
        boxstyle='round,pad=0.003',
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ax.transAxes, zorder=4, picker=True,
    )
    ax.add_patch(patch)

    # Topic name (strip leading /)
    disp = name.lstrip('/')
    if len(disp) > 20:
        disp = disp[:17] + '...'

    io_tag = ''
    if td.get('is_input') and td.get('is_output'):
        io_tag = ' [I/O]'
    elif td.get('is_input'):
        io_tag = ' [IN]'
    elif td.get('is_output'):
        io_tag = ' [OUT]'

    ax.text(x, y + th * 0.18,
            disp + io_tag,
            ha='center', va='center', fontsize=fontsize, fontweight='bold',
            color='#111111', transform=ax.transAxes, zorder=5, clip_on=True)

    # Metrics sub-line
    parts = []
    freq   = td.get('avg_freq_hz')
    delay  = td.get('latency_mean_ms') or td.get('avg_delta_ms')
    jitter = td.get('latency_std_dev_ms')
    spikes = td.get('spikes') or td.get('spike_count') or 0
    mc     = td.get('msg_count') or 0

    if freq   is not None: parts.append(_fmt_hz(freq))
    if delay  is not None: parts.append(f'd:{_fmt_ms(delay)}')
    if jitter is not None: parts.append(f'j:{_fmt_ms(jitter)}')
    if spikes:             parts.append(f'[!]{spikes}sp')

    if not parts:
        # Topic was discovered via graph introspection but not actively
        # subscribed to by the monitor — no timing data available.
        parts.append(f'{mc:,} msgs' if mc else '—')

    # Only show metrics line if box is tall enough
    if th >= 0.025:
        ax.text(x, y - th * 0.22,
                '  '.join(parts[:3]),
                ha='center', va='center', fontsize=max(fontsize - 1.0, 5.0),
                color='#333333', transform=ax.transAxes, zorder=5, clip_on=True)
    return patch


def _draw_edge(ax, x0, y0, x1, y1, color='#6699bb', lw=1.0, alpha=0.7,
               label=''):
    """Draw a directed arrow between two points (axes fraction coords)."""
    style = 'arc3,rad=0.0'
    if abs(y1 - y0) > 0.15:                   # bend long vertical edges
        rad = 0.25 * (1 if x1 > x0 else -1)
        style = f'arc3,rad={rad:.2f}'

    ax.annotate(
        '', xy=(x1, y1), xytext=(x0, y0),
        xycoords='axes fraction', textcoords='axes fraction',
        arrowprops=dict(
            arrowstyle='->', color=color, lw=lw,
            connectionstyle=style,
            shrinkA=3, shrinkB=3,
        ),
        zorder=3, annotation_clip=False,
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Node detail popup
# ──────────────────────────────────────────────────────────────────────────────


def _open_node_detail(nname: str, nd: dict, cat: str, topics_to_show: dict,
                      main_fig=None):
    """
    Open a Tkinter Toplevel window showing the node's publisher / subscriber
    topics with per-topic KPI metrics.

    Uses a native Tk window so it works reliably inside the running TkAgg
    mainloop without any plt.show() re-entrancy issues.
    Falls back to a styled matplotlib figure window when Tkinter is not
    available (e.g. Qt5 backend).
    """
    import matplotlib as _mpl
    be = _mpl.get_backend().lower()
    non_interactive = be in ('agg', 'pdf', 'svg', 'ps', 'cairo', 'template')
    if non_interactive:
        return   # headless – no windows

    pub_topics = [t for t in nd.get('publishes',  []) if t in topics_to_show]
    sub_topics = [t for t in nd.get('subscribes', []) if t in topics_to_show]

    proc_mean = nd.get('proc_delay_mean_ms')
    proc_std  = nd.get('proc_delay_std_dev_ms')
    proc_n    = nd.get('proc_delay_samples', 0)
    if proc_mean is not None and proc_std is not None:
        proc_str = f'{proc_mean:.2f} ms ± {proc_std:.2f} ms  ({proc_n} samples)'
    elif proc_mean is not None:
        proc_str = f'{proc_mean:.2f} ms  ({proc_n} samples)'
    else:
        proc_str = 'n/a  (pure publisher or no callback data yet)'

    # ── Try native Tkinter Toplevel first ─────────────────────────────────
    try:
        import tkinter as tk
        from tkinter import font as tkfont

        # Get the Tk root that TkAgg created; prefer the root from main_fig
        root = None
        if main_fig is not None:
            try:
                root = main_fig.canvas.get_tk_widget().winfo_toplevel()
            except Exception:
                pass
        if root is None:
            root = tk._default_root   # type: ignore[attr-defined]
        if root is None:
            raise RuntimeError("No Tk root available")

        # Destroy previous window for this node if it exists
        win_name = f'nd_{nname.replace("/","_").replace(" ","_")}'
        for child in root.winfo_children():
            if getattr(child, '_node_detail_key', None) == win_name:
                try:
                    child.destroy()
                except Exception:
                    pass

        top = tk.Toplevel(root)
        top._node_detail_key = win_name  # type: ignore[attr-defined]
        top.title(f'Node: {nname.lstrip("/")}')
        top.configure(bg='#1a1a2e')
        top.resizable(True, True)

        # ── fonts ─────────────────────────────────────────────────────────
        f_title = tkfont.Font(family='Helvetica', size=14, weight='bold')
        f_sub   = tkfont.Font(family='Helvetica', size=9)
        f_hdr   = tkfont.Font(family='Helvetica', size=9,  weight='bold')
        f_row   = tkfont.Font(family='Courier',   size=9)

        BG1, BG2, BG3 = '#16213e', '#0f3460', '#1d2c4e'
        FG_TITLE, FG_HDR, FG_ROW = '#111111', '#aabbcc', '#ccd6ff'

        # ── Node header ───────────────────────────────────────────────────
        hdr_frame = tk.Frame(top, bg=CAT_NODE_FC.get(cat, '#eeeeee'),
                             relief='ridge', bd=2)
        hdr_frame.pack(fill='x', padx=8, pady=(8, 4))
        tk.Label(hdr_frame, text=nname.lstrip('/'),
                 font=f_title, bg=CAT_NODE_FC.get(cat, '#eeeeee'),
                 fg=FG_TITLE).pack(pady=(6, 0))
        tk.Label(hdr_frame,
                 text=f'Category: {cat}    |    Processing delay: {proc_str}',
                 font=f_sub, bg=CAT_NODE_FC.get(cat, '#eeeeee'),
                 fg='#334466').pack(pady=(0, 6))

        # ── Helper: one table section ──────────────────────────────────────
        def _make_section(parent, title: str, topics: list):
            # Section heading
            sec_hdr = tk.Frame(parent, bg=BG3)
            sec_hdr.pack(fill='x', padx=8, pady=(6, 0))
            tk.Label(sec_hdr, text=title, font=f_hdr,
                     bg=BG3, fg='white').pack(pady=3)

            # Column headers
            def _row(parent, bg, values, font, fg):
                fr = tk.Frame(parent, bg=bg)
                fr.pack(fill='x', padx=8)
                widths = [55, 8, 10, 18, 6]   # proportional weight
                for val, w in zip(values, widths):
                    tk.Label(fr, text=val, font=font,
                             bg=bg, fg=fg,
                             anchor='w', width=w).pack(side='left', padx=2)

            _row(top, BG2,
                 ['Topic', 'Msgs', 'Freq', 'Latency (mean ± std)', 'Health'],
                 f_hdr, FG_HDR)

            # Separator
            tk.Frame(top, bg='#334477', height=1).pack(fill='x', padx=8)

            if not topics:
                tk.Label(top, text='  (none in displayed graph)',
                         font=f_sub, bg=BG1, fg='#556688').pack(
                    anchor='w', padx=16, pady=2)
                return

            HEALTH_COLORS = {
                'good':    ('#d5f5d5', '●'),
                'warn':    ('#fff3cc', '●'),
                'high':    ('#ffe0cc', '●'),
                'spike':   ('#ffd0d0', '!'),
                'no-data': ('#f5f5f5', '–'),
            }

            for i, tname in enumerate(topics):
                td  = topics_to_show.get(tname, {})
                _, _, health = _topic_health_colors(td)
                bg  = '#1d2c4e' if i % 2 == 0 else '#192648'

                mc = td.get('msg_count', 0) or 0
                freq_s = _fmt_hz(td.get('avg_freq_hz'))
                lat_mean = td.get('latency_mean_ms') or td.get('avg_delta_ms')
                lat_std  = td.get('latency_std_dev_ms')
                if lat_mean is not None:
                    lat_s = (_fmt_ms(lat_mean) + f' ± {_fmt_ms(lat_std)}'
                             if lat_std is not None else _fmt_ms(lat_mean))
                else:
                    lat_s = '—'

                h_color, h_sym = HEALTH_COLORS.get(health, ('#eeeeee', '?'))

                _row(top, bg,
                     [tname, f'{mc:,}', freq_s, lat_s, h_sym],
                     f_row, FG_ROW)

        _make_section(top, f'PUBLISHES  →  {len(pub_topics)} topic(s)',  pub_topics)
        _make_section(top, f'SUBSCRIBES  ←  {len(sub_topics)} topic(s)', sub_topics)

        # Close button
        tk.Button(top, text='Close', command=top.destroy,
                  bg='#334477', fg='white',
                  relief='flat', padx=10, pady=4).pack(pady=8)

        top.lift()
        top.focus_set()
        return   # success – done

    except Exception as _tk_err:
        # Tk not reachable (Qt backend, etc.) – fall back to matplotlib figure
        pass

    # ── Fallback: plain matplotlib figure ────────────────────────────────
    try:
        pfig = plt.figure(num=f'node_detail__{nname}',
                          figsize=(15, min(max(4 + (len(pub_topics) + len(sub_topics)) * 0.4, 5.5), 26)),
                          facecolor='#1a1a2e')
        pfig.clear()
        pax = pfig.add_axes([0, 0, 1, 1])
        pax.set_facecolor('#16213e')
        pax.set_xlim(0, 1); pax.set_ylim(0, 1); pax.axis('off')

        lines = [f'Node: {nname.lstrip("/")}   [{cat}]',
                 f'Processing delay: {proc_str}', '',
                 'PUBLISHES:']
        for t in pub_topics or ['(none)']:
            td = topics_to_show.get(t, {})
            lat = td.get('latency_mean_ms') or td.get('avg_delta_ms')
            lines.append(f'  {t}   {_fmt_hz(td.get("avg_freq_hz"))}   {_fmt_ms(lat)}')
        lines += ['', 'SUBSCRIBES:']
        for t in sub_topics or ['(none)']:
            td = topics_to_show.get(t, {})
            lat = td.get('latency_mean_ms') or td.get('avg_delta_ms')
            lines.append(f'  {t}   {_fmt_hz(td.get("avg_freq_hz"))}   {_fmt_ms(lat)}')

        pax.text(0.02, 0.97, '\n'.join(lines),
                 ha='left', va='top', fontsize=8.5,
                 color='#ccd6ff', family='monospace',
                 transform=pax.transAxes, zorder=3)
        try:
            pfig.canvas.manager.set_window_title(f'Node: {nname}')
        except Exception:
            pass
        pfig.canvas.draw()
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
#  Main render function
# ──────────────────────────────────────────────────────────────────────────────

def render_graph(topology: dict, metrics: dict, meta: dict,
                 output_file: str = None, show: bool = True,
                 session_label: str = '',
                 filter_internal: bool = True,
                 filter_monitor_nodes: bool = True,
                 filter_isolated: bool = True):
    """
    Render the rqt_graph-style pipeline view.

    Parameters
    ----------
    topology             : parsed graph_topology.json  (may be empty dict for CSV-only mode)
    metrics              : per-topic KPI data from graph_timing.csv
    meta                 : {'duration': float, 'start': ts, 'end': ts}
    output_file          : path to save image (None = no save)
    show                 : open interactive matplotlib window
    filter_internal      : strip ROS2 system/service/action/lifecycle topics
    filter_monitor_nodes : strip observer nodes (rviz, rqt, ros2_graph_monitor,
                           transform_listener_impl)
    filter_isolated      : strip topic boxes that have no drawn edges after
                           other filters are applied (e.g. topics only rviz
                           subscribed to)
    """
    nodes_raw  = topology.get('nodes', {})
    t_topo_raw = topology.get('topics', {})

    # ── Filter observer / monitor nodes ──────────────────────────────────────
    if filter_monitor_nodes:
        nodes = {n: v for n, v in nodes_raw.items()
                 if not MONITOR_NODE_RE.search(n)}
        filtered_mnodes = len(nodes_raw) - len(nodes)
    else:
        nodes = dict(nodes_raw)
        filtered_mnodes = 0

    # ── Build topics dict ────────────────────────────────────────────────────────────────────────────────────
    # When topology JSON is present it is the single source of truth:
    # it already contains both structural data (publishers/subscribers) and
    # metrics (freq, delay, msg_count) for every topic the monitor subscribed
    # to.  Unsampled topics have msg_count=0 / None metrics; that is correct.
    # The CSV is only needed when no topology JSON is available.
    topics_merged: dict = {}
    if t_topo_raw:
        for t, td in t_topo_raw.items():
            entry = dict(td)
            if filter_monitor_nodes:
                entry['publishers']  = [n for n in entry.get('publishers',  []) if not MONITOR_NODE_RE.search(n)]
                entry['subscribers'] = [n for n in entry.get('subscribers', []) if not MONITOR_NODE_RE.search(n)]
            # Overlay CSV metrics when available — topology JSON captures structure
            # but shows 0 for SSH-discovered topics the monitor couldn't subscribe to.
            if t in metrics:
                m = metrics[t]
                for key in ('msg_count', 'avg_freq_hz', 'latency_mean_ms', 'latency_std_dev_ms',
                            'avg_delta_ms', 'spikes', 'msg_type'):
                    if m.get(key) is not None:
                        entry[key] = m[key]
            topics_merged[t] = entry
        # Also include CSV topics not in the topology (edge case: monitor subscribed
        # to a topic that disappeared before topology was saved).
        for t, md in metrics.items():
            if t not in topics_merged:
                topics_merged[t] = dict(md)
    else:
        # CSV-only fallback: no topology JSON, build from metric rows
        for t, md in metrics.items():
            topics_merged[t] = dict(md)

    # ── Filter internal / system topics ──────────────────────────────────────────────────────────────
    if filter_internal:
        topics_to_show = {t: d for t, d in topics_merged.items()
                          if not INTERNAL_TOPIC_RE.search(t)}
        filtered_itopics = len(topics_merged) - len(topics_to_show)
    else:
        topics_to_show = topics_merged
        filtered_itopics = 0

    # ── Drop isolated topics (no edges after filtering) ───────────────────────────────────────────────
    if filter_isolated:
        def _has_drawn_edge(td):
            return (any(n in nodes for n in td.get('publishers',  []))
                    or any(n in nodes for n in td.get('subscribers', [])))
        pre_iso = len(topics_to_show)
        topics_to_show = {t: d for t, d in topics_to_show.items()
                          if _has_drawn_edge(d)}
        filtered_isolated = pre_iso - len(topics_to_show)
    else:
        filtered_isolated = 0

    # ── Early-exit: nothing to draw ──────────────────────────────────────────
    if not nodes and not topics_to_show:
        print('\n  ⚠  No nodes or topics to display.')
        if filtered_mnodes and not filter_monitor_nodes is False:
            print(f'     (Only the ros2_graph_monitor node was found in this session —')
            print(f'      the ROS2 pipeline was not running when monitoring started.)')
        print()
        print('  How to fix:')
        print('    1. Start your ROS2 launch file first.')
        print('    2. Then run:  make monitor   (or make monitor-remote REMOTE_IP=<ip>)')
        print('    3. Then:      make pipeline-graph')
        if filtered_mnodes:
            print()
            print(f'  To see the raw observer-only data anyway:')
            print(f'    make pipeline-graph INCLUDE_MONITORS=1 INCLUDE_INTERNAL=1 INCLUDE_ISOLATED=1')

        # Render a minimal figure with the explanation text rather than a
        # blank dark canvas, so the window that opens is informative.
        fig = plt.figure(figsize=(14, 7), facecolor='#1a1a2e')
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor('#16213e')
        ax.axis('off')
        msg = (
            'No ROS2 nodes discovered in this session.\n\n'
            'The pipeline was likely not running when monitoring started.\n\n'
            'Steps:\n'
            '  1. Start your ROS2 launch file first\n'
            '  2. make monitor   (or make monitor-remote REMOTE_IP=<ip>)\n'
            '  3. make pipeline-graph\n\n'
            f'Session: {session_label}'
        )
        ax.text(0.5, 0.5, msg, ha='center', va='center', fontsize=13,
                color='#ffcc55', transform=ax.transAxes,
                fontfamily='monospace',
                bbox=dict(facecolor='#0f3460', edgecolor='#ffcc55',
                          boxstyle='round,pad=1.0', linewidth=2))
        if output_file:
            fig.savefig(output_file, dpi=100, bbox_inches='tight',
                        facecolor=fig.get_facecolor())
            print(f'  Empty-state image saved -> {output_file}')
        if show:
            try:
                plt.show()
            except Exception:
                pass
        plt.close(fig)
        return

    # ── Compute layout ───────────────────────────────────────────────────────
    layout = GraphLayout(nodes, topics_to_show, topics_to_show)

    filter_parts = []
    if filtered_itopics:  filter_parts.append(f'-{filtered_itopics} system topics')
    if filtered_mnodes:   filter_parts.append(f'-{filtered_mnodes} observer nodes')
    if filtered_isolated: filter_parts.append(f'-{filtered_isolated} isolated topics')
    filter_note = f'  [{", ".join(filter_parts)} filtered]' if filter_parts else ''
    print(f'  Rendering: {len(nodes)} nodes, {len(topics_to_show)} topics{filter_note}')
    print(f'  Densest column: {layout.max_bucket_size} items  →  figure height: '
          f'{max(16, layout.max_bucket_size * 0.55 + 4):.0f} in')

    # ────────────────────── figure setup ─────────────────────────────────────
    n_nodes  = len(nodes)
    n_topics = len(topics_to_show)
    mode_label = 'Node-Topic-Node (full topology)' if nodes else 'Topic-only (CSV metrics)'

    TITLE_H  = 0.06
    LEGEND_H = 0.07
    CONTENT_H = 1.0 - TITLE_H - LEGEND_H

    FIG_W = 32
    # Scale height so the densest column has ≥0.55 inches per element
    min_per_elem_inches = 0.55
    FIG_H = max(16, layout.max_bucket_size * min_per_elem_inches + 4)

    fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor='#1a1a2e')
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    ax = fig.add_axes([0, LEGEND_H, 1, CONTENT_H])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    ax.set_facecolor('#16213e')

    ax_title = fig.add_axes([0, LEGEND_H + CONTENT_H, 1, TITLE_H])
    ax_title.set_xlim(0, 1); ax_title.set_ylim(0, 1); ax_title.axis('off')
    ax_title.set_facecolor('#0f3460')

    ax_legend = fig.add_axes([0, 0, 1, LEGEND_H])
    ax_legend.set_xlim(0, 1); ax_legend.set_ylim(0, 1); ax_legend.axis('off')
    ax_legend.set_facecolor('#0f3460')

    # ────────────────────── title bar ────────────────────────────────────────
    dur_str = f'  |  {meta["duration"]:.0f} s' if meta.get('duration') else ''
    total_spikes = sum(
        (td.get('spikes', 0) or td.get('spike_count', 0) or 0)
        for td in topics_to_show.values()
    )
    spike_txt = f'  |  [!] {total_spikes} spikes' if total_spikes else ''
    filter_txt = ''
    if filter_internal and filtered_itopics:
        filter_txt += f'  |  -{filtered_itopics} system topics'
    if filter_monitor_nodes and filtered_mnodes:
        filter_txt += f'  |  -{filtered_mnodes} observer nodes'

    ax_title.text(0.5, 0.5,
                  f'ROS2 Pipeline Graph{dur_str}  |  {n_nodes} nodes  |  '
                  f'{n_topics} topics  |  {mode_label}{spike_txt}{filter_txt}  |  {session_label}',
                  ha='center', va='center', fontsize=12, fontweight='bold',
                  color='white', transform=ax_title.transAxes)
    # ── Adaptive box size so elements never overlap in the densest column ──
    # spacing = available y-range / (items_in_densest_bucket + 2 margins)
    y_range = GraphLayout.Y1 - GraphLayout.Y0   # 0.93
    slot    = y_range / (layout.max_bucket_size + 2)
    # Cap box height at 90 % of slot; let them be at most the default size
    t_h = min(TOPIC_H, slot * 0.90)
    n_h = min(NODE_H,  slot * 0.90)
    # Scale box width proportionally (keep aspect ratio)
    scale = t_h / TOPIC_H
    t_w = TOPIC_W * max(scale, 0.70)   # don't shrink width more than 30 %
    n_w = NODE_W  * max(scale, 0.70)
    # Scale fonts with boxes
    t_font = max(5.0, 6.5 * scale)
    n_font = max(5.0, 7.5 * scale)
    # Thin edges on dense graphs
    edge_lw    = max(0.3, 1.0  * scale)
    edge_alpha = max(0.4, 0.7  * scale)
    # ────────────────────── column headers ───────────────────────────────────
    for cat, x in CAT_NODE_X.items():
        n_cat_nodes  = sum(1 for n in nodes if layout.node_cat.get(n) == cat)
        n_cat_topics = sum(1 for t in topics_to_show
                           if abs(layout.topic_lane.get(t, -1) - x) < 0.02)
        if n_cat_nodes == 0 and n_cat_topics == 0:
            continue
        ec = CAT_HEADER_COLOR.get(cat, '#555')
        patch = FancyBboxPatch(
            (x - 0.055, 0.955), 0.11, 0.038,
            boxstyle='round,pad=0.003',
            facecolor=ec, edgecolor='white', linewidth=1.2,
            transform=ax.transAxes, zorder=3,
        )
        ax.add_patch(patch)
        ax.text(x, 0.974, cat,
                ha='center', va='center', fontsize=8.5, fontweight='bold',
                color='white', transform=ax.transAxes, zorder=4)
        ax.text(x, 0.959, f'{n_cat_nodes}N / {n_cat_topics}T',
                ha='center', va='center', fontsize=6.5, color='#dddddd',
                transform=ax.transAxes, zorder=4)

    # ────────────────────── draw edges first (below boxes) ───────────────────
    for tname, td in topics_to_show.items():
        tx, ty = layout.get('topic', tname)
        # Publisher node -> topic  (solid blue)
        for pub_node in td.get('publishers', []):
            if pub_node in nodes:
                nx, ny = layout.get('node', pub_node)
                _draw_edge(ax, nx, ny, tx, ty,
                           color='#5599dd', lw=edge_lw, alpha=edge_alpha)
        # Topic -> subscriber node  (solid orange)
        for sub_node in td.get('subscribers', []):
            if sub_node in nodes:
                nx, ny = layout.get('node', sub_node)
                _draw_edge(ax, tx, ty, nx, ny,
                           color='#dd8833', lw=edge_lw, alpha=edge_alpha)

    # ────────────────────── draw topic boxes ─────────────────────────────────
    topic_artists = []
    for tname, td in topics_to_show.items():
        tx, ty = layout.get('topic', tname)
        patch = _draw_topic(ax, tx, ty, tname, td, fontsize=t_font, w=t_w, h=t_h)
        # Build tooltip text
        mt_short = (td.get('msg_type') or '').split('/')[-1] or 'unknown'
        pubs = ', '.join(n.lstrip('/') for n in td.get('publishers', []))
        subs = ', '.join(n.lstrip('/') for n in td.get('subscribers', []))
        mc   = td.get('msg_count') or 0
        sampled = mc > 0 or td.get('avg_freq_hz') is not None
        info = (
            f'Topic:     {tname}\n'
            f'Type:      {mt_short}\n'
            f'Messages:  {mc:,}  {"" if sampled else "(not sampled)"}\n'
            f'Freq:      {_fmt_hz(td.get("avg_freq_hz"))}\n'
            f'Delay avg: {_fmt_ms(td.get("latency_mean_ms") or td.get("avg_delta_ms"))}\n'
            f'Jitter:    {_fmt_ms(td.get("latency_std_dev_ms"))}\n'
            f'Spikes:    {td.get("spikes", 0) or td.get("spike_count", 0)}\n'
            f'Publishers:   {pubs or "none"}\n'
            f'Subscribers:  {subs or "none"}'
        )
        topic_artists.append((patch, tname, info))

    # ────────────────────── draw node boxes ──────────────────────────────────
    node_artists = []
    target = topology.get('target_node')
    for nname, nd in nodes.items():
        nx, ny = layout.get('node', nname)
        cat = layout.node_cat.get(nname, 'Other')
        proc_mean = nd.get('proc_delay_mean_ms')
        proc_std  = nd.get('proc_delay_std_dev_ms')
        sublabel  = f'\u2206{proc_mean:.1f}ms' if proc_mean is not None else None
        patch = _draw_node(ax, nx, ny, nname, cat, is_target=(nname == target),
                           fontsize=n_font, w=n_w, h=n_h, sublabel=sublabel)
        pub_list  = ', '.join(t.lstrip('/') for t in nd.get('publishes',  []))
        sub_list  = ', '.join(t.lstrip('/') for t in nd.get('subscribes', []))
        if proc_mean is not None and proc_std is not None:
            proc_str = f'{proc_mean:.2f} ms \u00b1 {proc_std:.2f} ms ({nd.get("proc_delay_samples", 0)} samples)'
        elif proc_mean is not None:
            proc_str = f'{proc_mean:.2f} ms ({nd.get("proc_delay_samples", 0)} samples)'
        else:
            proc_str = 'n/a (pure publisher or no input yet)'
        info = (
            f'Node:         {nname}\n'
            f'Category:     {cat}\n'
            f'Proc delay:   {proc_str}\n'
            f'Publishes:    {pub_list  or "nothing"}\n'
            f'Subscribes:   {sub_list or "nothing"}\n'
            f'\u2192 Click to open detail view'
        )
        # Store nd and cat so the click handler can open the detail popup
        node_artists.append((patch, nname, info, nd, cat))

    # topic_artists: (patch, name, info)
    # node_artists:  (patch, name, info, nd, cat)
    all_artists = topic_artists + [(p, n, i) for p, n, i, *_ in node_artists]

    # ────────────────────── legend ───────────────────────────────────────────
    legend_items = [
        (mpatches.Patch(fc='#d5f5d5', ec='#2ca02c', lw=1.5), 'Latency < 20 ms'),
        (mpatches.Patch(fc='#fff3cc', ec='#e6a817', lw=1.5), '20 – 100 ms'),
        (mpatches.Patch(fc='#ffe0cc', ec='#e05a00', lw=1.5), '> 100 ms'),
        (mpatches.Patch(fc='#ffd0d0', ec='#d62728', lw=1.5), 'Spike [!]'),
        (mpatches.Patch(fc='#f5f5f5', ec='#aaaaaa', lw=1.0), 'No data'),
        (mpatches.Patch(fc='#cce5ff', ec='#1f77b4', lw=2.0), 'Node (Sensor)'),
        (mpatches.Patch(fc='#e2ccff', ec='#9467bd', lw=2.0), 'Node (Perception)'),
        (mpatches.Patch(fc='#ccffe5', ec='#2ca02c', lw=2.0), 'Node (Planning)'),
        (mpatches.Patch(fc='#ffcccc', ec='#d62728', lw=2.0), 'Node (Controls)'),
        (mpatches.FancyArrow(0, 0, 1, 0, width=0.3, fc='#5599dd'), 'Publish edge'),
        (mpatches.FancyArrow(0, 0, 1, 0, width=0.3, fc='#dd8833'), 'Subscribe edge'),
    ]
    ax_legend.legend(
        handles=[h for h, _ in legend_items],
        labels=[l for _, l in legend_items],
        loc='upper left', ncol=6, frameon=True,
        facecolor='#0f3460', edgecolor='#334477',
        fontsize=8, labelcolor='white',
        bbox_to_anchor=(0.005, 0.99), borderpad=0.6,
        handlelength=1.1, handleheight=0.9,
    )

    total_msgs = sum(td.get('msg_count', 0) for td in topics_to_show.values())
    ax_legend.text(0.5, 0.25,
                   f'{n_nodes} nodes  |  {n_topics} topics  |  {total_msgs:,} messages  |  '
                   'Blue arrows = publish   Orange arrows = subscribe',
                   ha='center', va='center', fontsize=8,
                   color='#aabbcc', transform=ax_legend.transAxes)

    # ────────────────────── interactive tooltip ───────────────────────────────
    tooltip = ax.text(
        0.0, 0.0, '',
        fontsize=7.5, color='#111111', ha='left', va='top',
        bbox=dict(boxstyle='round,pad=0.4', fc='#fffde7', ec='#e6a817', lw=1.5, alpha=0.96),
        transform=ax.transAxes, visible=False, zorder=10,
    )

    def _on_motion(event):
        if event.inaxes is not ax:
            tooltip.set_visible(False)
            fig.canvas.draw_idle()
            return
        hit = False
        for patch, _, info in all_artists:
            if patch.contains(event)[0]:
                tx_ = min(event.xdata + 0.01, 0.68)
                ty_ = min(event.ydata + 0.01, 0.94)
                tooltip.set_text(info)
                tooltip.set_position((tx_, ty_))
                tooltip.set_visible(True)
                hit = True
                break
        if not hit:
            tooltip.set_visible(False)
        fig.canvas.draw_idle()

    def _on_click(event):
        if event.inaxes is not ax:
            return
        # Check node artists first (they open detail popup on click)
        for patch, nname, info, nd, cat in node_artists:
            if patch.contains(event)[0]:
                print(f'\n{"─"*60}\n{info}\n{"─"*60}')
                _open_node_detail(nname, nd, cat, topics_to_show, main_fig=fig)
                return
        # Fall back to topic artists (print tooltip text to console)
        for patch, tname, info in topic_artists:
            if patch.contains(event)[0]:
                print(f'\n{"─"*60}\n{info}\n{"─"*60}')
                return

    fig.canvas.mpl_connect('motion_notify_event', _on_motion)
    fig.canvas.mpl_connect('button_press_event',  _on_click)

    # ────────────────────── save / show ─────────────────────────────────────
    if output_file:
        fig.savefig(output_file, dpi=150, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        print(f'Pipeline graph saved -> {output_file}')

    if show:
        try:
            plt.show()
        except Exception:
            print('Interactive display unavailable – graph saved to file.')

    plt.close(fig)


# ──────────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='ROS2 Pipeline Graph – rqt_graph-style directed node/topic view with KPI metrics.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Render from most-recent session (interactive):
  python src/visualize_graph.py monitoring_sessions/<session>/graph_timing.csv

  # Non-interactive, save PNG only:
  python src/visualize_graph.py graph_timing.csv --no-show --output pipeline.png

  # Provide topology JSON explicitly:
  python src/visualize_graph.py graph_timing.csv \\
      --topology graph_topology.json --output-dir ./vis

Note:
  graph_topology.json is written automatically by ros2_graph_monitor.py
  when the --topology flag is set (done automatically by monitor_stack.py).
  Without it the view shows topic-metric boxes only (no Node entities or edges).
        """,
    )
    parser.add_argument('csv_file', help='Path to graph_timing.csv')
    parser.add_argument('--topology', '-t', default=None,
                        help='Path to graph_topology.json (auto-detected if omitted).')
    parser.add_argument('--output', '-o', default=None, help='Output image path.')
    parser.add_argument('--output-dir', default=None,
                        help='Directory to save pipeline_graph.png.')
    parser.add_argument('--show',    dest='show', action='store_true',  default=True)
    parser.add_argument('--no-show', dest='show', action='store_false')
    parser.add_argument('--include-system', dest='filter_internal',
                        action='store_false', default=True,
                        help='Show system/infrastructure topics: /rosout, /clock, '
                             '/parameter_events, /_action/*, /transition_event, '
                             '/tf_static, /bond (hidden by default to focus on '
                             'sensor and application topics).')
    parser.add_argument('--include-monitors', dest='filter_monitors',
                        action='store_false', default=True,
                        help='Include rviz/rqt/ros2_graph_monitor/transform_listener '
                             'observer nodes (hidden by default).')
    parser.add_argument('--include-isolated', dest='filter_isolated',
                        action='store_false', default=True,
                        help='Include topic boxes that have no drawn edges after '
                             'other filters (e.g. topics only rviz subscribed to).')
    args = parser.parse_args()

    # Select matplotlib backend before any figure is created.
    # Must happen here – after arg parsing tells us whether we need a window –
    # but before pyplot creates any canvas objects.
    if not args.show:
        matplotlib.use('Agg', force=True)
    else:
        # Try interactive backends in order of preference
        for _be in ('TkAgg', 'Qt5Agg', 'GTK3Agg', 'wxAgg'):
            try:
                matplotlib.use(_be, force=True)
                break
            except Exception:
                continue

    if not os.path.isfile(args.csv_file):
        print(f'Error: {args.csv_file} not found.', file=sys.stderr)
        sys.exit(1)

    # Auto-detect topology JSON alongside the CSV
    topology_path = args.topology
    if topology_path is None:
        candidate = Path(args.csv_file).parent / 'graph_topology.json'
        if candidate.is_file():
            topology_path = str(candidate)

    # Determine output path
    output_file = args.output
    if output_file is None and args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = str(out_dir / 'pipeline_graph.png')
    if output_file is None and not args.show:
        output_file = str(Path(args.csv_file).parent / 'pipeline_graph.png')

    session_label = Path(args.csv_file).parent.name or Path(args.csv_file).stem

    # Load topology JSON first; it is the single source of truth for the graph
    # view (structure + metrics for sampled topics in one place).
    # The CSV is only parsed when no topology JSON is available.
    topology: dict = {}
    metrics:  dict = {}
    meta:     dict = {}

    if topology_path:
        print(f'Loading topology from {topology_path} ...')
        with open(topology_path) as f:
            topology = json.load(f)
        n_nodes   = len(topology.get('nodes', {}))
        n_ttopics = len(topology.get('topics', {}))
        print(f'  {n_nodes} nodes, {n_ttopics} topics in topology.')
        # Always parse the CSV too — the topology JSON captures structure but
        # SSH-discovered topics have msg_count=0; CSV has the real metrics.
        metrics, meta = parse_csv_metrics(args.csv_file)
    else:
        print('No graph_topology.json found – parsing CSV for metrics ...')
        metrics, meta = parse_csv_metrics(args.csv_file)
        print(f'  {len(metrics)} topics in CSV.')
        print('  Tip: run ros2_graph_monitor.py with --topology to get the full Node→Topic→Node view.')

    print('Rendering ...')
    render_graph(topology, metrics, meta,
                 output_file=output_file,
                 show=args.show,
                 session_label=session_label,
                 filter_internal=args.filter_internal,
                 filter_monitor_nodes=args.filter_monitors,
                 filter_isolated=args.filter_isolated)


if __name__ == '__main__':
    main()
