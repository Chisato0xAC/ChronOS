进程监控名单设置手册

只需要改这一个文件：

- `config/process_watch_rules.json`

文件内容示例：

```json
{
  "watch_list": [
    "notepad.exe",
    "Code.exe"
  ]
}
```

说明：

- `watch_list` 里每一项都是要监控的进程名（包含 `.exe`）。
- 改完后，重启服务即可生效。
