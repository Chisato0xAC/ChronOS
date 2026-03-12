import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
from pathlib import Path


# 这个路径指向前端目录。
SRC_DIR = Path(__file__).resolve().parent / "src"
# 这个路径指向根目录 data 文件夹。
DATA_DIR = Path(__file__).resolve().parent / "data"
# 这个路径指向项目里的状态文件，用来保存 DP 和 GP。
STATE_FILE = DATA_DIR / "state.json"

# 爬虫运行状态文件（爬虫脚本读写）。
CRAWLER_STATE_FILE = DATA_DIR / "crawler_state.json"

# 爬虫脚本路径（工具脚本，由主程序按时间触发）
CRAWLER_SCRIPT = Path(__file__).resolve().parent / "src" / "crawler" / "bilibili.py"
CRAWLER_AUTH_FILE = DATA_DIR / "bilibili_auth.json"

# 一天的分界线（北京时间）：4:00
DAY_BOUNDARY_HOUR = 4


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
    print(message, flush=True)


def log_error(message: str) -> None:
    # 错误日志：写到 stderr，并强制 flush
    print(message, file=sys.stderr, flush=True)


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
    today_4am = now.replace(hour=DAY_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    if now < today_4am:
        return today_4am
    return today_4am + timedelta(days=1)


def run_crawler_once() -> None:
    # 启动一次爬虫脚本。
    # 这个脚本会自己判断“今天窗口是否已爬取”，所以重复启动也不会重复爬取。
    if not CRAWLER_SCRIPT.exists():
        log_error(f"Crawler script not found: {CRAWLER_SCRIPT}")
        return

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
    except Exception as e:
        log_error(f"启动爬虫脚本失败: {e}")


def crawler_scheduler_loop() -> None:
    # 这是一个后台循环：
    # 1) 主程序启动时先跑一次（用于补爬）
    # 2) 然后每天到 4:00 再跑一次
    log("调度器：准备启动爬虫工具")

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
        # 如果不是目标接口，就返回 404。
        if self.path != "/api/save-dp":
            self.send_response(404)
            self.end_headers()
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
            if STATE_FILE.exists():
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            else:
                state = {"dp": 0, "gp": 0}

            state["dp"] = dp_value
            if "gp" not in state:
                state["gp"] = 0

            # 把最新状态写回 state.json。
            STATE_FILE.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

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

    # 启动后台调度：主程序负责到点启动工具脚本
    t = threading.Thread(target=crawler_scheduler_loop, daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", 8000), SaveDpHandler)
    log("Server running at http://0.0.0.0:8000")
    server.serve_forever()
