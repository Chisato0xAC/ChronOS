import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# 这个脚本做两件事：
# 1) 爬取 B 站历史记录里的「视频时长」与「观看时间」
# 2) 把所有视频时长相加，换算成 DP 变更值（分钟取整）

# --- 配置区 ---
# 账号信息文件（放在 data/ 里；data/ 已在 .gitignore 中，不会提交到 git）
AUTH_FILE = Path(__file__).resolve().parents[2] / "data" / "bilibili_auth.json"

HISTORY_API_URL = "https://api.bilibili.com/x/web-interface/history/cursor"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 一天的分界线（北京时间）：4:00
DAY_BOUNDARY_HOUR = 4

# 注意：本项目把“当前状态(state)”和“爬虫运行状态(crawler_state)”分开存。
# - data/state.json：只保存 dp/gp 等“当前数值”（爬虫不写入）
# - data/crawler_state.json：只保存爬虫运行状态（本脚本负责读写）
STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "state.json"
CRAWLER_STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "crawler_state.json"


def format_dt(dt: datetime) -> str:
    # 把时间格式化成易读文本（北京时间=本机时间）
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def build_headers(sessdata: str) -> dict:
    # 这是请求 B 站接口需要的基础信息
    return {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Cookie": f"SESSDATA={sessdata};",
    }


