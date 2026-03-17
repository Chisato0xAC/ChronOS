import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# 让这个脚本无论从哪里运行，都能 import 到项目根目录下的模块（例如 chronos_config.py）。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chronos_config import (
    DAY_BOUNDARY_HOUR,
    DAY_BOUNDARY_MINUTE,
    DAY_BOUNDARY_SECOND,
)

# 这个脚本做两件事：
# 1) 爬取 B 站历史记录里的「视频时长」与「观看时间」
# 2) 把所有视频时长相加，换算成 DP 变更值（分钟取整）

# --- 配置区 ---
# 账号信息文件（放在 data/ 里；data/ 已在 .gitignore 中，不会提交到 git）
AUTH_FILE = Path(__file__).resolve().parents[2] / "data" / "bilibili_auth.json"

# B 站扣除规则文件（放在 data/ 里，方便用户自己改数值）
BILIBILI_RULE_FILE = Path(__file__).resolve().parents[2] / "data" / "bilibili_rule.json"

HISTORY_API_URL = "https://api.bilibili.com/x/web-interface/history/cursor"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 一天的分界线：统一在 chronos_config.py 配置

# 注意：本项目把“当前状态(state)”和“爬虫运行状态(crawler_state)”分开存。
# - data/state.json：只保存 dp/gp 等“当前数值”（爬虫不写入）
# - data/crawler_state.json：只保存爬虫运行状态（本脚本负责读写）
STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "state.json"
CRAWLER_STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "crawler_state.json"


def format_dt(dt: datetime) -> str:
    # 把时间格式化成易读文本（北京时间=本机时间）
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    # 统一打印格式：给每一行加上时间戳。
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_text}] {message}")


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


def parse_duration_text_to_seconds(text: str) -> int:
    # 把 "MM:SS" 或 "HH:MM:SS" 转成秒数。
    # 例："02:43" => 163 秒；"01:22:23" => 4943 秒。
    raw = str(text or "").strip()
    parts = [p.strip() for p in raw.split(":") if p.strip() != ""]

    if len(parts) == 2:
        mm = int(parts[0])
        ss = int(parts[1])
        return mm * 60 + ss

    if len(parts) == 3:
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2])
        return hh * 3600 + mm * 60 + ss

    raise ValueError(f"不支持的时长格式: {raw}")


