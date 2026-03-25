import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


# 项目根目录：ChronOS/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 统一 Python 缓存目录到项目根目录下的 __pycache__。
# 这样自动重启器本身和它启动的子进程都会集中缓存。
PY_CACHE_DIR = PROJECT_ROOT / "__pycache__"
PY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
sys.pycache_prefix = str(PY_CACHE_DIR)
os.environ["PYTHONPYCACHEPREFIX"] = str(PY_CACHE_DIR)
LOG_DIR = PROJECT_ROOT / "logs"
WATCH_CONFIG_FILE = PROJECT_ROOT / "config" / "reload_watch.json"

# 默认：这些类型的文件改动后，会触发自动重启。
DEFAULT_WATCH_SUFFIXES = {
    ".py",
    ".js",
    ".json",
    ".bat",
    ".vbs",
}

# 默认：这些目录不参与监听，避免无关文件触发重启。
DEFAULT_IGNORE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "logs",
    "data",
}

# 控制台输出锁：避免多线程同时 print 造成一行被拆开。
PRINT_LOCK = threading.Lock()

# 重启风暴保护：在短时间内连续失败时自动退出。
RESTART_GUARD_WINDOW_SECONDS = 30
RESTART_GUARD_MAX_COUNT = 5
RESTART_GUARD_SLEEP_SECONDS = 2

# 运行时配置（优先读 config/reload_watch.json，失败时回退默认值）。
WATCH_SUFFIXES = set(DEFAULT_WATCH_SUFFIXES)
IGNORE_DIR_NAMES = set(DEFAULT_IGNORE_DIR_NAMES)


def load_watch_config() -> None:
    # 从 config/reload_watch.json 读取监听配置。
    # 读取失败时回退默认配置，保证服务能继续运行。
    global WATCH_SUFFIXES
    global IGNORE_DIR_NAMES

    watch_suffixes = set(DEFAULT_WATCH_SUFFIXES)
    ignore_dir_names = set(DEFAULT_IGNORE_DIR_NAMES)

    try:
        if WATCH_CONFIG_FILE.exists() and WATCH_CONFIG_FILE.is_file():
            raw = WATCH_CONFIG_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)

            if isinstance(data, dict):
                raw_suffixes = data.get("watch_suffixes")
                if isinstance(raw_suffixes, list):
                    parsed_suffixes = set()
                    for item in raw_suffixes:
                        s = str(item).strip().lower()
                        if s == "":
                            continue
                        if not s.startswith("."):
                            s = "." + s
                        parsed_suffixes.add(s)
                    if parsed_suffixes:
                        watch_suffixes = parsed_suffixes

                raw_ignores = data.get("ignore_dir_names")
                if isinstance(raw_ignores, list):
                    parsed_ignores = set()
                    for item in raw_ignores:
                        name = str(item).strip()
                        if name == "":
                            continue
                        parsed_ignores.add(name)
                    ignore_dir_names = parsed_ignores
    except Exception as e:
        log_error(f"读取监听配置失败，已回退默认配置: {e}")

    WATCH_SUFFIXES = watch_suffixes
    IGNORE_DIR_NAMES = ignore_dir_names


def get_daily_log_file() -> Path:
    # 按天归档：每天一个日志文件。
    day_text = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"server.{day_text}.log"


def append_log_file(line: str) -> None:
    # 统一日志文件：所有输出都追加到“当天日志”。
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = get_daily_log_file()
    with log_file.open("a", encoding="utf-8", newline="\n") as f:
        f.write(str(line) + "\n")


def emit_line(line: str, to_stderr: bool = False) -> None:
    # 同时输出到控制台 + 统一日志文件（单文件）。
    with PRINT_LOCK:
        if to_stderr:
            print(line, file=sys.stderr, flush=True)
        else:
            print(line, flush=True)
        append_log_file(line)


def print_boundary(title: str) -> None:
    # 打印明显分隔线，方便区分“重启前/重启后”。
    line = "=" * 72
    emit_line(line)
    emit_line(f"[{now_text()}] [INFO] [RELOADER] {title}")
    emit_line(line)


def now_text() -> str:
    # 统一时间文本格式。
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    # 统一输出格式，方便和主服务日志一起看。
    emit_line(f"[{now_text()}] [INFO] [RELOADER] {message}")


def log_error(message: str) -> None:
    # 错误输出。
    emit_line(f"[{now_text()}] [ERROR] [RELOADER] {message}", to_stderr=True)


def should_abort_restart(restart_times: list, reason: str) -> bool:
    # 重启风暴保护：如果在短时间内重启过多，就直接退出。
    now_ts = time.time()
    window_start = now_ts - RESTART_GUARD_WINDOW_SECONDS
    filtered = [t for t in restart_times if t >= window_start]
    filtered.append(now_ts)
    restart_times[:] = filtered

    if len(restart_times) <= RESTART_GUARD_MAX_COUNT:
        return False

    log_error(
        "检测到重启过于频繁，已自动退出（避免刷屏）。"
        f"原因={reason}，窗口={RESTART_GUARD_WINDOW_SECONDS}s，"
        f"次数={len(restart_times)}"
    )
    return True


