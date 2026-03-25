from src.state.state_rules import calculate_cycle_run_cost
from src.state.state_rules import calculate_single_run_cost
from src.state.state_rules import get_cycle_window
from src.state.state_store import commit_state_change


def settle_single_run_cost(
    actor: str,
    run_minutes: int,
    run_index: int,
    base_dp_per_minute: int = 1,
    running_at_settlement: bool = False,
    note: str = "",
    extra_data: dict = None,
) -> dict:
    # 把单次运行结算结果写入全局状态（当前只改 dp）。
    cost = calculate_single_run_cost(
        run_minutes=run_minutes,
        run_index=run_index,
        base_dp_per_minute=base_dp_per_minute,
        running_at_settlement=running_at_settlement,
    )

    data = {
        "run_minutes": int(run_minutes),
        "run_index": int(run_index),
        "base_dp_per_minute": int(base_dp_per_minute),
        "running_at_settlement": bool(running_at_settlement),
        "detail": cost.get("detail", {}),
        "total_cost": int(cost.get("total_cost", 0) or 0),
        "chaos_triggered": bool(cost.get("chaos_triggered", False)),
        "chaos_rule": str(cost.get("chaos_rule", "")),
    }
    if isinstance(extra_data, dict):
        for k, v in extra_data.items():
            data[k] = v

    result = commit_state_change(
        actor=actor,
        note=note,
        data=data,
        deltas={"dp": -int(data.get("total_cost", 0) or 0)},
    )
    result["cost"] = cost
    return result
