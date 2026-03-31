import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def load_process_watch_module():
    # 直接按文件路径加载模块，避免受包结构影响。
    module_path = Path(__file__).resolve().parent / "process_watch.py"
    spec = importlib.util.spec_from_file_location("process_watch", str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 process_watch.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProcessWatchTestCase(unittest.TestCase):
    # 这个用例只验证核心逻辑：
    # 启动事件 + 结束事件 能正确累计运行秒数并产出导出文件。
    def test_start_then_stop_accumulates_seconds_and_exports(self):
        pw = load_process_watch_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)

            # 把数据文件路径改到临时目录，避免污染真实目录。
            setattr(pw, "DATA_DIR", tmp_dir)
            setattr(pw, "PROCESS_WATCH_STATE_FILE", tmp_dir / "process_watch.json")
            setattr(
                pw, "PROCESS_WATCH_RULES_FILE", tmp_dir / "process_watch_rules.json"
            )
            setattr(
                pw, "PROCESS_WATCH_EVENTS_FILE", tmp_dir / "process_watch_events.jsonl"
            )
            setattr(
                pw, "PROCESS_WATCH_EXPORT_CSV", tmp_dir / "process_watch_export.csv"
            )

            # 每次测试前清空内存会话。
            with getattr(pw, "ACTIVE_SESSIONS_LOCK"):
                getattr(pw, "ACTIVE_SESSIONS").clear()

            # 规则文件：只监控 notepad.exe。
            getattr(pw, "PROCESS_WATCH_RULES_FILE").write_text(
                json.dumps(
                    {"watch_list": ["notepad.exe"]}, ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )

            # 数据文件：只存结果。
            pw.save_watch_state(
                {
                    "summary": {},
                    "updated_ts": 0,
                    "updated_text": "",
                }
            )

            # 固定时间，保证断言稳定。
            old_time_fn = getattr(pw, "time").time
            old_now_text_fn = getattr(pw, "now_text")
            try:
                getattr(pw, "time").time = lambda: 1770000100
                setattr(pw, "now_text", lambda: "2026-03-21 10:00:00")
                pw.handle_start_event("notepad.exe", 123)

                getattr(pw, "time").time = lambda: 1770000130
                setattr(pw, "now_text", lambda: "2026-03-21 10:00:30")
                pw.handle_stop_event("notepad.exe", 123)
            finally:
                getattr(pw, "time").time = old_time_fn
                setattr(pw, "now_text", old_now_text_fn)

            # 断言：累计秒数应为 30 秒。
            state = json.loads(
                getattr(pw, "PROCESS_WATCH_STATE_FILE").read_text(encoding="utf-8")
            )
            summary = state.get("summary", {}).get("notepad.exe", {})
            self.assertEqual(int(summary.get("total_seconds", 0)), 30)
            self.assertEqual(int(summary.get("start_count", 0)), 1)
            self.assertEqual(int(summary.get("stop_count", 0)), 1)
            self.assertEqual(bool(summary.get("is_running", True)), False)

            # 断言：事件文件有两行（start + stop）。
            lines = (
                getattr(pw, "PROCESS_WATCH_EVENTS_FILE")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            self.assertEqual(len(lines), 2)

            # 断言：CSV 导出文件已生成，且包含进程名。
            csv_text = getattr(pw, "PROCESS_WATCH_EXPORT_CSV").read_text(
                encoding="utf-8"
            )
            self.assertIn("process_name", csv_text)
            self.assertIn("notepad.exe", csv_text)

    # 这个用例验证“重启恢复活跃会话”后，stop 事件不会被记成 0 秒。
    def test_restore_active_session_after_restart_then_stop_not_zero(self):
        pw = load_process_watch_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)

            # 把数据文件路径改到临时目录，避免污染真实目录。
            setattr(pw, "DATA_DIR", tmp_dir)
            setattr(pw, "PROCESS_WATCH_STATE_FILE", tmp_dir / "process_watch.json")
            setattr(
                pw, "PROCESS_WATCH_RULES_FILE", tmp_dir / "process_watch_rules.json"
            )
            setattr(
                pw, "PROCESS_WATCH_EVENTS_FILE", tmp_dir / "process_watch_events.jsonl"
            )
            setattr(
                pw, "PROCESS_WATCH_EXPORT_CSV", tmp_dir / "process_watch_export.csv"
            )
            setattr(
                pw, "PROCESS_WATCH_ACTIVE_FILE", tmp_dir / "process_watch_active.json"
            )

            # 规则文件：只监控 notepad.exe。
            getattr(pw, "PROCESS_WATCH_RULES_FILE").write_text(
                json.dumps(
                    {"watch_list": ["notepad.exe"]}, ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )

            # 初始状态文件。
            pw.save_watch_state(
                {
                    "summary": {},
                    "updated_ts": 0,
                    "updated_text": "",
                }
            )

            old_time_fn = getattr(pw, "time").time
            old_now_text_fn = getattr(pw, "now_text")
            old_list_running_fn = getattr(pw, "list_running_watch_processes")

            try:
                # 第 1 阶段：先产生一次 start，并把活跃快照写入文件。
                getattr(pw, "time").time = lambda: 1770000100
                setattr(pw, "now_text", lambda: "2026-03-21 10:00:00")
                pw.handle_start_event("notepad.exe", 123)

                # 模拟 server 重启：清空内存会话。
                with getattr(pw, "ACTIVE_SESSIONS_LOCK"):
                    getattr(pw, "ACTIVE_SESSIONS").clear()

                # 重启后系统里该 PID 仍在运行，恢复会话。
                getattr(pw, "time").time = lambda: 1770000110
                setattr(
                    pw,
                    "list_running_watch_processes",
                    lambda: {"notepad.exe": {123}},
                )
                pw.restore_active_sessions_on_startup()

                # 第 2 阶段：稍后 stop，应该基于原 start_ts=100 计算为 30 秒。
                getattr(pw, "time").time = lambda: 1770000130
                setattr(pw, "now_text", lambda: "2026-03-21 10:00:30")
                pw.handle_stop_event("notepad.exe", 123)
            finally:
                getattr(pw, "time").time = old_time_fn
                setattr(pw, "now_text", old_now_text_fn)
                setattr(pw, "list_running_watch_processes", old_list_running_fn)

            state = json.loads(
                getattr(pw, "PROCESS_WATCH_STATE_FILE").read_text(encoding="utf-8")
            )
            summary = state.get("summary", {}).get("notepad.exe", {})
            self.assertEqual(int(summary.get("total_seconds", 0)), 30)

            lines = (
                getattr(pw, "PROCESS_WATCH_EVENTS_FILE")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            stop_event = json.loads(lines[-1])
            self.assertEqual(stop_event.get("type"), "stop")
            self.assertEqual(int(stop_event.get("session_seconds", 0)), 30)


if __name__ == "__main__":
    unittest.main()
