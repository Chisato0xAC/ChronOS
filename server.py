import json
import queue
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta
from pathlib import Path

from chronos_config import (
    DAY_BOUNDARY_HOUR,
    DAY_BOUNDARY_MINUTE,
    DAY_BOUNDARY_SECOND,
)


# 这个路径指向前端目录。
SRC_DIR = Path(__file__).resolve().parent / "src"
# 这个路径指向根目录 data 文件夹。
DATA_DIR = Path(__file__).resolve().parent / "data"
# 这个路径指向项目里的状态文件，用来保存 DP 和 GP。
STATE_FILE = DATA_DIR / "state.json"

# 这个路径指向状态历史记录文件（JSON Lines：一行一条 JSON）。
# 注意：这里只记录 data/state.json 的变化，不记录爬虫状态。
STATE_HISTORY_FILE = DATA_DIR / "state_history.jsonl"

# 这个列表保存所有 SSE 连接（前端会连过来等待“状态已变化”的通知）。
SSE_CLIENT_QUEUES = []
SSE_CLIENT_QUEUES_LOCK = threading.Lock()

# 写 state.json / state_history.jsonl / crawler_state.json 时用同一把锁，避免并发写坏文件。
STATE_IO_LOCK = threading.Lock()

# 这些异常通常表示“客户端断开了连接”，属于正常情况。
DISCONNECT_ERRORS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)

# 爬虫运行状态文件（爬虫脚本读写）。
CRAWLER_STATE_FILE = DATA_DIR / "crawler_state.json"

# 爬虫脚本路径（工具脚本，由主程序按时间触发）
CRAWLER_SCRIPT = Path(__file__).resolve().parent / "src" / "crawler" / "bilibili.py"
CRAWLER_AUTH_FILE = DATA_DIR / "bilibili_auth.json"

# 自定义扩展规则目录（用户可以在这里放 JSON 规则文件）
EXT_RULES_DIR = Path(__file__).resolve().parent / "extensions" / "rules"

# git hooks 模板目录（项目自带）。
GITHOOKS_TEMPLATES_DIR = Path(__file__).resolve().parent / "tools" / "githooks"

# 一天的分界线：统一在 chronos_config.py 配置


def ensure_utf8_stdio() -> None:
    # Windows 下 stdout/stderr 被重定向到文件时，编码容易变成系统默认编码，
    # 导致 logs/server.out.log 里的中文显示为乱码。
    # 这里强制把输出编码设为 UTF-8。
    try:
        # typing/LSP 可能不认识 reconfigure，但 CPython 3.7+ 的 TextIOWrapper 有。
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def log(message: str) -> None:
    # 统一的日志输出：
    # - 无论 stdout 是否被重定向到文件，都强制 flush
    # - 这样 ChronOS.vbs 的 server.out.log 能实时看到输出
    # 额外加上时间戳，方便你回看时知道“什么时候发生的”。
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_text}] {message}", flush=True)


def log_error(message: str) -> None:
    # 错误日志：写到 stderr，并强制 flush
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_text}] [ERROR] {message}", file=sys.stderr, flush=True)


# 如果 data/state.json 不存在，就创建一个默认文件。
# 这样用户第一次运行项目时，不需要手动新建 data 文件夹。
def ensure_state_file_exists():
    # 第一步：确保 data/ 文件夹存在。
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 第二步：如果 state.json 已存在，就什么都不做。
    if STATE_FILE.exists():
        return

    # 第三步：写入一个最简单的默认状态。
    # 注意：state.json 只保存“当前数值状态”（例如 dp/gp），不存爬虫运行状态。
    default_state = {"dp": 0, "gp": 0}
    STATE_FILE.write_text(
        json.dumps(default_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_state_history_file_exists() -> None:
    # 如果 data/state_history.jsonl 不存在，就创建一个空文件。
    # 这个文件采用 JSONL：每一行都是一条 JSON 记录。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_HISTORY_FILE.exists():
        return
    STATE_HISTORY_FILE.write_text("", encoding="utf-8")


def append_state_history(event_type: str, changes: list, note: str = "") -> None:
    # 追加一条 state 变更历史。
    # - 只负责写一行 JSON，不修改旧记录（可追溯）
    # - changes 的格式：[{"path": "dp", "from": 1, "to": 2}]
    # - data 用于补充上下文（例如 undo_of_ts）

    return append_state_history_with_data(
        event_type=event_type, changes=changes, note=note, data={}
    )


def append_state_history_with_data(
    event_type: str, changes: list, note: str, data: dict, actor: str = "server"
) -> None:
    # 和 append_state_history 一样，但允许写入 data / actor。
    ensure_state_history_file_exists()

    ts = int(time.time())
    text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "v": 1,
        "ts": ts,
        "text": text,
        "type": event_type,
        "actor": actor,
        "note": note,
        "data": data,
        "changes": changes,
    }

    # JSONL：每条记录一行，方便追加写入。
    with STATE_HISTORY_FILE.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_extension_rules() -> list:
    # 读取 extensions/rules/*.json 里的规则。
    # 0.0.5 第二步：只负责读取并返回，不做任何 DP 修改。
    rules = []

    try:
        if not EXT_RULES_DIR.exists() or not EXT_RULES_DIR.is_dir():
            return []

        for file_path in sorted(EXT_RULES_DIR.glob("*.json")):
            try:
                raw = file_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, dict):
                    data["_file"] = str(file_path)
                    rules.append(data)
            except Exception:
                # 单个规则文件坏了就跳过，不影响主服务。
                continue
    except Exception:
        return []

    return rules


