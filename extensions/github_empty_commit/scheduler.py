import json
import time
from datetime import datetime
from pathlib import Path


# 项目根目录（ChronOS）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_FILE = PROJECT_ROOT / "config" / "github_empty_commit.json"
PLAN_FILE = DATA_DIR / "github_empty_commit_plan.json"


def now_text() -> str:
    # 统一时间显示格式。
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    # 控制台日志：给使用者看当前状态。
    print(f"[{now_text()}] [GITHUB_EMPTY_COMMIT_SCHED] {message}", flush=True)


def ensure_config_file_exists() -> None:
    # 如果配置文件不存在，就写入默认配置。
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        return

    default_config = {
        "enabled": False,
        "interval_days": 7,
        "repo_path": "",
        "commit_message": "chore: keepalive",
        "push_remote": "origin",
        "push_branch": "",
    }
    CONFIG_FILE.write_text(
        json.dumps(default_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_plan_file_exists() -> None:
    # 如果计划文件不存在，就写入默认计划。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PLAN_FILE.exists():
        return

    default_plan = {
        "enabled": False,
        "interval_days": 7,
        "repo_path": "",
        "commit_message": "chore: keepalive",
        "push_remote": "origin",
        "push_branch": "",
        "pending": False,
        "pending_ts": 0,
        "pending_text": "",
        "next_run_ts": 0,
        "next_run_text": "",
        "last_run_ts": 0,
        "last_run_text": "",
        "last_result": "",
    }
    PLAN_FILE.write_text(
        json.dumps(default_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_config() -> dict:
    # 读取配置文件，失败时返回空配置。
    ensure_config_file_exists()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def read_plan() -> dict:
    # 读取计划文件，失败时返回默认值。
    ensure_plan_file_exists()
    try:
        data = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def write_plan(plan: dict) -> None:
    # 保存最新计划。
    PLAN_FILE.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    # 入口：只负责计时和写计划，不执行提交。
    log("计划器已启动")
    ensure_config_file_exists()
    ensure_plan_file_exists()

    while True:
        config = read_config()
        plan = read_plan()

        enabled = bool(config.get("enabled", False))
        plan["enabled"] = enabled

        if not enabled:
            plan["pending"] = False
            plan["next_run_ts"] = 0
            plan["next_run_text"] = ""
            write_plan(plan)
            time.sleep(60)
            continue

        interval_days = int(config.get("interval_days", 7) or 7)
        if interval_days <= 0:
            interval_days = 1
        plan["interval_days"] = interval_days

        plan["repo_path"] = str(config.get("repo_path", "")).strip()
        plan["commit_message"] = str(
            config.get("commit_message", "chore: keepalive")
        ).strip()
        plan["push_remote"] = (
            str(config.get("push_remote", "origin")).strip() or "origin"
        )
        plan["push_branch"] = str(config.get("push_branch", "")).strip()

        if bool(plan.get("pending", False)):
            write_plan(plan)
            time.sleep(60)
            continue

        last_run_ts = int(plan.get("last_run_ts", 0) or 0)
        next_run_ts = int(plan.get("next_run_ts", 0) or 0)
        interval_seconds = int(interval_days) * 24 * 60 * 60
        now_ts = int(time.time())

        if last_run_ts <= 0 and next_run_ts <= 0:
            next_run_ts = now_ts
        elif last_run_ts > 0:
            expected_next = last_run_ts + interval_seconds
            if next_run_ts <= 0 or next_run_ts < expected_next:
                next_run_ts = expected_next

        if next_run_ts > 0 and now_ts >= next_run_ts:
            plan["pending"] = True
            plan["pending_ts"] = now_ts
            plan["pending_text"] = now_text()

        plan["next_run_ts"] = next_run_ts
        plan["next_run_text"] = (
            datetime.fromtimestamp(next_run_ts).strftime("%Y-%m-%d %H:%M:%S")
            if next_run_ts > 0
            else ""
        )

        write_plan(plan)
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
