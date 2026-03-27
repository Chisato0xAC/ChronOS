import csv
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pythoncom
import wmi


# 项目根目录（ChronOS）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 把项目根目录加入模块搜索路径，保证可以 import src.*
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.state.state_manager import calculate_cycle_run_cost
from src.state.state_manager import get_cycle_window
from src.state.state_manager import settle_single_run_cost

DATA_DIR = PROJECT_ROOT / "data"

# 数据文件：只保存监控结果（不保存规则）。
PROCESS_WATCH_STATE_FILE = DATA_DIR / "process_watch.json"

# 规则文件：只保存监控名单（不保存运行结果）。
PROCESS_WATCH_RULES_FILE = PROJECT_ROOT / "config" / "process_watch_rules.json"

# 事件流水和导出文件（都属于数据产物）。
PROCESS_WATCH_EVENTS_FILE = DATA_DIR / "process_watch_events.jsonl"
PROCESS_WATCH_EXPORT_CSV = DATA_DIR / "process_watch_export.csv"

# 当前运行会话快照（给外部程序读取）。
PROCESS_WATCH_ACTIVE_FILE = DATA_DIR / "process_watch_active.json"

# 每分钟写一次“预估扣除 DP”（只预估，不改 DP）。
PROCESS_WATCH_PENDING_DP_FILE = DATA_DIR / "process_watch_pending_dp.json"

# 规则配置：DP 基础值
DEFAULT_BASE_DP_PER_MINUTE = 1


# 内存里的运行会话：
# {"notepad.exe": {1234: 1710000000, 5678: 1710000033}, ...}
ACTIVE_SESSIONS = {}
ACTIVE_SESSIONS_LOCK = threading.Lock()

# 事件采集模式：默认用 WMI；出现配额冲突时自动切换为轮询。
EVENT_CAPTURE_MODE = "wmi"
EVENT_CAPTURE_MODE_LOCK = threading.Lock()
# 轮询线程启用开关：只有切到轮询模式时才会启动。
POLLING_THREAD_ENABLED = False
POLLING_THREAD_ENABLED_LOCK = threading.Lock()


def now_text() -> str:
    # 统一时间显示格式。
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    # 控制台日志：给使用者看当前状态。
    print(f"[{now_text()}] [PROCESS_WATCH] {message}", flush=True)


def is_wmi_quota_conflict_error(error: Exception) -> bool:
    # 判断是否是 WMI 常见的“配额冲突”异常。
    text = str(error)
    if "配额冲突" in text:
        return True
    if "-2147217300" in text:
        return True
    return False


def enable_polling_thread() -> None:
    # 启用轮询线程（只启一次）。
    global POLLING_THREAD_ENABLED
    with POLLING_THREAD_ENABLED_LOCK:
        if POLLING_THREAD_ENABLED:
            return
        POLLING_THREAD_ENABLED = True


def set_event_capture_mode_polling(reason: str) -> None:
    # 切到轮询模式（只切一次，避免重复刷日志）。
    global EVENT_CAPTURE_MODE
    with EVENT_CAPTURE_MODE_LOCK:
        if EVENT_CAPTURE_MODE == "polling":
            return
        EVENT_CAPTURE_MODE = "polling"
    enable_polling_thread()
    log("WMI 监听不可用，已切换为轮询模式: " + str(reason))


def is_polling_mode() -> bool:
    # 读取当前采集模式。
    with EVENT_CAPTURE_MODE_LOCK:
        return EVENT_CAPTURE_MODE == "polling"


def is_polling_thread_enabled() -> bool:
    # 轮询线程是否允许启动。
    with POLLING_THREAD_ENABLED_LOCK:
        return POLLING_THREAD_ENABLED


