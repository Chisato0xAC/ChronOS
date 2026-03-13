import json
import sys
import urllib.request


# 这个脚本用于把一个“事件”发送给 ChronOS 本地服务端。
#
# 设计目标：
# 1) 给 git hook 用：即使发送失败，也不能影响 git commit。
# 2) 参数尽量简单：event + id + 若干 key=value（组成 data）。
#
# 用法示例：
#   python -X utf8 -u tools/send_event.py git_commit commit:abcd1234 hash=abcd1234


def parse_kv_args(parts: list) -> dict:
    data = {}
    for p in parts:
        if not isinstance(p, str):
            continue
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = str(k).strip()
        if k == "":
            continue
        data[k] = v
    return data


def main() -> int:
    # 约定：
    # argv[1] = event
    # argv[2] = id
    # argv[3:] = key=value -> data
    if len(sys.argv) < 3:
        return 0

    event_name = str(sys.argv[1]).strip()
    event_id = str(sys.argv[2]).strip()
    if event_name == "" or event_id == "":
        return 0

    event_data = parse_kv_args(sys.argv[3:])

    payload = {
        "event": event_name,
        "id": event_id,
        "data": event_data,
    }

    try:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url="http://127.0.0.1:8000/api/trigger-event",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # timeout 要短：不能拖慢 git commit。
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            _ = resp.read()
        return 0
    except Exception:
        # 发送失败是正常情况：例如服务没开。
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
