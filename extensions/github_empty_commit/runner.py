import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


# 项目根目录（ChronOS）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PLAN_FILE = DATA_DIR / "github_empty_commit_plan.json"
LOCK_FILE = DATA_DIR / "github_empty_commit_runner.lock"
LOCK_STALE_SECONDS = 10 * 60


def now_text() -> str:
    # 统一时间显示格式。
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    # 控制台日志：给使用者看当前状态。
    print(f"[{now_text()}] [GITHUB_EMPTY_COMMIT_RUN] {message}", flush=True)


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


def try_acquire_runner_lock() -> bool:
    # 防重复提交：同一时刻只允许一个 runner 执行。
    # 这里用“创建锁文件”的方式做互斥（O_EXCL 是原子操作）。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now_ts = int(time.time())

    if LOCK_FILE.exists():
        try:
            raw = LOCK_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
            lock_ts = int(data.get("created_ts", 0) or 0)
        except Exception:
            lock_ts = 0

        # 兜底：锁文件长期不释放时，自动认定为过期锁并清理。
        if lock_ts > 0 and (now_ts - lock_ts) < LOCK_STALE_SECONDS:
            return False

        try:
            LOCK_FILE.unlink()
            log("检测到过期锁，已自动清理")
        except Exception:
            return False

    try:
        fd = os.open(
            str(LOCK_FILE),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
        os.write(
            fd,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "created_ts": now_ts,
                    "created_text": now_text(),
                },
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception as e:
        log("创建执行锁失败: " + str(e))
        return False


def release_runner_lock() -> None:
    # 释放互斥锁：无论成功失败，都尽量删除锁文件。
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        return


def resolve_repo_path(raw_path: str) -> Path:
    # 支持相对路径和绝对路径。
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        return (PROJECT_ROOT / path).resolve()
    return path


def run_empty_commit(repo_dir: Path, message: str) -> bool:
    # 在指定仓库执行一次空提交。
    try:
        proc = subprocess.run(
            ["git", "commit", "--allow-empty", "-m", message],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if proc.stdout:
            for line in str(proc.stdout).splitlines():
                text = str(line).strip()
                if text != "":
                    log(text)

        if proc.returncode != 0:
            if proc.stderr:
                for line in str(proc.stderr).splitlines():
                    text = str(line).strip()
                    if text != "":
                        log("ERROR: " + text)
            log("空提交失败，退出码 " + str(proc.returncode))
            return False

        log("空提交成功")
        return True
    except Exception as e:
        log("空提交失败: " + str(e))
        return False


def run_git_push(repo_dir: Path, remote: str, branch: str) -> bool:
    # 执行一次 git push。
    cmd = ["git", "push", str(remote)]
    if str(branch).strip() != "":
        cmd.append(str(branch))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if proc.stdout:
            for line in str(proc.stdout).splitlines():
                text = str(line).strip()
                if text != "":
                    log(text)

        if proc.returncode != 0:
            if proc.stderr:
                for line in str(proc.stderr).splitlines():
                    text = str(line).strip()
                    if text != "":
                        log("ERROR: " + text)
            log("push 失败，退出码 " + str(proc.returncode))
            return False

        log("push 成功")
        return True
    except Exception as e:
        log("push 失败: " + str(e))
        return False


def main() -> int:
    # 入口：只负责执行提交与 push。
    log("执行器已启动")
    ensure_plan_file_exists()

    while True:
        plan = read_plan()

        if not bool(plan.get("enabled", False)):
            time.sleep(60)
            continue

        if not bool(plan.get("pending", False)):
            time.sleep(60)
            continue

        # 关键：多个 runner 同时运行时，只有一个允许进入提交流程。
        if not try_acquire_runner_lock():
            time.sleep(2)
            continue

        try:
            repo_path = str(plan.get("repo_path", "")).strip()
            if repo_path == "":
                plan["pending"] = False
                plan["last_result"] = "missing_repo_path"
                write_plan(plan)
                time.sleep(60)
                continue

            repo_dir = resolve_repo_path(repo_path)
            if not repo_dir.exists():
                plan["pending"] = False
                plan["last_result"] = "repo_path_not_found"
                write_plan(plan)
                time.sleep(60)
                continue

            if not (repo_dir / ".git").exists():
                plan["pending"] = False
                plan["last_result"] = "not_git_repo"
                write_plan(plan)
                time.sleep(60)
                continue

            commit_message = str(plan.get("commit_message", "chore: keepalive")).strip()
            if commit_message == "":
                commit_message = "chore: keepalive"

            ok = run_empty_commit(repo_dir, commit_message)
            if not ok:
                plan["pending"] = False
                plan["last_result"] = "commit_failed"
                write_plan(plan)
                time.sleep(60)
                continue

            push_remote = str(plan.get("push_remote", "origin")).strip() or "origin"
            push_branch = str(plan.get("push_branch", "")).strip()
            ok_push = run_git_push(repo_dir, push_remote, push_branch)

            plan["pending"] = False
            plan["last_run_ts"] = int(time.time())
            plan["last_run_text"] = now_text()
            plan["last_result"] = "push_ok" if ok_push else "push_failed"
            write_plan(plan)

            time.sleep(60)
        finally:
            release_runner_lock()


if __name__ == "__main__":
    raise SystemExit(main())