def list_running_watch_processes() -> dict:
    # 读取当前系统进程快照（只保留监控名单里的进程）。
    watch_list = load_watch_rules()
    watch_set = set(watch_list)
    if len(watch_set) == 0:
        return {}

    result = {}
    try:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            return {}

        rows = completed.stdout.splitlines()
        reader = csv.reader(rows)
        for row in reader:
            # tasklist CSV 一行通常是：映像名,PID,会话名,会话#,内存使用
            if not isinstance(row, list) or len(row) < 2:
                continue

            process_name = str(row[0] or "").strip().lower()
            if process_name not in watch_set:
                continue

            pid_text = str(row[1] or "").strip().replace(",", "")
            try:
                pid = int(pid_text)
            except Exception:
                continue

            if pid <= 0:
                continue

            if process_name not in result:
                result[process_name] = set()
            result[process_name].add(pid)
    except Exception:
        return {}

    return result


def seed_active_sessions_from_snapshot(snapshot: dict) -> None:
    # 轮询模式首次启动时，把“当前已在运行”的进程写入内存会话。
    now_ts = int(time.time())
    changed = False
    with ACTIVE_SESSIONS_LOCK:
        for process_name, pid_set in snapshot.items():
            if not isinstance(pid_set, set):
                continue

            if process_name not in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS[process_name] = {}

            for pid in pid_set:
                if int(pid) not in ACTIVE_SESSIONS[process_name]:
                    ACTIVE_SESSIONS[process_name][int(pid)] = now_ts
                    changed = True

    if changed:
        write_active_sessions_snapshot()