def forward_stream_lines(stream, to_stderr: bool) -> None:
    # 把子进程的输出按“整行”转发到当前控制台。
    # 这样可以减少“半行拼接/换行异常”。
    try:
        for raw in stream:
            line = str(raw).rstrip("\r\n")
            emit_line(line, to_stderr=to_stderr)
    except Exception:
        # 转发失败不影响主流程。
        return


def should_ignore(file_path: Path) -> bool:
    # 只要路径里出现忽略目录名，就跳过。
    for part in file_path.parts:
        if part in IGNORE_DIR_NAMES:
            return True
    return False


def build_snapshot() -> dict:
    # 扫描项目文件，记录每个文件的最后修改时间。
    # 用 mtime_ns（纳秒）可以减少时间精度导致的漏检。
    snap = {}
    for file_path in PROJECT_ROOT.rglob("*"):
        if not file_path.is_file():
            continue
        if should_ignore(file_path):
            continue
        if file_path.suffix.lower() not in WATCH_SUFFIXES:
            continue

        try:
            snap[str(file_path)] = file_path.stat().st_mtime_ns
        except Exception:
            # 文件可能在扫描时被临时占用/删除，跳过即可。
            continue

    return snap


def find_changed_files(old_snap: dict, new_snap: dict) -> list:
    # 找出“新增、删除、修改”的文件。
    changed = []

    old_keys = set(old_snap.keys())
    new_keys = set(new_snap.keys())

    for key in sorted(new_keys - old_keys):
        changed.append(f"新增: {Path(key).relative_to(PROJECT_ROOT)}")

    for key in sorted(old_keys - new_keys):
        changed.append(f"删除: {Path(key).relative_to(PROJECT_ROOT)}")

    for key in sorted(old_keys & new_keys):
        if old_snap[key] != new_snap[key]:
            changed.append(f"修改: {Path(key).relative_to(PROJECT_ROOT)}")

    return changed


def start_server() -> subprocess.Popen:
    # 启动主服务（server.py）。
    cmd = [sys.executable, "-X", "utf8", "-u", "server.py"]
    log("启动 server.py")
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if proc.stdout is not None:
        threading.Thread(
            target=forward_stream_lines,
            args=(proc.stdout, False),
            daemon=True,
        ).start()
    if proc.stderr is not None:
        threading.Thread(
            target=forward_stream_lines,
            args=(proc.stderr, True),
            daemon=True,
        ).start()

    return proc


def stop_server(proc: subprocess.Popen) -> None:
    # 停止主服务，避免残留进程占端口。
    if proc.poll() is not None:
        return

    proc.terminate()
    try:
        proc.wait(timeout=5)
        log("server.py 已停止")
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        log("server.py 已强制停止")


def main() -> int:
    # 自动重启入口。
    # 逻辑：先启动一次 server，再每秒轮询文件变化，变化就重启。
    restart_count = 0
    print_boundary("自动重启器已启动")

    # 启动时先加载一次监听配置文件。
    load_watch_config()

    last_snapshot = build_snapshot()
    server_proc = start_server()
    restart_times = []

    try:
        while True:
            # 如果服务意外退出，也自动拉起。
            if server_proc.poll() is not None:
                log_error(
                    f"server.py 已退出，退出码={server_proc.returncode}，准备重启"
                )
                if should_abort_restart(restart_times, "服务意外退出"):
                    stop_server(server_proc)
                    return 1

                restart_count = restart_count + 1
                print_boundary(f"重启开始（第 {restart_count} 次，原因：服务意外退出）")
                time.sleep(RESTART_GUARD_SLEEP_SECONDS)
                time.sleep(1)
                server_proc = start_server()
                print_boundary(f"重启完成（第 {restart_count} 次）")
                last_snapshot = build_snapshot()
                continue

            time.sleep(1)
            # 每轮都重读配置：这样只改 JSON 配置就能热生效。
            load_watch_config()
            current_snapshot = build_snapshot()
            changed_files = find_changed_files(last_snapshot, current_snapshot)
            if not changed_files:
                continue

            log(f"检测到文件变化，共 {len(changed_files)} 处")
            log(changed_files[0])

            if should_abort_restart(restart_times, "文件变更触发"):
                stop_server(server_proc)
                return 1

            restart_count = restart_count + 1
            print_boundary(
                f"重启开始（第 {restart_count} 次，原因：{changed_files[0]}）"
            )
            stop_server(server_proc)
            time.sleep(0.5)
            server_proc = start_server()
            print_boundary(f"重启完成（第 {restart_count} 次）")
            last_snapshot = current_snapshot
    except KeyboardInterrupt:
        log("收到 Ctrl+C，准备退出")
        stop_server(server_proc)
        return 0
    except Exception as e:
        log_error(f"自动重启器异常: {e}")
        stop_server(server_proc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
