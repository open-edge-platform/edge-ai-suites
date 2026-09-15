# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for src/visualize_resources.py pure-logic aggregation functions.

Covers:
  aggregate_core_by_node — per-core CPU grouped by ROS2 node name (#63)
"""

from collections import defaultdict

from visualize_resources import aggregate_core_by_node


def _make_data(pid_records, ros2_node_map=None, threads=None):
    """Build a minimal parse_resource_log()-shaped dict for pid-mode data."""
    pids = defaultdict(list)
    for pid, records in pid_records.items():
        pids[pid] = records
    return {
        'timestamps': [],
        'pids': pids,
        'threads': defaultdict(list, threads or {}),
        'ros2_node_map': ros2_node_map or {},
    }


def _rec(time, core, cpu, command='cmd'):
    return {'time': time, 'core': core, 'cpu': cpu, 'command': command}


def _thread_rec(time, core, cpu, tgid, command='cmd'):
    return {'time': time, 'core': core, 'cpu': cpu, 'command': command, 'tgid': tgid}


def test_no_node_map_returns_empty():
    """Sessions without ros2_node_map (older captures) yield no per-node view."""
    data = _make_data({'1': [_rec('t0', 0, 50.0)]}, ros2_node_map={})
    assert not aggregate_core_by_node(data)


def test_groups_by_node_on_shared_core():
    """Two PIDs on the same core are attributed to their respective nodes."""
    data = _make_data(
        {
            '1': [_rec('t0', 0, 60.0), _rec('t1', 0, 60.0)],
            '2': [_rec('t0', 0, 20.0), _rec('t1', 0, 20.0)],
        },
        ros2_node_map={'1': 'controller_server', '2': 'planner_server'},
    )

    result = aggregate_core_by_node(data)

    assert len(result) == 1
    core, times, node_series = result[0]
    assert core == 0
    assert times == ['t0', 't1']
    assert node_series['controller_server'] == [60.0, 60.0]
    assert node_series['planner_server'] == [20.0, 20.0]
    assert '(other)' not in node_series  # nothing left over


def test_unmapped_pid_bucketed_as_non_ros2():
    """PIDs absent from ros2_node_map are grouped under '(non-ROS2)'."""
    data = _make_data(
        {
            '1': [_rec('t0', 0, 40.0)],
            '2': [_rec('t0', 0, 10.0)],  # not in ros2_node_map
        },
        ros2_node_map={'1': 'controller_server'},
    )

    _core, _times, node_series = aggregate_core_by_node(data)[0]

    assert node_series['controller_server'] == [40.0]
    assert node_series['(non-ROS2)'] == [10.0]


def test_caps_to_top_nodes_per_core_and_buckets_rest_as_other():
    """Only the busiest N node labels per core are kept individually."""
    node_map = {str(i): f'node_{i}' for i in range(1, 6)}  # 5 distinct nodes
    pid_records = {
        str(i): [_rec('t0', 0, cpu)]
        for i, cpu in zip(range(1, 6), [50.0, 40.0, 30.0, 20.0, 10.0])
    }
    data = _make_data(pid_records, ros2_node_map=node_map)

    _core, _times, node_series = aggregate_core_by_node(data, top_nodes_per_core=2)[0]

    # Only the top 2 busiest nodes (node_1, node_2) kept individually.
    assert set(node_series) == {'node_1', 'node_2', '(other)'}
    assert node_series['node_1'] == [50.0]
    assert node_series['node_2'] == [40.0]
    assert node_series['(other)'] == [30.0 + 20.0 + 10.0]


def test_selects_busiest_cores_only():
    """Only the top_cores busiest cores (by total session CPU) are returned."""
    data = _make_data(
        {
            '1': [_rec('t0', 0, 90.0)],   # core 0: busiest
            '2': [_rec('t0', 1, 5.0)],    # core 1: quiet
        },
        ros2_node_map={'1': 'node_a', '2': 'node_b'},
    )

    result = aggregate_core_by_node(data, top_cores=1)

    assert len(result) == 1
    assert result[0][0] == 0  # core 0 kept, core 1 dropped


def test_no_data_returns_empty():
    """A session with no matching PID records yields no per-core series."""
    data = _make_data({}, ros2_node_map={'1': 'node_a'})
    assert not aggregate_core_by_node(data)


def test_groups_by_node_in_thread_mode_using_tgid():
    """Thread records are keyed by TID but attributed via their 'tgid' (parent PID)."""
    data = _make_data(
        {},
        ros2_node_map={'1': 'controller_server', '2': 'planner_server'},
        threads={
            '101': [_thread_rec('t0', 0, 60.0, tgid='1'), _thread_rec('t1', 0, 60.0, tgid='1')],
            '201': [_thread_rec('t0', 0, 20.0, tgid='2'), _thread_rec('t1', 0, 20.0, tgid='2')],
        },
    )

    result = aggregate_core_by_node(data)

    assert len(result) == 1
    core, times, node_series = result[0]
    assert core == 0
    assert times == ['t0', 't1']
    assert node_series['controller_server'] == [60.0, 60.0]
    assert node_series['planner_server'] == [20.0, 20.0]
    assert '(other)' not in node_series
