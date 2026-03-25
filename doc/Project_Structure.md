# ChronOS 文件结构说明

这份文档用最直白的话说明：每个目录主要放什么。

## 1) 根目录总览

```text
ChronOS/
├─ AGENTS.md
├─ ChronOS-dev.bat
├─ ChronOS.vbs
├─ chronos_config.py
├─ server.py
├─ .gitignore
├─ config/
├─ data/
├─ doc/
├─ extensions/
├─ logs/
├─ src/
└─ tools/
```

## 2) 每个目录是做什么的

### config/

- 放“规则和配置文件”（JSON）。
- 例如：B 站配置、进程监控规则、GitHub 空提交配置。

### data/

- 放“运行中产生的数据文件”。
- 例如：状态文件、事件记录、导出结果。

### doc/

- 放项目文档。
- `concepts/`：概念说明。
- `rules/`：规则与使用说明。
- `versions/`：版本记录（每个版本一个文件）。

### extensions/

- 放扩展功能代码和扩展规则。
- `github_empty_commit/`：GitHub 空提交功能代码。
- `rules/`：扩展规则模板 JSON。

### logs/

- 放服务运行日志。
- 例如：标准输出日志、错误日志。

### src/

- 放主功能代码。
- `crawler/`：爬虫模块。
- `monitor/`：进程监控模块。
- `index.html`、`main.js`、`notify.js`：前端页面和脚本。

### tools/

- 放开发辅助工具。
- 例如：自动重载脚本、事件发送脚本、githooks 安装脚本。

## 3) 目前关键文件举例

- `server.py`：主服务入口。
- `chronos_config.py`：全局配置读取/管理。
- `ChronOS-dev.bat`：Windows 开发启动脚本。
- `config/github_empty_commit.json`：空提交任务配置。
- `data/state.json`：运行状态数据。
- `doc/versions/CURRENT.md`：当前开发版本标记。

## 4) 使用建议

- 想改“规则”：先看 `config/`。
- 想查“历史数据”：看 `data/`。
- 想看“功能说明”：看 `doc/`。
- 想定位“业务代码”：先从 `src/` 和 `extensions/` 开始。
