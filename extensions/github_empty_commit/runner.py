import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


# 项目根目录（ChronOS）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PLAN_FILE = DATA_DIR / "github_empty_commit_plan.json"


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


if __name__ == "__main__":
    raise SystemExit(main())
