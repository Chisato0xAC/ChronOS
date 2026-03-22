import csv
import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pythoncom
import wmi


# 项目根目录（ChronOS）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

# 数据文件：只保存监控结果（不保存规则）。
PROCESS_WATCH_STATE_FILE = DATA_DIR / "process_watch.json"

# 规则文件：只保存监控名单（不保存运行结果）。
PROCESS_WATCH_RULES_FILE = PROJECT_ROOT / "config" / "process_watch_rules.json"

# 事件流水和导出文件（都属于数据产物）。
PROCESS_WATCH_EVENTS_FILE = DATA_DIR / "process_watch_events.jsonl"
PROCESS_WATCH_EXPORT_CSV = DATA_DIR / "process_watch_export.csv"


# 内存里的运行会话：
# {"notepad.exe": {1234: 1710000000, 5678: 1710000033}, ...}
ACTIVE_SESSIONS = {}
ACTIVE_SESSIONS_LOCK = threading.Lock()


def now_text() -> str:
    # 统一时间显示格式。
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    # 控制台日志：给使用者看当前状态。
    print(f"[{now_text()}] [PROCESS_WATCH] {message}", flush=True)


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
        }


def append_event_line(event: dict) -> None:
    # 事件采用 JSONL：每次启动/结束写一行，便于导出和追溯。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with PROCESS_WATCH_EVENTS_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


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
            ]
        )

        names = sorted(summary.keys())
        for name in names:
            item = summary.get(name, {})
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
                ]
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
    export_summary_to_csv(state)
    log(f"结束: {process_name} pid={pid} session_seconds={session_seconds}")


def process_start_listener_loop() -> None:
    # 事件驱动：监听“进程启动”。
    # WMI 在子线程里使用前，需要先初始化 COM。
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        watcher = c.Win32_Process.watch_for("creation")

        while True:
            p = watcher()
            name = str(getattr(p, "Name", "") or "").strip().lower()
            pid = int(getattr(p, "ProcessId", 0) or 0)
            if name == "" or pid <= 0:
                continue
            handle_start_event(name, pid)
    finally:
        pythoncom.CoUninitialize()


def process_stop_listener_loop() -> None:
    # 事件驱动：监听“进程结束”。
    # WMI 在子线程里使用前，需要先初始化 COM。
    pythoncom.CoInitialize()
    try:
        c = wmi.WMI()
        watcher = c.Win32_Process.watch_for("deletion")

        while True:
            p = watcher()
            name = str(getattr(p, "Name", "") or "").strip().lower()
            pid = int(getattr(p, "ProcessId", 0) or 0)
            if name == "" or pid <= 0:
                continue
            handle_stop_event(name, pid)
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

    t1 = threading.Thread(target=process_start_listener_loop, daemon=True)
    t2 = threading.Thread(target=process_stop_listener_loop, daemon=True)
    t1.start()
    t2.start()

    while True:
        # 主线程只保活。
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