def match_rules_for_event(rules: list, event_name: str, event_data: dict) -> list:
    # 找出命中的规则。
    # 0.0.5 第二步：只做匹配，不做 DP 修改。
    matched = []
    if not isinstance(rules, list):
        return []
    if not isinstance(event_data, dict):
        event_data = {}

    for rule in rules:
        if not isinstance(rule, dict):
            continue

        rule_event = rule.get("event", "")
        if str(rule_event) != str(event_name):
            continue

        # tag_regex：只有当事件 data 里提供 tag 时才匹配。
        tag_regex = rule.get("tag_regex", "")
        if isinstance(tag_regex, str) and tag_regex.strip() != "":
            tag_value = str(event_data.get("tag", ""))
            if tag_value.strip() == "":
                continue
            try:
                if re.match(tag_regex, tag_value) is None:
                    continue
            except Exception:
                # 正则写错就当不匹配。
                continue

        matched.append(rule)

    return matched


def ensure_git_hooks_installed() -> None:
    # 自动安装 git hooks（只做一次复制，失败也不影响主服务）。
    # 目的：让“git commit / git tag”能全自动触发 ChronOS 的规则系统。
    # 注意：.git/hooks 目录不会被 git 提交，所以需要在本机安装。

    try:
        repo_root = Path(__file__).resolve().parent
        git_dir = repo_root / ".git"
        if not git_dir.exists() or not git_dir.is_dir():
            return

        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)

        # 我们只安装这两个 hook：
        # - post-commit：提交后触发
        # - reference-transaction：创建 tag 时触发（如果 git 版本支持）
        hook_names = ["post-commit", "reference-transaction"]
        installed_any = False

        for name in hook_names:
            src = GITHOOKS_TEMPLATES_DIR / name
            dst = hooks_dir / name

            if not src.exists() or not src.is_file():
                continue

            try:
                src_bytes = src.read_bytes()
                if dst.exists() and dst.is_file():
                    try:
                        if dst.read_bytes() == src_bytes:
                            continue
                    except Exception:
                        # 读失败就覆盖写。
                        pass

                dst.write_bytes(src_bytes)
                installed_any = True
            except Exception:
                # 单个 hook 写失败就跳过。
                continue

        if installed_any:
            log("已自动安装 git hooks（.git/hooks）")
    except Exception:
        # 安装失败不应影响主服务启动。
        return


def write_json_atomic(file_path: Path, obj: dict) -> None:
    # 原子写入：先写临时文件，再替换原文件，避免写到一半程序中断导致文件损坏。
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(file_path)


def read_state_file() -> dict:
    # 读取 data/state.json。
    # 这个函数尽量保证：即使文件不存在/字段缺失，也能返回一个可用的 dict。
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                return state
        except Exception:
            pass
    return {"dp": 0, "gp": 0}


