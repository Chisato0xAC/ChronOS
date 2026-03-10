import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


# 这个路径指向前端目录。
SRC_DIR = Path(__file__).resolve().parent / "src"
# 这个路径指向根目录 data 文件夹。
DATA_DIR = Path(__file__).resolve().parent / "data"
# 这个路径指向项目里的状态文件，用来保存 DP 和 GP。
STATE_FILE = DATA_DIR / "state.json"


# 如果 data/state.json 不存在，就创建一个默认文件。
# 这样用户第一次运行项目时，不需要手动新建 data 文件夹。
def ensure_state_file_exists():
    # 第一步：确保 data/ 文件夹存在。
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 第二步：如果 state.json 已存在，就什么都不做。
    if STATE_FILE.exists():
        return

    # 第三步：写入一个最简单的默认状态。
    default_state = {"dp": 0, "gp": 0}
    STATE_FILE.write_text(
        json.dumps(default_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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

            # 先准备一个新的状态对象。
            state = {"dp": dp_value, "gp": 0}
            # 如果原文件存在，就保留原来的 GP。
            if STATE_FILE.exists():
                old_state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                state["gp"] = old_state.get("gp", 0)

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
    # 启动前，先确保状态文件存在。
    ensure_state_file_exists()
    server = HTTPServer(("0.0.0.0", 8000), SaveDpHandler)
    print("Server running at http://0.0.0.0:8000")
    server.serve_forever()
