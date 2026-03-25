import json
import threading
import time
from datetime import datetime
from pathlib import Path


# 项目根目录（ChronOS）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

# 全局状态文件
STATE_FILE = DATA_DIR / "state.json"
STATE_HISTORY_FILE = DATA_DIR / "state_history.jsonl"

# 全局锁，避免并发写文件互相覆盖
STATE_IO_LOCK = threading.Lock()


def now_text() -> str:
    # 统一时间显示格式
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_state_file_exists() -> None:
    # 如果 data/state.json 不存在，就创建默认文件
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        return

    default_state = {"dp": 0, "gp": 0}
    STATE_FILE.write_text(
        json.dumps(default_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_state_history_file_exists() -> None:
    # 如果 data/state_history.jsonl 不存在，就创建空文件
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_HISTORY_FILE.exists():
        return
    STATE_HISTORY_FILE.write_text("", encoding="utf-8")


def load_state() -> dict:
    # 读取 data/state.json
    ensure_state_file_exists()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"dp": 0, "gp": 0}


def write_state(state: dict) -> None:
    # 写回 data/state.json
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_state_history(record: dict) -> None:
    # 追加一条历史记录
    ensure_state_history_file_exists()
    with STATE_HISTORY_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def commit_state_change(
    actor: str,
    note: str,
    data: dict,
    deltas: dict = None,
    sets: dict = None,
) -> dict:
    # 通用状态管理器入口：支持“字段增减”和“字段直接赋值”。
    with STATE_IO_LOCK:
        state = load_state()
        before = {}
        after = {}

        if not isinstance(deltas, dict):
            deltas = {}
        if not isinstance(sets, dict):
            sets = {}

        for key, delta in deltas.items():
            old_value = int(state.get(key, 0) or 0)
            new_value = old_value + int(delta)
            if new_value < 0:
                new_value = 0
            state[key] = int(new_value)
            before[key] = int(old_value)
            after[key] = int(new_value)

        for key, value in sets.items():
            old_value = state.get(key)
            state[key] = value
            before[key] = old_value
            after[key] = value

        if "dp" not in state:
            state["dp"] = 0
        if "gp" not in state:
            state["gp"] = 0

        write_state(state)

        changes = []
        for key in after.keys():
            changes.append(
                {"path": str(key), "from": before.get(key), "to": after.get(key)}
            )

        record = {
            "v": 1,
            "ts": int(time.time()),
            "text": now_text(),
            "type": "state_change",
            "actor": str(actor or "unknown"),
            "note": str(note or ""),
            "data": data if isinstance(data, dict) else {},
            "changes": changes,
        }
        append_state_history(record)

        return {
            "before": before,
            "after": after,
            "changes": changes,
        }