def read_crawler_state_file() -> dict:
    # 读取 data/crawler_state.json。
    ensure_crawler_state_file_exists()
    try:
        data = json.loads(CRAWLER_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def write_crawler_state_file(crawler_state: dict) -> None:
    # 写回 data/crawler_state.json。
    if not isinstance(crawler_state, dict):
        crawler_state = {}
    write_json_atomic(CRAWLER_STATE_FILE, crawler_state)


def history_has_pending_dp_id(pending_dp_id: str) -> bool:
    # 防止重复应用同一个 pending_dp_id。
    # 简单做法：从历史文件末尾往前扫，找到匹配就返回 True。
    if not pending_dp_id:
        return False
    if not STATE_HISTORY_FILE.exists():
        return False

    try:
        lines = STATE_HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except Exception:
            continue

        if not isinstance(record, dict):
            continue

        data = record.get("data")
        if not isinstance(data, dict):
            continue

        if str(data.get("pending_dp_id", "")) == pending_dp_id:
            return True

    return False


def history_has_rule_event_id(event_id: str) -> bool:
    # 用于扩展规则的“去重”：同一个 event_id 只允许处理一次。
    # 0.0.5 第三步前置：先把检查逻辑准备好（本步仍不修改 DP）。
    if not event_id:
        return False
    if not STATE_HISTORY_FILE.exists():
        return False

    try:
        lines = STATE_HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return False

    # 从末尾往前扫：通常最新记录在最后，速度更快。
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except Exception:
            continue

        if not isinstance(record, dict):
            continue

        if str(record.get("type", "")) != "rule_apply":
            continue

        data = record.get("data")
        if not isinstance(data, dict):
            continue

        if str(data.get("event_id", "")) == str(event_id):
            return True

    return False


def try_apply_pending_crawler_changes() -> None:
    # 接入爬虫修改：把 crawler_state.json 里的 pending_dp_* 正式应用到 state.json。
    # 未来扩展方向：把 pending_dp_* 改成 pending_events 数组，再在这里统一处理。

    crawler_state = read_crawler_state_file()
    pending_status = str(crawler_state.get("pending_dp_status", "")).strip()
    if pending_status != "pending":
        return

    pending_dp_id = str(crawler_state.get("pending_dp_id", "")).strip()
    if not pending_dp_id:
        return

    dp_delta = int(crawler_state.get("pending_dp_delta", 0) or 0)

    with STATE_IO_LOCK:
        # 双保险：如果历史里已经有这个 pending_dp_id，就不要重复应用。
        if history_has_pending_dp_id(pending_dp_id):
            crawler_state["pending_dp_status"] = "applied"
            crawler_state["pending_dp_applied_note"] = "already_in_history"
            crawler_state["pending_dp_applied_ts"] = int(time.time())
            crawler_state["pending_dp_applied_text"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            write_crawler_state_file(crawler_state)
            return

        state = read_state_file()
        old_dp = int(state.get("dp", 0) or 0)

        new_dp = old_dp + dp_delta
        if new_dp < 0:
            new_dp = 0

        # 先把 crawler_state 标记为已应用（即使 new_dp 没变化，也算处理过）。
        crawler_state["pending_dp_status"] = "applied"
        crawler_state["pending_dp_applied_ts"] = int(time.time())
        crawler_state["pending_dp_applied_text"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        crawler_state["pending_dp_applied_old_dp"] = int(old_dp)
        crawler_state["pending_dp_applied_new_dp"] = int(new_dp)

        if new_dp != old_dp:
            state["dp"] = int(new_dp)
            if "gp" not in state:
                state["gp"] = 0

            write_json_atomic(STATE_FILE, state)

            append_state_history_with_data(
                event_type="crawler_dp_apply",
                actor="crawler",
                note="接入爬虫扣除",
                data={
                    "pending_dp_id": pending_dp_id,
                    "pending_dp_reason": str(
                        crawler_state.get("pending_dp_reason", "")
                    ),
                    "pending_dp_trigger_ts": int(
                        crawler_state.get("pending_dp_trigger_ts", 0) or 0
                    ),
                    "pending_dp_window_start_ts": int(
                        crawler_state.get("pending_dp_window_start_ts", 0) or 0
                    ),
                    "pending_dp_window_end_ts": int(
                        crawler_state.get("pending_dp_window_end_ts", 0) or 0
                    ),
                    "pending_dp_delta": int(dp_delta),
                },
                changes=[{"path": "dp", "from": old_dp, "to": int(new_dp)}],
            )

        write_crawler_state_file(crawler_state)

    # 通知前端刷新（不需要等 watcher）。
    sse_broadcast("state", {"reason": "crawler_applied"})


def apply_crawler_pending_changes_once() -> None:
    # 包一层 try/except，避免爬虫对接的异常影响主服务。
    try:
        try_apply_pending_crawler_changes()
    except Exception as e:
        log_error(f"接入爬虫修改失败: {e}")


def get_value_by_path(obj: dict, path: str):
    # 通过点号路径读取值，例如："inventory.potion_small"。
    cur = obj
    parts = str(path).split(".")
    for i in range(len(parts)):
        key = parts[i]
        if not isinstance(cur, dict):
            return None
        if key not in cur:
            return None
        cur = cur[key]
    return cur


def set_value_by_path(obj: dict, path: str, value) -> None:
    # 通过点号路径写入值。
    # - 如果中间层级不存在，会自动创建 dict。
    parts = str(path).split(".")
    cur = obj
    for i in range(len(parts) - 1):
        key = parts[i]
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[parts[-1]] = value


def find_latest_undoable_history_record():
    # 找到最近一条“可以撤销”的历史记录。
    # 简单规则：
    # - type == undo 的记录本身不可撤销
    # - 如果某条记录已经被 undo_of_ts 指向过，就跳过（避免重复撤销同一条）
    if not STATE_HISTORY_FILE.exists():
        return None

    try:
        lines = STATE_HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    undone_ts = set()

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line == "":
            continue

        try:
            record = json.loads(line)
        except Exception:
            continue

        if not isinstance(record, dict):
            continue

        record_type = record.get("type")

        if record_type == "undo":
            data = record.get("data")
            if isinstance(data, dict):
                undo_of_ts = data.get("undo_of_ts")
                if isinstance(undo_of_ts, int):
                    undone_ts.add(undo_of_ts)
            continue

        ts = record.get("ts")
        if isinstance(ts, int) and ts in undone_ts:
            continue

        changes = record.get("changes")
        if isinstance(changes, list) and len(changes) > 0:
            return record

    return None


def sse_broadcast(event_name: str, data: dict) -> None:
    # 把一条事件广播给所有在线的 SSE 客户端。
    # SSE 协议格式：
    # event: <name>\n
    # data: <json>\n
    # \n
    message = (
        "event: "
        + str(event_name)
        + "\n"
        + "data: "
        + json.dumps(data, ensure_ascii=False)
        + "\n\n"
    )

    with SSE_CLIENT_QUEUES_LOCK:
        queues = list(SSE_CLIENT_QUEUES)

    for q in queues:
        try:
            q.put_nowait(message)
        except Exception:
            # 队列满/异常就跳过，避免影响主流程。
            pass


def state_file_watcher_loop() -> None:
    # 监控 data/state.json 的“文件修改时间”。
    # 一旦外部（爬虫/手动修改/其他程序）改了 state.json，就广播一条事件给前端。
    last_mtime = None

    while True:
        try:
            if STATE_FILE.exists():
                mtime = STATE_FILE.stat().st_mtime
                if last_mtime is None:
                    last_mtime = mtime
                elif mtime != last_mtime:
                    last_mtime = mtime
                    sse_broadcast("state", {"reason": "file_changed"})
        except Exception as e:
            log_error(f"监控 state.json 失败: {e}")

        # 这里用很短的 sleep，只在服务端做轮询。
        time.sleep(0.5)


def ensure_crawler_state_file_exists() -> None:
    # 确保 data/crawler_state.json 存在。
    # 这个文件只给爬虫脚本写入/读取；主服务端不主动修改其内容。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CRAWLER_STATE_FILE.exists():
        return
    CRAWLER_STATE_FILE.write_text(
        json.dumps({}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_next_trigger_time(now: datetime) -> datetime:
    # 返回下一次要触发爬取的时间点（4:00）。
    today_4am = now.replace(
        hour=DAY_BOUNDARY_HOUR,
        minute=DAY_BOUNDARY_MINUTE,
        second=DAY_BOUNDARY_SECOND,
        microsecond=0,
    )
    if now < today_4am:
        return today_4am
    return today_4am + timedelta(days=1)


def run_crawler_once() -> None:
    # 启动一次爬虫脚本。
    # 这个脚本会自己判断“今天窗口是否已爬取”，所以重复启动也不会重复爬取。
    # 但为了避免“每次程序启动都启动一次爬虫进程”，这里先读取 data/crawler_state.json
    # 做一次轻量判断：只有确实需要爬取时才启动爬虫脚本。
    if not CRAWLER_SCRIPT.exists():
        log_error(f"Crawler script not found: {CRAWLER_SCRIPT}")
        return

    # 计算“最近一个已完成日”的触发点时间（默认就是每天 4:00）。
    # - 例如：现在是 10:00，则触发点是今天 4:00
    # - 例如：现在是 02:00，则触发点是昨天 4:00
    now = datetime.now()
    today_4am = now.replace(
        hour=DAY_BOUNDARY_HOUR,
        minute=DAY_BOUNDARY_MINUTE,
        second=DAY_BOUNDARY_SECOND,
        microsecond=0,
    )
    if now >= today_4am:
        latest_completed_trigger = today_4am
    else:
        latest_completed_trigger = today_4am - timedelta(days=1)

    # 如果 crawler_state 里已经记录过这个触发点，就说明“今天窗口已经爬过了”。
    try:
        crawler_state = read_crawler_state_file()
        last_trigger_ts = int(crawler_state.get("last_trigger_ts", 0) or 0)
        if last_trigger_ts == int(latest_completed_trigger.timestamp()):
            last_text = str(crawler_state.get("last_trigger_text", "")).strip()
            if last_text:
                log(f"调度器：今天窗口已爬取（触发点 {last_text}），跳过启动爬虫")
            else:
                log("调度器：今天窗口已爬取，跳过启动爬虫")
            return
    except Exception:
        # 读取失败就不拦截，让爬虫脚本自己判断（保证稳健）。
        pass

    # 如果 auth 文件存在，但 sessdata 为空，就不反复启动爬虫。
    # （第一次没有文件时仍允许启动：爬虫会自动生成模板文件）
    if CRAWLER_AUTH_FILE.exists():
        try:
            auth = json.loads(CRAWLER_AUTH_FILE.read_text(encoding="utf-8"))
            sessdata = str(auth.get("sessdata", "")).strip()
            if not sessdata:
                log("调度器：爬虫工具未配置 sessdata，跳过")
                return
        except Exception:
            # auth 文件坏了，就让爬虫自己报错（方便用户发现问题）
            pass

    try:
        log("准备启动爬虫脚本...")
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "-u", str(CRAWLER_SCRIPT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if proc.stdout:
            log(proc.stdout.strip())
        if proc.returncode != 0:
            if proc.stderr:
                log_error(proc.stderr.strip())
            log_error(f"爬虫脚本退出码: {proc.returncode}")
            return

        # 爬虫脚本成功退出后，尝试把 pending_dp_* 正式应用到 state.json。
        apply_crawler_pending_changes_once()
    except Exception as e:
        log_error(f"启动爬虫脚本失败: {e}")


def crawler_scheduler_loop() -> None:
    # 这是一个后台循环：
    # 1) 主程序启动时先检查一次：只有“需要补爬”才会启动爬虫
    # 2) 然后每天到 4:00 再跑一次
    log("调度器：检测爬虫状态")

    try:
        run_crawler_once()
    except Exception as e:
        log_error(f"调度器：爬虫启动检查失败: {e}")

    next_trigger = get_next_trigger_time(datetime.now())
    log(f"调度器：下一次爬虫触发时间 {next_trigger.strftime('%Y-%m-%d %H:%M:%S')}")
    while True:
        now = datetime.now()

        if now < next_trigger:
            wait_seconds = (next_trigger - now).total_seconds()
            time.sleep(min(wait_seconds, 60))
            continue

        # 到点（或略过）了，执行一次
        log("调度器：到达触发时间 4:00，启动爬虫工具")
        try:
            run_crawler_once()
        except Exception as e:
            log_error(f"调度器：定时启动爬虫失败: {e}")

        # 下一次触发：再加 1 天
        next_trigger = next_trigger + timedelta(days=1)
        log(f"调度器：下一次爬虫触发时间 {next_trigger.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(1)


# 这个处理器只负责一个接口：保存 DP 到 JSON 文件。
class SaveDpHandler(BaseHTTPRequestHandler):
    # 这里处理浏览器的 GET 请求，用来返回页面和脚本文件。
    def do_GET(self):
        # /api/state-history：返回最近的 state 历史记录（用于前端展示）。
        if self.path.startswith("/api/state-history"):
            try:
                # limit 默认 50，最大 200。
                limit = 50
                if "?" in self.path:
                    query = self.path.split("?", 1)[1]
                    parts = query.split("&")
                    for p in parts:
                        if p.startswith("limit="):
                            raw = p.split("=", 1)[1]
                            try:
                                limit = int(raw)
                            except Exception:
                                limit = 50

                if limit < 1:
                    limit = 1
                if limit > 200:
                    limit = 200

                items = []
                undone_ts = set()
                if STATE_HISTORY_FILE.exists():
                    # 直接按行读取（JSONL）
                    lines = STATE_HISTORY_FILE.read_text(encoding="utf-8").splitlines()

                    # 从最新开始往前扫：
                    # - 遇到 undo：记录 undo_of_ts，并且不把 undo 本身放进 items
                    # - 遇到普通记录：如果它的 ts 在 undone_ts 里，说明已被撤销，跳过
                    # - 最终只返回“当前仍有效”的历史记录
                    for i in range(len(lines) - 1, -1, -1):
                        raw = lines[i].strip()
                        if raw == "":
                            continue

                        try:
                            record = json.loads(raw)
                        except Exception:
                            continue

                        if not isinstance(record, dict):
                            continue

                        record_type = record.get("type")
                        if record_type == "undo":
                            data = record.get("data")
                            if isinstance(data, dict):
                                undo_of_ts = data.get("undo_of_ts")
                                if isinstance(undo_of_ts, int):
                                    undone_ts.add(undo_of_ts)
                            continue

                        ts = record.get("ts")
                        if isinstance(ts, int) and ts in undone_ts:
                            continue

                        items.append(record)
                        if len(items) >= limit:
                            break

                response_body = json.dumps(
                    {"ok": True, "items": items, "limit": limit},
                    ensure_ascii=False,
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
                return
            except Exception as e:
                log_error(f"读取历史记录失败: {e}")
                self.send_response(500)
                self.end_headers()
                return

        # SSE：前端连接这个接口，等待“state 变化”的通知。
        if self.path == "/api/state-events":
            q = None
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                # 每个连接一个队列，用于接收广播消息。
                q = queue.Queue(maxsize=50)
                with SSE_CLIENT_QUEUES_LOCK:
                    SSE_CLIENT_QUEUES.append(q)

                def safe_write(raw_text: str) -> bool:
                    # 安全写入：如果客户端断开连接，就返回 False。
                    try:
                        self.wfile.write(raw_text.encode("utf-8"))
                        self.wfile.flush()
                        return True
                    except DISCONNECT_ERRORS:
                        return False

                # 先发一条注释行，避免某些代理缓冲。
                if not safe_write(": connected\n\n"):
                    return

                while True:
                    try:
                        msg = q.get(timeout=15)
                        if not safe_write(msg):
                            break
                    except queue.Empty:
                        # 心跳：保持连接不断。
                        if not safe_write(": keepalive\n\n"):
                            break
            except DISCONNECT_ERRORS:
                # 手机锁屏/切后台时，经常会强制断开连接：这是正常情况。
                pass
            except Exception as e:
                # 其他异常才需要打印，便于排查。
                log_error(f"SSE 连接处理失败: {e}")
            finally:
                try:
                    with SSE_CLIENT_QUEUES_LOCK:
                        if q is not None and q in SSE_CLIENT_QUEUES:
                            SSE_CLIENT_QUEUES.remove(q)
                except Exception:
                    pass
            return

        # 访问根路径时，返回首页。
        if self.path == "/":
            file_path = SRC_DIR / "index.html"
        elif self.path.startswith("/data/"):
            # /data/* 路径改为从根目录 data 文件夹读取。
            file_path = Path(__file__).resolve().parent / self.path.lstrip("/")
        else:
            # 其他路径按 src 目录中的相对路径读取。
            file_path = SRC_DIR / self.path.lstrip("/")

        # 文件不存在时，返回 404。
        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return

        # 根据文件类型设置响应头。
        if file_path.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif file_path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif file_path.suffix == ".json":
            content_type = "application/json; charset=utf-8"
        else:
            content_type = "text/plain; charset=utf-8"

        file_bytes = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(file_bytes)))
        self.end_headers()
        self.wfile.write(file_bytes)

    # 这里处理前端发来的 POST 请求。
    def do_POST(self):
        # /api/save-dp：保存 DP
        # /api/undo：撤销最近一次修改（可追溯）
        # /api/trigger-event：接收外部事件（为自定义扩展规则预留）
        if self.path not in ("/api/save-dp", "/api/undo", "/api/trigger-event"):
            self.send_response(404)
            self.end_headers()
            return

        # 撤销接口：不要求请求体。
        if self.path == "/api/undo":
            try:
                target = find_latest_undoable_history_record()
                if target is None:
                    response_body = json.dumps(
                        {"ok": False, "reason": "no_undoable_history"}
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(response_body)))
                    self.end_headers()
                    self.wfile.write(response_body)
                    return

                # 撤销包含：读取 state -> 反向应用 changes -> 写回 state -> 写 history。
                # 这几个动作必须在同一把锁里完成，避免并发写入把文件写乱。
                with STATE_IO_LOCK:
                    state = read_state_file()

                    undo_changes = []
                    changes = target.get("changes")
                    if not isinstance(changes, list):
                        changes = []

                    for i in range(len(changes)):
                        ch = changes[i]
                        if not isinstance(ch, dict):
                            continue
                        path = ch.get("path")
                        if not isinstance(path, str) or path.strip() == "":
                            continue

                        # 反向应用：把值写回 from。
                        to_value = ch.get("from")
                        from_value = get_value_by_path(state, path)
                        set_value_by_path(state, path, to_value)
                        undo_changes.append(
                            {"path": path, "from": from_value, "to": to_value}
                        )

                    # 把撤销后的状态写回 state.json（只写一次）。
                    write_json_atomic(STATE_FILE, state)

                    # 追加一条 undo 历史记录（可追溯）。
                    undo_of_ts = target.get("ts")
                    if not isinstance(undo_of_ts, int):
                        undo_of_ts = 0
                    append_state_history_with_data(
                        event_type="undo",
                        note="撤销",
                        data={"undo_of_ts": undo_of_ts},
                        changes=undo_changes,
                    )

                # 通知前端：state 变了，请重新读取。
                sse_broadcast("state", {"reason": "undo"})

                response_body = json.dumps(
                    {"ok": True, "undo_of_ts": undo_of_ts}
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
                return
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

        # /api/trigger-event：接收外部事件（第一步：先只打日志，不修改 DP）
        if self.path == "/api/trigger-event":
            # 读取请求体内容。
            content_length = int(self.headers.get("Content-Length", "0"))
            request_body = self.rfile.read(content_length)

            try:
                body_data = json.loads(request_body.decode("utf-8"))
            except Exception:
                # JSON 解析失败。
                self.send_response(400)
                self.end_headers()
                return

            if not isinstance(body_data, dict):
                self.send_response(400)
                self.end_headers()
                return

            # event：事件名，例如 git_commit / git_tag
            # id：事件唯一标识，用于未来做“去重”（同一个事件只处理一次）
            # data：事件补充信息（可选）
            event_name = body_data.get("event", "")
            event_id = body_data.get("id", "")
            event_data = body_data.get("data", {})

            if not isinstance(event_name, str) or event_name.strip() == "":
                self.send_response(400)
                self.end_headers()
                return

            if not isinstance(event_id, str) or event_id.strip() == "":
                self.send_response(400)
                self.end_headers()
                return

            if event_data is None:
                event_data = {}
            if not isinstance(event_data, dict):
                self.send_response(400)
                self.end_headers()
                return

            # 只打日志：用于确认“事件能送进 ChronOS”。
            # 注意：data 可能很长，这里做一个简单截断，避免日志爆炸。
            try:
                safe_data_text = json.dumps(event_data, ensure_ascii=False)
            except Exception:
                safe_data_text = "{}"
            if len(safe_data_text) > 200:
                safe_data_text = safe_data_text[:200] + "...(truncated)"

            log(
                "trigger-event: "
                + "event="
                + str(event_name)
                + " id="
                + str(event_id)
                + " data="
                + safe_data_text
            )

            # 0.0.5 第二步：读取规则，并打印“命中哪些规则”。
            # 这一步只做匹配，不修改 DP。
            rules = load_extension_rules()
            matched = match_rules_for_event(rules, event_name, event_data)

            if len(matched) == 0:
                log("trigger-event: matched_rules=0")
            else:
                # 只打印规则 id，避免日志太长。
                ids = []
                for r in matched:
                    rid = r.get("id", "") if isinstance(r, dict) else ""
                    if rid:
                        ids.append(str(rid))
                if len(ids) == 0:
                    log(f"trigger-event: matched_rules={len(matched)}")
                else:
                    log(
                        "trigger-event: matched_rules="
                        + str(len(matched))
                        + " ids="
                        + ",".join(ids)
                    )

            # 0.0.5 第三步（本次要做）：去重检查。
            # - 如果 event_id 已经处理过，就打印日志并跳过。
            # - 如果没处理过：应用命中规则的 DP 变化，并写入 rule_apply history。
            if history_has_rule_event_id(str(event_id)):
                log("trigger-event: dedupe=hit (already_processed)")
            else:
                log("trigger-event: dedupe=miss")

                # 计算本次事件要增加/减少的 DP。
                # 注意：这里允许多条规则同时命中，dp_delta 会累加。
                total_dp_delta = 0
                applied_rule_ids = []
                for r in matched:
                    if not isinstance(r, dict):
                        continue
                    rid = r.get("id", "")
                    if isinstance(rid, str) and rid.strip() != "":
                        applied_rule_ids.append(rid.strip())

                    try:
                        delta = int(r.get("dp_delta", 0) or 0)
                    except Exception:
                        delta = 0
                    total_dp_delta += delta

                if len(applied_rule_ids) == 0 or total_dp_delta == 0:
                    log("trigger-event: apply=skip (no_effect)")
                else:
                    # 在同一把锁里完成：读 state -> 改 dp -> 写 state -> 记 history。
                    with STATE_IO_LOCK:
                        state = read_state_file()
                        old_dp = int(state.get("dp", 0) or 0)
                        new_dp = old_dp + int(total_dp_delta)
                        if new_dp < 0:
                            new_dp = 0

                        if new_dp != old_dp:
                            state["dp"] = int(new_dp)
                            if "gp" not in state:
                                state["gp"] = 0

                            write_json_atomic(STATE_FILE, state)

                            # 为了避免 history 太大，这里只保留 event_data 的关键字段。
                            stored_event_data = {}
                            try:
                                if isinstance(event_data, dict):
                                    for k in ("hash", "message", "tag"):
                                        if k in event_data:
                                            stored_event_data[k] = event_data.get(k)
                            except Exception:
                                stored_event_data = {}

                            append_state_history_with_data(
                                event_type="rule_apply",
                                actor="extension",
                                note="应用自定义规则",
                                data={
                                    "event": str(event_name),
                                    "event_id": str(event_id),
                                    "rules": applied_rule_ids,
                                    "dp_delta": int(total_dp_delta),
                                    "event_data": stored_event_data,
                                },
                                changes=[
                                    {"path": "dp", "from": old_dp, "to": int(new_dp)}
                                ],
                            )

                            # 通知前端刷新。
                            sse_broadcast("state", {"reason": "rule_apply"})
                            log(
                                "trigger-event: apply=ok dp "
                                + str(old_dp)
                                + " -> "
                                + str(new_dp)
                                + " (delta="
                                + str(total_dp_delta)
                                + ")"
                            )
                        else:
                            log("trigger-event: apply=skip (dp_unchanged)")

            response_body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            return

        # 读取请求体内容。
        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length)

        try:
            # 解析前端发送的 JSON，并拿到 dp。
            body_data = json.loads(request_body.decode("utf-8"))
            dp_value = int(body_data.get("dp", 0))
            # DP 不允许小于 0。
            if dp_value < 0:
                dp_value = 0

            # 读取旧状态，然后只更新 dp/gp。
            # 这样 state.json 里其他字段（例如爬虫状态）不会被覆盖掉。
            with STATE_IO_LOCK:
                state = read_state_file()

                old_dp = int(state.get("dp", 0))

                # 只有当 dp 真的变化时，才写入 state.json，并记录一条 history。
                if dp_value != old_dp:
                    state["dp"] = dp_value
                    if "gp" not in state:
                        state["gp"] = 0

                    # 把最新状态写回 state.json。
                    write_json_atomic(STATE_FILE, state)

                    # 追加一条历史记录（只记录变化）。
                    append_state_history(
                        event_type="dp_set",
                        note="保存 DP",
                        changes=[{"path": "dp", "from": old_dp, "to": dp_value}],
                    )

                    # 通知前端：state 变了，请重新读取 data/state.json。
                    sse_broadcast("state", {"reason": "dp_saved"})

            # 返回保存成功结果。
            response_body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
        except Exception:
            # 解析失败或写入失败时，返回 400。
            self.send_response(400)
            self.end_headers()


# 启动本地服务，监听 8000 端口。
if __name__ == "__main__":
    # 尽量保证日志文件可读（UTF-8）。
    ensure_utf8_stdio()

    # 启动前，先确保状态文件存在。
    ensure_state_file_exists()
    ensure_crawler_state_file_exists()
    ensure_state_history_file_exists()

    # 启动时自动安装 git hooks：让 commit/tag 能自动触发扩展规则。
    ensure_git_hooks_installed()

    # 启动时也尝试接一次爬虫 pending（用于“程序没运行时错过 4:00”的补偿）。
    apply_crawler_pending_changes_once()

    # 启动后台调度：主程序负责到点启动工具脚本
    t = threading.Thread(target=crawler_scheduler_loop, daemon=True)
    t.start()

    # 启动后台监控：用于发现“外部改动 state.json”的情况。
    watcher = threading.Thread(target=state_file_watcher_loop, daemon=True)
    watcher.start()

    # 使用 ThreadingHTTPServer：因为 SSE 连接会长期占用一个请求。
    server = ThreadingHTTPServer(("0.0.0.0", 8000), SaveDpHandler)
    log("Server running at http://0.0.0.0:8000")
    server.serve_forever()
