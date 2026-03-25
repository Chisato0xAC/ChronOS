import time
from datetime import datetime, timedelta

from chronos_config import DAY_BOUNDARY_HOUR, DAY_BOUNDARY_MINUTE, DAY_BOUNDARY_SECOND


def get_cycle_window(now_ts: int = None) -> dict:
    # 计算当前时间属于哪个周期（04:00 到次日 04:00）。
    if now_ts is None:
        now_ts = int(time.time())

    now_dt = datetime.fromtimestamp(int(now_ts))
    boundary_today = now_dt.replace(
        hour=int(DAY_BOUNDARY_HOUR),
        minute=int(DAY_BOUNDARY_MINUTE),
        second=int(DAY_BOUNDARY_SECOND),
        microsecond=0,
    )

    if now_dt >= boundary_today:
        cycle_start = boundary_today
    else:
        cycle_start = boundary_today - timedelta(days=1)

    cycle_end = cycle_start + timedelta(days=1)
    cycle_key = cycle_start.strftime("%Y-%m-%d")
    return {
        "cycle_key": cycle_key,
        "start_ts": int(cycle_start.timestamp()),
        "end_ts": int(cycle_end.timestamp()),
        "start_text": cycle_start.strftime("%Y-%m-%d %H:%M:%S"),
        "end_text": cycle_end.strftime("%Y-%m-%d %H:%M:%S"),
    }


def calculate_cycle_run_cost(
    run_minutes_list: list, base_dp_per_minute: int, running_at_settlement: bool
) -> dict:
    # DP Cycle Run Cost Rule
    if running_at_settlement:
        return {
            "ok": True,
            "chaos_triggered": True,
            "chaos_rule": "TBD",
            "total_cost": 0,
            "details": [],
        }

    details = []
    total_cost = 0
    for i in range(len(run_minutes_list)):
        run_index = i + 1
        minutes = int(run_minutes_list[i])
        if minutes < 0:
            minutes = 0

        cost = int(minutes) * int(run_index) * int(base_dp_per_minute)
        total_cost += cost
        details.append(
            {
                "run_index": int(run_index),
                "minutes": int(minutes),
                "multiplier": int(run_index),
                "cost": int(cost),
            }
        )

    return {
        "ok": True,
        "chaos_triggered": False,
        "chaos_rule": "TBD",
        "total_cost": int(total_cost),
        "details": details,
    }


def calculate_single_run_cost(
    run_minutes: int,
    run_index: int,
    base_dp_per_minute: int,
    running_at_settlement: bool,
) -> dict:
    # 单次运行成本（第 N 次倍率）
    if running_at_settlement:
        return {
            "ok": True,
            "chaos_triggered": True,
            "chaos_rule": "TBD",
            "total_cost": 0,
            "detail": {
                "run_index": int(run_index),
                "minutes": int(run_minutes),
                "multiplier": int(run_index),
                "cost": 0,
            },
        }

    minutes = int(run_minutes)
    if minutes < 0:
        minutes = 0

    index = int(run_index)
    if index < 1:
        index = 1

    cost = int(minutes) * int(index) * int(base_dp_per_minute)
    return {
        "ok": True,
        "chaos_triggered": False,
        "chaos_rule": "TBD",
        "total_cost": int(cost),
        "detail": {
            "run_index": int(index),
            "minutes": int(minutes),
            "multiplier": int(index),
            "cost": int(cost),
        },
    }