def ensure_bilibili_rule_file_exists() -> None:
    # 确保 data/bilibili_rule.json 存在。
    # 用户可以在这个文件里改阈值和百分比。
    BILIBILI_RULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if BILIBILI_RULE_FILE.exists():
        return

    default_rule = {
        "short_duration_max": "02:43",
        "short_weight_percent": 120,
        "long_duration_min": "01:22:23",
        "long_weight_percent": 80,
        "normal_weight_percent": 100,
    }
    BILIBILI_RULE_FILE.write_text(
        json.dumps(default_rule, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_bilibili_rule() -> dict:
    # 读取并解析 B 站扣除规则。
    # 如果文件坏了/缺字段，就使用默认值，避免脚本直接崩掉。
    ensure_bilibili_rule_file_exists()

    default_rule = {
        "short_duration_max": "02:43",
        "short_weight_percent": 120,
        "long_duration_min": "01:22:23",
        "long_weight_percent": 80,
        "normal_weight_percent": 100,
    }

    try:
        data = json.loads(BILIBILI_RULE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    # 合并默认值，缺什么补什么
    merged = dict(default_rule)
    merged.update(data)

    # 把文本阈值解析成秒数，方便计算
    try:
        short_max_seconds = parse_duration_text_to_seconds(merged["short_duration_max"])
    except Exception:
        short_max_seconds = parse_duration_text_to_seconds(
            default_rule["short_duration_max"]
        )

    try:
        long_min_seconds = parse_duration_text_to_seconds(merged["long_duration_min"])
    except Exception:
        long_min_seconds = parse_duration_text_to_seconds(
            default_rule["long_duration_min"]
        )

    def safe_int(value, fallback: int) -> int:
        try:
            return int(value)
        except Exception:
            return int(fallback)

    return {
        "short_max_seconds": int(short_max_seconds),
        "short_weight_percent": safe_int(
            merged.get("short_weight_percent"), default_rule["short_weight_percent"]
        ),
        "long_min_seconds": int(long_min_seconds),
        "long_weight_percent": safe_int(
            merged.get("long_weight_percent"), default_rule["long_weight_percent"]
        ),
        "normal_weight_percent": safe_int(
            merged.get("normal_weight_percent"), default_rule["normal_weight_percent"]
        ),
    }


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

    today_4am = now.replace(
        hour=DAY_BOUNDARY_HOUR,
        minute=DAY_BOUNDARY_MINUTE,
        second=DAY_BOUNDARY_SECOND,
        microsecond=0,
    )
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
    today_4am = now.replace(
        hour=DAY_BOUNDARY_HOUR,
        minute=DAY_BOUNDARY_MINUTE,
        second=DAY_BOUNDARY_SECOND,
        microsecond=0,
    )
    if now >= today_4am:
        return today_4am
    return today_4am - timedelta(days=1)


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


def calc_total_minutes_from_records(records: list, rule: dict) -> int:
    # 根据规则计算“要扣除的分钟数”。
    # 需求：
    # 扣除 DP = （
    #   低于等于 short_max 的视频叠加总时长 * short_weight%
    #   + 高于等于 long_min 的视频叠加总时长 * long_weight%
    #   + 其它视频叠加总时长 * normal_weight%
    # ） // 60
    short_max = int(rule.get("short_max_seconds", 0) or 0)
    long_min = int(rule.get("long_min_seconds", 0) or 0)

    short_w = int(rule.get("short_weight_percent", 120) or 120)
    long_w = int(rule.get("long_weight_percent", 80) or 80)
    normal_w = int(rule.get("normal_weight_percent", 100) or 100)

    # 用整数做百分比计算，避免浮点误差：
    # 先累计 duration * percent（分子），最后统一除以 (100*60)
    weighted_seconds_numerator = 0
    for r in records:
        duration = int(r.get("duration", 0) or 0)
        if duration < 0:
            duration = 0

        if duration <= short_max:
            weighted_seconds_numerator += duration * short_w
        elif duration >= long_min:
            weighted_seconds_numerator += duration * long_w
        else:
            weighted_seconds_numerator += duration * normal_w

    return int(weighted_seconds_numerator // (100 * 60))


def calc_dp_delta(total_minutes: int) -> int:
    # DP 变更值：默认是扣除（负数）。
    # 未来做 DP 变更记录功能时，可以在这里接入更复杂的规则。
    return -abs(int(total_minutes))


def main() -> None:
    # 这个脚本是一个“一次性工具”：运行一次，做一次检查/补爬，然后退出。
    log("爬虫：开始运行（北京时间 4:00 分界）")

    sessdata = get_sessdata_from_file()
    if not sessdata:
        log("爬虫：缺少 sessdata，请先填写 data/bilibili_auth.json")
        return

    crawler_state = load_crawler_state()
    now = datetime.now()
    latest_completed_trigger = get_latest_completed_trigger_time(now)

    if has_crawled_trigger_time(crawler_state, latest_completed_trigger):
        last_text = str(crawler_state.get("last_trigger_text", "")).strip()
        if last_text:
            log(f"爬虫：已完成（触发点 {last_text}）")
        else:
            log("爬虫：已完成（今天窗口已爬取过）")
        return
    else:
        log("爬虫：需要执行（今天窗口还没爬取）")
        run_time = datetime.now()
        window_start, window_end = get_window_for_trigger_time(latest_completed_trigger)
        start_ts = int(window_start.timestamp())
        end_ts = int(window_end.timestamp())

        log(f"爬虫：窗口 {format_dt(window_start)} 到 {format_dt(window_end)}")
        records = fetch_history_records_in_range(start_ts, end_ts, sessdata)
        log(f"爬虫：记录数 {len(records)}")

        rule = load_bilibili_rule()
        total_minutes = calc_total_minutes_from_records(records, rule)
        dp_delta = calc_dp_delta(total_minutes)
        log(f"爬虫：DP 变更值(分钟取整) {dp_delta}")

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
        log("爬虫：完成（已写入 data/crawler_state.json）")
        return


if __name__ == "__main__":
    main()
