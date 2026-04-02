Managed Children (Server Scheduler)

- 这个文件说明：`server.py` 如何托管子进程。
- 子进程清单在 `config/managed_children.json`。
- `server.py` 启动时会读取清单并启动子进程。
- `server.py` 退出时会停止全部托管子进程。

## 配置文件格式

```json
{
  "children": [
    {
      "name": "process_watch",
      "cmd": ["python", "-X", "utf8", "-u", "src/monitor/process_watch.py"],
      "cwd": ".",
      "auto_restart": true
    }
  ]
}
```

## 字段说明

- `name`：子进程名字（用于日志和管理）。
- `cmd`：启动命令数组。
  - `python` 会自动替换为当前主程序的 Python 路径。
- `cwd`：工作目录（相对项目根目录）。
- `auto_restart`：子进程异常退出后是否自动拉起。

## 新增一个子进程（最小步骤）

1. 先在项目内新建脚本（建议放到对应模块目录）。
2. 再在 `config/managed_children.json` 的 `children` 里新增一项。
3. 重启 `server.py`，让主调度器重新加载配置。