def ensure_process_watch_state_file_exists() -> None:
    # 如果 data/process_watch.json 不存在，就创建默认数据文件。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PROCESS_WATCH_STATE_FILE.exists():
        return

    default_data = {
        "summary": {},
        "updated_ts": 0,
        "updated_text": "",
    }
    PROCESS_WATCH_STATE_FILE.write_text(
        json.dumps(default_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_process_watch_rules_file_exists() -> None:
    # 如果 config/process_watch_rules.json 不存在，就创建默认规则文件。
    PROCESS_WATCH_RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PROCESS_WATCH_RULES_FILE.exists():
        return

    default_rules = {"watch_list": []}
    PROCESS_WATCH_RULES_FILE.write_text(
        json.dumps(default_rules, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_watch_list(watch_list) -> list:
    # 把名单整理成统一格式：小写、去空、去重。
    if not isinstance(watch_list, list):
        return []

    seen = set()
    result = []
    for item in watch_list:
        name = str(item).strip().lower()
        if name == "":
            continue
        if name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def load_watch_rules() -> list:
    # 读取规则文件里的 watch_list。
    ensure_process_watch_rules_file_exists()
    try:
        data = json.loads(PROCESS_WATCH_RULES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return normalize_watch_list(data.get("watch_list", []))
    except Exception:
        pass
    return []


def load_watch_state() -> dict:
    # 读取数据文件；读取失败时给一个可用默认值。
    # 兼容旧格式：如果旧文件里有 watch_list，会迁移到 rules 文件。
    ensure_process_watch_state_file_exists()
    ensure_process_watch_rules_file_exists()

    try:
        data = json.loads(PROCESS_WATCH_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # 兼容旧格式：以前把 watch_list / target_process_name 混在数据文件里。
            if "watch_list" in data or "target_process_name" in data:
                old_watch_list = normalize_watch_list(data.get("watch_list", []))
                if len(old_watch_list) == 0:
                    old_single_name = str(data.get("target_process_name", "")).strip()
                    if old_single_name != "":
                        old_watch_list = normalize_watch_list([old_single_name])

                if len(old_watch_list) > 0:
                    try:
                        rules = json.loads(
                            PROCESS_WATCH_RULES_FILE.read_text(encoding="utf-8")
                        )
                    except Exception:
                        rules = {"watch_list": []}

                    if not isinstance(rules, dict):
                        rules = {"watch_list": []}

                    current_list = normalize_watch_list(rules.get("watch_list", []))
                    if len(current_list) == 0:
                        rules["watch_list"] = old_watch_list
                        PROCESS_WATCH_RULES_FILE.write_text(
                            json.dumps(rules, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )

                data.pop("watch_list", None)
                data.pop("target_process_name", None)

            if "summary" not in data or not isinstance(data.get("summary"), dict):
                data["summary"] = {}
            if "updated_ts" not in data:
                data["updated_ts"] = 0
            if "updated_text" not in data:
                data["updated_text"] = ""
            return data
    except Exception:
        pass

    return {
        "summary": {},
        "updated_ts": 0,
        "updated_text": "",
    }


def save_watch_state(state: dict) -> None:
    # 把最新数据写回 data/process_watch.json。
    PROCESS_WATCH_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_summary_item(summary: dict, process_name: str) -> None:
    # 确保某个进程在 summary 里有完整结构。
    if process_name not in summary or not isinstance(summary.get(process_name), dict):
        summary[process_name] = {
            "is_running": False,
            "active_instance_count": 0,
            "total_seconds": 0,
            "start_count": 0,
            "stop_count": 0,
            "last_start_ts": 0,
            "last_start_text": "",
            "last_stop_ts": 0,
            "last_stop_text": "",
            "last_event": "",
            "cycle_key": "",
            "cycle_run_index": 0,
            "cycle_run_minutes": [],
            "cycle_total_cost": 0,
        }


def ensure_summary_item_cycle_fields(item: dict) -> None:
    # 兼容旧数据：补齐周期统计字段。
    if "cycle_key" not in item:
        item["cycle_key"] = ""
    if "cycle_run_index" not in item:
        item["cycle_run_index"] = 0
    if "cycle_run_minutes" not in item or not isinstance(
        item.get("cycle_run_minutes"), list
    ):
        item["cycle_run_minutes"] = []
    if "cycle_total_cost" not in item:
        item["cycle_total_cost"] = 0


def rollover_cycle_if_needed(item: dict, now_ts: int) -> None:
    # 到新周期时，重置“同周期运行次数/分钟列表/周期成本”。
    ensure_summary_item_cycle_fields(item)
    current_cycle = get_cycle_window(now_ts)
    current_key = str(current_cycle.get("cycle_key", ""))
    if str(item.get("cycle_key", "")) != current_key:
        item["cycle_key"] = current_key
        item["cycle_run_index"] = 0
        item["cycle_run_minutes"] = []
        item["cycle_total_cost"] = 0


def append_event_line(event: dict) -> None:
    # 事件采用 JSONL：每次启动/结束写一行，便于导出和追溯。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with PROCESS_WATCH_EVENTS_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_active_sessions_snapshot() -> None:
    # 把当前活跃会话写入 data/process_watch_active.json。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with ACTIVE_SESSIONS_LOCK:
        snapshot = {}
        for name, items in ACTIVE_SESSIONS.items():
            if not isinstance(items, dict):
                continue
            cleaned = {}
            for pid, start_ts in items.items():
                try:
                    cleaned[int(pid)] = int(start_ts)
                except Exception:
                    continue
            if len(cleaned) > 0:
                snapshot[name] = cleaned

    payload = {
        "updated_ts": int(time.time()),
        "updated_text": now_text(),
        "active": snapshot,
    }
    PROCESS_WATCH_ACTIVE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def calc_running_minutes(start_ts: int, end_ts: int) -> int:
    # 把秒数向上取整到分钟
    if end_ts <= start_ts:
        return 0
    seconds = end_ts - start_ts
    minutes = int(seconds / 60)
    if seconds % 60 != 0:
        minutes = minutes + 1
    return minutes


def export_summary_to_csv(state: dict) -> None:
    # 导出当前汇总到 CSV，方便直接用表格软件打开。
    summary = state.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with PROCESS_WATCH_EXPORT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "process_name",
                "is_running",
                "active_instance_count",
                "total_seconds",
                "total_minutes",
                "start_count",
                "stop_count",
                "last_start_text",
                "last_stop_text",
                "last_event",
                "cycle_key",
                "cycle_run_index",
                "cycle_total_cost",
            ]
        )

        names = sorted(summary.keys())
        for name in names:
            item = summary.get(name, {})
            ensure_summary_item_cycle_fields(item)
            total_seconds = int(item.get("total_seconds", 0) or 0)
            writer.writerow(
                [
                    name,
                    bool(item.get("is_running", False)),
                    int(item.get("active_instance_count", 0) or 0),
                    total_seconds,
                    round(total_seconds / 60.0, 2),
                    int(item.get("start_count", 0) or 0),
                    int(item.get("stop_count", 0) or 0),
                    str(item.get("last_start_text", "")),
                    str(item.get("last_stop_text", "")),
                    str(item.get("last_event", "")),
                    str(item.get("cycle_key", "")),
                    int(item.get("cycle_run_index", 0) or 0),
                    int(item.get("cycle_total_cost", 0) or 0),
                ]
            )


def write_pending_dp_snapshot() -> None:
    # 每分钟生成一次“预估扣除 DP”快照（不修改 state.json）。
    state = load_watch_state()
    summary = state.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    now_ts = int(time.time())
    now_text_value = now_text()
    payload_items = []
    watch_list = load_watch_rules()

    for process_name in sorted(summary.keys()):
        if process_name not in watch_list:
            continue

        item = summary.get(process_name, {})
        ensure_summary_item_cycle_fields(item)
        rollover_cycle_if_needed(item, now_ts)

        run_index = int(item.get("cycle_run_index", 0) or 0) + 1
        active_minutes_list = []

        with ACTIVE_SESSIONS_LOCK:
            active_map = ACTIVE_SESSIONS.get(process_name, {})
            if not isinstance(active_map, dict):
                active_map = {}
            for _, start_ts in active_map.items():
                try:
                    m = calc_running_minutes(int(start_ts), int(now_ts))
                except Exception:
                    m = 0
                if m > 0:
                    active_minutes_list.append(int(m))

        if len(active_minutes_list) == 0:
            continue

        predicted_runs = list(item.get("cycle_run_minutes", []))
        for m in active_minutes_list:
            predicted_runs.append(int(m))

        predicted_cost = calculate_cycle_run_cost(
            run_minutes_list=predicted_runs,
            base_dp_per_minute=DEFAULT_BASE_DP_PER_MINUTE,
            running_at_settlement=False,
        )

        payload_items.append(
            {
                "process_name": process_name,
                "cycle_key": str(item.get("cycle_key", "")),
                "next_run_index": int(run_index),
                "running_instances": len(active_minutes_list),
                "active_minutes_list": active_minutes_list,
                "predicted_run_minutes_list": predicted_runs,
                "predicted_total_cost": int(predicted_cost.get("total_cost", 0) or 0),
                "predicted_details": predicted_cost.get("details", []),
            }
        )

    payload = {
        "updated_ts": int(now_ts),
        "updated_text": now_text_value,
        "cycle": get_cycle_window(now_ts),
        "items": payload_items,
    }
    PROCESS_WATCH_PENDING_DP_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def handle_start_event(process_name: str, pid: int) -> None:
    # 处理“进程启动”事件。
    now_ts = int(time.time())
    now_text_value = now_text()

    watch_list = load_watch_rules()
    if process_name not in watch_list:
        return

    state = load_watch_state()
    summary = state.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    ensure_summary_item(summary, process_name)

    with ACTIVE_SESSIONS_LOCK:
        if process_name not in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[process_name] = {}

        # 同一个 PID 重复启动事件直接忽略。
        if pid in ACTIVE_SESSIONS[process_name]:
            return

        ACTIVE_SESSIONS[process_name][pid] = now_ts
        active_count = len(ACTIVE_SESSIONS[process_name])

    item = summary[process_name]
    ensure_summary_item_cycle_fields(item)
    rollover_cycle_if_needed(item, now_ts)
    item["is_running"] = active_count > 0
    item["active_instance_count"] = active_count
    item["start_count"] = int(item.get("start_count", 0) or 0) + 1
    item["last_start_ts"] = now_ts
    item["last_start_text"] = now_text_value
    item["last_event"] = f"start pid={pid}"

    state["summary"] = summary
    state["updated_ts"] = now_ts
    state["updated_text"] = now_text_value
    save_watch_state(state)

    event = {
        "type": "start",
        "ts": now_ts,
        "text": now_text_value,
        "process_name": process_name,
        "pid": int(pid),
    }
    append_event_line(event)
    write_active_sessions_snapshot()
    export_summary_to_csv(state)
    log(f"启动: {process_name} pid={pid}")


def handle_stop_event(process_name: str, pid: int) -> None:
    # 处理“进程结束”事件。
    now_ts = int(time.time())
    now_text_value = now_text()

    watch_list = load_watch_rules()
    if process_name not in watch_list:
        return

    state = load_watch_state()
    summary = state.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    ensure_summary_item(summary, process_name)

    session_seconds = 0
    with ACTIVE_SESSIONS_LOCK:
        if process_name not in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[process_name] = {}

        start_ts = ACTIVE_SESSIONS[process_name].pop(pid, 0)
        if start_ts > 0 and now_ts >= start_ts:
            session_seconds = now_ts - start_ts

        active_count = len(ACTIVE_SESSIONS[process_name])

    item = summary[process_name]
    ensure_summary_item_cycle_fields(item)
    rollover_cycle_if_needed(item, now_ts)
    total_seconds = int(item.get("total_seconds", 0) or 0) + int(session_seconds)
    item["total_seconds"] = total_seconds
    item["is_running"] = active_count > 0
    item["active_instance_count"] = active_count
    item["stop_count"] = int(item.get("stop_count", 0) or 0) + 1
    item["last_stop_ts"] = now_ts
    item["last_stop_text"] = now_text_value
    item["last_event"] = f"stop pid={pid} session_seconds={session_seconds}"

    state["summary"] = summary
    state["updated_ts"] = now_ts
    state["updated_text"] = now_text_value
    save_watch_state(state)

    event = {
        "type": "stop",
        "ts": now_ts,
        "text": now_text_value,
        "process_name": process_name,
        "pid": int(pid),
        "session_seconds": int(session_seconds),
    }
    append_event_line(event)
    write_active_sessions_snapshot()
    export_summary_to_csv(state)
    log(f"结束: {process_name} pid={pid} session_seconds={session_seconds}")

    # 按 Cycle Run Cost Rule 结算 DP（只在 stop 事件后）
    session_minutes = calc_running_minutes(int(now_ts - session_seconds), int(now_ts))
    if session_minutes > 0:
        run_index = int(item.get("cycle_run_index", 0) or 0) + 1
        settle_single_run_cost(
            actor="process_watch",
            run_minutes=int(session_minutes),
            run_index=int(run_index),
            base_dp_per_minute=DEFAULT_BASE_DP_PER_MINUTE,
            running_at_settlement=False,
            note="进程监控结算",
            extra_data={
                "process_name": process_name,
                "pid": int(pid),
                "session_seconds": int(session_seconds),
                "cycle": get_cycle_window(now_ts),
            },
        )

        # 更新周期内倍率统计（凌晨 4 点到次日凌晨 4 点）。
        item["cycle_run_index"] = int(run_index)
        run_minutes_list = item.get("cycle_run_minutes", [])
        if not isinstance(run_minutes_list, list):
            run_minutes_list = []
        run_minutes_list.append(int(session_minutes))
        item["cycle_run_minutes"] = run_minutes_list

        total_cost = 0
        for i in range(len(run_minutes_list)):
            idx = i + 1
            minutes = int(run_minutes_list[i])
            if minutes < 0:
                minutes = 0
            total_cost += int(minutes) * int(idx) * int(DEFAULT_BASE_DP_PER_MINUTE)
        item["cycle_total_cost"] = int(total_cost)

        state["summary"] = summary
        state["updated_ts"] = now_ts
        state["updated_text"] = now_text_value
        save_watch_state(state)


def pending_dp_loop() -> None:
    # 每分钟更新一次预估扣除 DP（只写预估文件）。
    while True:
        try:
            write_pending_dp_snapshot()
        except Exception as e:
            log(f"预估扣除 DP 更新失败: {e}")
        time.sleep(60)


def polling_listener_loop() -> None:
    # 轮询模式：每 5 秒比较一次进程快照，补发 start/stop 事件。
    # 说明：这是 WMI 不可用时的降级方案，目标是“功能可用，不再刷异常日志”。
    while True:
        if not is_polling_thread_enabled():
            time.sleep(1)
            continue

        poll_interval_seconds = 5
        previous_snapshot = list_running_watch_processes()
        seed_active_sessions_from_snapshot(previous_snapshot)
        log("轮询模式已启动（每 5 秒扫描一次）")

        while True:
            if not is_polling_thread_enabled():
                break

            try:
                current_snapshot = list_running_watch_processes()
                names = set(previous_snapshot.keys()) | set(current_snapshot.keys())

                for process_name in names:
                    previous_pids = previous_snapshot.get(process_name, set())
                    current_pids = current_snapshot.get(process_name, set())

                    started = current_pids - previous_pids
                    stopped = previous_pids - current_pids

                    for pid in started:
                        handle_start_event(process_name, int(pid))

                    for pid in stopped:
                        handle_stop_event(process_name, int(pid))

                previous_snapshot = current_snapshot
            except Exception as e:
                log(f"轮询监听异常（将继续重试）: {e}")

            time.sleep(poll_interval_seconds)


def process_start_listener_loop() -> None:
    # 事件驱动：监听“进程启动”。
    # WMI 在子线程里使用前，需要先初始化 COM。
    while True:
        if is_polling_mode():
            time.sleep(1)
            continue

        pythoncom.CoInitialize()
        try:
            c = wmi.WMI()
            watcher = c.Win32_Process.watch_for("creation")

            while True:
                if is_polling_mode():
                    break

                p = watcher()
                name = str(getattr(p, "Name", "") or "").strip().lower()
                pid = int(getattr(p, "ProcessId", 0) or 0)
                if name == "" or pid <= 0:
                    continue
                handle_start_event(name, pid)
        except Exception as e:
            if is_wmi_quota_conflict_error(e):
                set_event_capture_mode_polling(str(e))
            else:
                log(f"启动监听异常，3 秒后重试: {e}")
                time.sleep(3)
        finally:
            pythoncom.CoUninitialize()


def process_stop_listener_loop() -> None:
    # 事件驱动：监听“进程结束”。
    # 出现配额冲突时会切换到轮询模式，不再持续刷异常。
    while True:
        if is_polling_mode():
            time.sleep(1)
            continue

        pythoncom.CoInitialize()
        try:
            c = wmi.WMI()
            watcher = c.Win32_Process.watch_for("deletion")

            while True:
                if is_polling_mode():
                    break

                p = watcher()
                name = str(getattr(p, "Name", "") or "").strip().lower()
                pid = int(getattr(p, "ProcessId", 0) or 0)
                if name == "" or pid <= 0:
                    continue
                handle_stop_event(name, pid)
        except Exception as e:
            if is_wmi_quota_conflict_error(e):
                set_event_capture_mode_polling(str(e))
            else:
                log(f"结束监听异常，3 秒后重试: {e}")
                time.sleep(3)
        finally:
            pythoncom.CoUninitialize()


def main() -> int:
    # 入口：事件驱动监听（不使用轮询）。
    log("进程监控程序已启动（事件驱动）")
    ensure_process_watch_state_file_exists()
    ensure_process_watch_rules_file_exists()

    # 启动时先导出一次当前汇总（即使还没事件，也能看到表头文件）。
    state = load_watch_state()
    export_summary_to_csv(state)
    write_active_sessions_snapshot()
    write_pending_dp_snapshot()

    t1 = threading.Thread(target=process_start_listener_loop, daemon=True)
    t2 = threading.Thread(target=process_stop_listener_loop, daemon=True)
    t3 = threading.Thread(target=pending_dp_loop, daemon=True)
    t1.start()
    t2.start()
    t3.start()

    # 轮询线程默认不启动，只有 WMI 失效时才启用。
    t4 = threading.Thread(target=polling_listener_loop, daemon=True)
    t4.start()

    while True:
        # 主线程只保活。
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