def ensure_auth_file_exists() -> None:
    # 确保 data/bilibili_auth.json 存在。
    # 用户只需要把 SESSDATA 填进去。
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    if AUTH_FILE.exists():
        return
    default_auth = {"sessdata": ""}
    AUTH_FILE.write_text(
        json.dumps(default_auth, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_sessdata_from_file() -> str:
    # 从 data/bilibili_auth.json 读取 SESSDATA
    ensure_auth_file_exists()
    auth = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    sessdata = str(auth.get("sessdata", "")).strip()
    # 如果还没填写，就返回空字符串。
    # 这个脚本作为工具使用时，不用抛异常（避免主程序日志出现一大段 traceback）。
    return sessdata


def ensure_crawler_state_file_exists() -> None:
    # 确保 data/crawler_state.json 存在。
    # 这个文件只存爬虫运行状态（例如：今天窗口是否爬过）。
    CRAWLER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CRAWLER_STATE_FILE.exists():
        return
    CRAWLER_STATE_FILE.write_text(
        json.dumps({}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_crawler_state() -> dict:
    ensure_crawler_state_file_exists()
    try:
        data = json.loads(CRAWLER_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        # 如果文件内容损坏，就返回空字典，避免脚本直接崩掉
        return {}


def save_crawler_state(crawler_state: dict) -> None:
    CRAWLER_STATE_FILE.write_text(
        json.dumps(crawler_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_current_dp() -> int:
    # 只读取当前 dp（爬虫不写 state.json）。
    try:
        if not STATE_FILE.exists():
            return 0
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return int(state.get("dp", 0) or 0)
    except Exception:
        return 0


def get_latest_completed_window(now: datetime) -> tuple:
    # 以 4:00 为界，计算“最近一个完整日”的窗口：
    # - 如果现在已经 >= 今天 4:00，则窗口是：昨天 4:00 ~ 今天 3:59:59
    # - 如果现在还 < 今天 4:00，则窗口是：前天 4:00 ~ 昨天 3:59:59

    today_4am = now.replace(hour=DAY_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    if now >= today_4am:
        # 已经过了今天 4:00，说明“最近一个完整日”在今天 4:00 结束
        trigger_time = today_4am
    else:
        # 还没到今天 4:00，说明“最近一个完整日”在昨天 4:00 结束
        trigger_time = today_4am - timedelta(days=1)

    window_start = trigger_time - timedelta(days=1)
    window_end = trigger_time - timedelta(seconds=1)

    return window_start, window_end


def get_latest_completed_trigger_time(now: datetime) -> datetime:
    # “触发时间”就是 4:00 这个时间点。
    # 这个函数返回“最近一个完整日”的结束触发时间。
    today_4am = now.replace(hour=DAY_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    if now >= today_4am:
        return today_4am
    return today_4am - timedelta(days=1)


def get_next_trigger_time(now: datetime) -> datetime:
    # 返回下一次要触发爬取的时间点（4:00）。
    today_4am = now.replace(hour=DAY_BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    if now < today_4am:
        return today_4am
    return today_4am + timedelta(days=1)


def get_window_for_trigger_time(trigger_time: datetime) -> tuple:
    # 给定触发时间（某天 4:00），窗口就是前一天 4:00 ~ 当天 3:59:59
    window_start = trigger_time - timedelta(days=1)
    window_end = trigger_time - timedelta(seconds=1)
    return window_start, window_end


def has_crawled_trigger_time(crawler_state: dict, trigger_time: datetime) -> bool:
    last_trigger_ts = int(crawler_state.get("last_trigger_ts", 0) or 0)
    return last_trigger_ts == int(trigger_time.timestamp())


def mark_crawled(
    crawler_state: dict,
    run_time: datetime,
    trigger_time: datetime,
    window_start: datetime,
    window_end: datetime,
    total_minutes: int,
    dp_delta: int,
    current_dp: int,
) -> dict:
    if not isinstance(crawler_state, dict):
        crawler_state = {}

    crawler_state["last_trigger_ts"] = int(trigger_time.timestamp())
    crawler_state["last_window_start_ts"] = int(window_start.timestamp())
    crawler_state["last_window_end_ts"] = int(window_end.timestamp())
    crawler_state["last_total_minutes"] = int(total_minutes)
    crawler_state["last_dp_delta"] = int(dp_delta)

    # 同步写一份易读的文本时间，方便肉眼查看 data/crawler_state.json
    crawler_state["last_trigger_text"] = format_dt(trigger_time)
    crawler_state["last_window_start_text"] = format_dt(window_start)
    crawler_state["last_window_end_text"] = format_dt(window_end)

    # 记录脚本“实际运行”的时间（用于区分：触发点时间 vs 实际补爬时间）
    crawler_state["last_run_ts"] = int(run_time.timestamp())
    crawler_state["last_run_text"] = format_dt(run_time)

    # 预留“扣除 DP”的对接点：
    # - 这里不直接修改 data/state.json（因为 DP 变更记录功能还没做）
    # - 但我们把“如果扣除的话，DP 会变成多少”算出来写进 data/crawler_state.json
    planned_dp_after = current_dp + int(dp_delta)
    if planned_dp_after < 0:
        planned_dp_after = 0

    crawler_state["planned_dp_after"] = int(planned_dp_after)
    crawler_state["dp_delta_kind"] = "deduct"

    # 预留“待扣除 DP”的机制：
    # - 把这次窗口产生的 dp_delta 写成一个“待处理事件”
    # - 未来做 DP 变更记录系统时，由主程序读取并正式扣除（并写入历史）
    crawler_state["pending_dp_status"] = "pending"
    crawler_state["pending_dp_delta"] = int(dp_delta)
    crawler_state["pending_dp_trigger_ts"] = int(trigger_time.timestamp())
    crawler_state["pending_dp_window_start_ts"] = int(window_start.timestamp())
    crawler_state["pending_dp_window_end_ts"] = int(window_end.timestamp())
    crawler_state["pending_dp_created_ts"] = int(run_time.timestamp())
    crawler_state["pending_dp_created_text"] = format_dt(run_time)
    crawler_state["pending_dp_reason"] = "crawler_window"
    crawler_state["pending_dp_note"] = "爬虫已计算出扣除值，等待 DP 变更记录系统对接"
    crawler_state["pending_dp_id"] = (
        f"{int(trigger_time.timestamp())}_{int(window_start.timestamp())}_"
        f"{int(window_end.timestamp())}_{int(dp_delta)}"
    )
    return crawler_state


def fetch_history_records_in_range(start_ts: int, end_ts: int, sessdata: str) -> list:
    # 只保留两列：duration（视频时长，单位秒）、view_at（观看时间，Unix 时间戳）
    all_records = []
    seen_record_ids = set()  # 窗口内记录去重
    seen_page_first_ids = set()  # 防止翻页异常导致循环

    if not sessdata:
        return []
    headers = build_headers(sessdata)

    # 初始游标参数
    params = {
        "ps": 20,
        "max": 0,
        "view_at": 0,
        "business": "archive",
    }

    while True:
        resp = requests.get(HISTORY_API_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        res_json = resp.json()

        if res_json.get("code") != 0:
            raise RuntimeError(f"API 报错: {res_json.get('message', '')}")

        data = res_json.get("data", {})
        items = data.get("list", [])
        cursor = data.get("cursor", {})

        if not items:
            break

        # 关键：检查本页第一条数据是否已经处理过
        current_page_first_id = (
            f"{items[0].get('view_at', 0)}_{items[0].get('duration', 0)}"
        )
        if current_page_first_id in seen_page_first_ids:
            break
        seen_page_first_ids.add(current_page_first_id)

        page_has_any_in_range = False
        page_all_older_than_start = True

        for item in items:
            view_at = int(item.get("view_at", 0) or 0)
            duration = int(item.get("duration", 0) or 0)

            # 只保留窗口内的数据
            if view_at < start_ts or view_at > end_ts:
                if view_at >= start_ts:
                    page_all_older_than_start = False
                continue

            page_has_any_in_range = True
            page_all_older_than_start = False

            # 唯一标识符：观看时间 + 时长（足够用于防重）
            record_id = f"{view_at}_{duration}"
            if record_id in seen_record_ids:
                continue

            record = {
                "duration": duration,
                "view_at": view_at,
            }
            all_records.append(record)
            seen_record_ids.add(record_id)

        # 如果这一页已经全部早于窗口开始时间了，说明后面只会更早，可以停止翻页
        # 注意：B 站历史通常按时间倒序返回，这个判断能大幅减少请求次数
        if page_all_older_than_start and not page_has_any_in_range:
            break

        # 翻页：下一次请求要带上本次返回的 cursor
        next_max = cursor.get("max")
        next_view_at = cursor.get("view_at")
        if not next_max or next_max == params["max"]:
            break

        params["max"] = next_max
        params["view_at"] = next_view_at

        # 礼貌频率限制
        time.sleep(1.5)

    return all_records


def calc_total_minutes_from_records(records: list) -> int:
    # 把所有视频时长(秒)相加，然后除以 60 取整，得到“分钟数”。
    total_seconds = 0
    for r in records:
        total_seconds += int(r.get("duration", 0) or 0)
    return int(total_seconds // 60)


def calc_dp_delta(total_minutes: int) -> int:
    # DP 变更值：默认是扣除（负数）。
    # 未来做 DP 变更记录功能时，可以在这里接入更复杂的规则。
    return -abs(int(total_minutes))


def main() -> None:
    # 这个脚本是一个“一次性工具”：运行一次，做一次检查/补爬，然后退出。
    print("爬虫：开始运行（北京时间 4:00 分界）")

    sessdata = get_sessdata_from_file()
    if not sessdata:
        print("爬虫：缺少 sessdata，请先填写 data/bilibili_auth.json")
        return

    crawler_state = load_crawler_state()
    now = datetime.now()
    latest_completed_trigger = get_latest_completed_trigger_time(now)

    if has_crawled_trigger_time(crawler_state, latest_completed_trigger):
        last_text = str(crawler_state.get("last_trigger_text", "")).strip()
        if last_text:
            print(f"爬虫：已完成（触发点 {last_text}）")
        else:
            print("爬虫：已完成（今天窗口已爬取过）")
        return
    else:
        print("爬虫：需要执行（今天窗口还没爬取）")
        run_time = datetime.now()
        window_start, window_end = get_window_for_trigger_time(latest_completed_trigger)
        start_ts = int(window_start.timestamp())
        end_ts = int(window_end.timestamp())

        print(f"爬虫：窗口 {format_dt(window_start)} 到 {format_dt(window_end)}")
        records = fetch_history_records_in_range(start_ts, end_ts, sessdata)
        print(f"爬虫：记录数 {len(records)}")

        total_minutes = calc_total_minutes_from_records(records)
        dp_delta = calc_dp_delta(total_minutes)
        print(f"爬虫：DP 变更值(分钟取整) {dp_delta}")

        current_dp = read_current_dp()
        crawler_state = mark_crawled(
            crawler_state,
            run_time,
            latest_completed_trigger,
            window_start,
            window_end,
            total_minutes,
            dp_delta,
            current_dp,
        )
        save_crawler_state(crawler_state)
        print("爬虫：完成（已写入 data/crawler_state.json）")
        return


if __name__ == "__main__":
    main()
