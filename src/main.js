// 这两个变量用于保存当前的 DP 和 GP 数值。
let currentDp = 0;
// 这里把 GP 的初始值设为 0。
let currentGp = 0;

// 这行代码拿到页面里显示 DP 的标签。
const currentDpElement = document.getElementById("currentDp");
// 这行代码拿到“当前周期 DP 变更”显示标签。
const currentCycleDpDeltaElement = document.getElementById("currentCycleDpDelta");
// 这行代码拿到页面里显示 GP 的标签。
const currentGpElement = document.getElementById("currentGp");
// 这行代码拿到 DP +1 按钮。
const addDpButtonElement = document.getElementById("addDpButton");
// 这行代码拿到 DP -1 按钮。
const minusDpButtonElement = document.getElementById("minusDpButton");
// 这行代码拿到 DP 输入框。
const dpInputElement = document.getElementById("dpInput");
// 这行代码拿到设置 DP 按钮。
const setDpButtonElement = document.getElementById("setDpButton");

// 这行代码拿到撤销按钮。
const undoButtonElement = document.getElementById("undoButton");

// 这行代码拿到历史记录显示区域。
const historyListElement = document.getElementById("historyList");
// 这行代码拿到“每日日报（简略）”显示区域。
const dailyReportSimpleElement = document.getElementById("dailyReportSimple");
// 这行代码拿到“每日日报-前一天”按钮。
const dailyReportPrevDayButtonElement = document.getElementById("dailyReportPrevDayButton");
// 这行代码拿到“每日日报-后一天”按钮。
const dailyReportNextDayButtonElement = document.getElementById("dailyReportNextDayButton");
// 这行代码拿到“服务状态”显示区域。
const serviceStatusElement = document.getElementById("serviceStatus");
// 这行代码拿到右侧便签输入框。
const noteInputElement = document.getElementById("noteInput");
// 这行代码拿到便签保存状态提示。
const noteSaveStatusElement = document.getElementById("noteSaveStatus");
// 这行代码拿到“打开悬浮窗”按钮。
const openFloatingWindowButtonElement = document.getElementById("openFloatingWindowButton");
// 这行代码拿到“导航栏位置”下拉框。
const navPositionSelectElement = document.getElementById("navPositionSelect");
// 这行代码拿到“导航栏卡片”本体。
const navBarCardElement = document.getElementById("navBarCard");
// 这行代码拿到“设置”按钮。
const taskbarSettingsButtonElement = document.getElementById("taskbarSettingsButton");
// 这行代码拿到“状态”按钮。
const taskbarStatusButtonElement = document.getElementById("taskbarStatusButton");
// 这行代码拿到“物品”按钮。
const taskbarItemsButtonElement = document.getElementById("taskbarItemsButton");
// 这行代码拿到“商店”按钮。
const taskbarStoreButtonElement = document.getElementById("taskbarStoreButton");
// 这行代码拿到“工具”按钮。
const taskbarToolsButtonElement = document.getElementById("taskbarToolsButton");
// 这行代码拿到“记录”按钮。
const taskbarRecordsButtonElement = document.getElementById("taskbarRecordsButton");
// 这行代码拿到“统计”按钮。
const taskbarStatsButtonElement = document.getElementById("taskbarStatsButton");
// 这行代码拿到“设置弹窗”。
const settingsPanelElement = document.getElementById("settingsPanel");
// 这行代码拿到“关闭设置弹窗”按钮。
const closeSettingsPanelButtonElement = document.getElementById("closeSettingsPanelButton");
// 这行代码拿到“统计弹窗”。
const statsPanelElement = document.getElementById("statsPanel");
// 这行代码拿到“统计弹窗内容”。
const statsPanelContentElement = document.getElementById("statsPanelContent");
// 这行代码拿到“关闭统计弹窗”按钮。
const closeStatsPanelButtonElement = document.getElementById("closeStatsPanelButton");
// 这行代码拿到“记录弹窗”。
const recordsPanelElement = document.getElementById("recordsPanel");
// 这行代码拿到“关闭记录弹窗”按钮。
const closeRecordsPanelButtonElement = document.getElementById("closeRecordsPanelButton");
// 这行代码拿到“工具弹窗”。
const toolsPanelElement = document.getElementById("toolsPanel");
// 这行代码拿到“关闭工具弹窗”按钮。
const closeToolsPanelButtonElement = document.getElementById("closeToolsPanelButton");
// 这行代码拿到主内容容器，用于给任务栏让出空间。
const mainRootElement = document.getElementById("mainRoot");
// 这行代码拿到“通知延迟秒数”输入框。
const notifyDelayHoursInputElement = document.getElementById("notifyDelayHoursInput");
// 这行代码拿到“通知延迟分钟”输入框。
const notifyDelayMinutesInputElement = document.getElementById("notifyDelayMinutesInput");
// 这行代码拿到“通知延迟秒数”输入框。
const notifyDelaySecondsInputElement = document.getElementById("notifyDelaySecondsInput");
// 这行代码拿到“通知时间预览”标签。
const notifySchedulePreviewElement = document.getElementById("notifySchedulePreview");
// 这行代码拿到“通知任务列表”显示区域。
const notifyTaskListElement = document.getElementById("notifyTaskList");
// 这行代码拿到“开发中提示条”。
const cuteDevToastElement = document.getElementById("cuteDevToast");
// 单页布局下，历史区固定显示最近几条，避免出现翻页。
const HISTORY_FETCH_LIMIT = 16;
// 记录 SSE 是否已经成功连接过一次（用于判断“重连”）。
let hasOpenedStateStreamOnce = false;
// 这个变量保存便签自动保存的定时器。
let noteAutoSaveTimer = null;
// 这个数组保存“待触发”的通知任务（从后端读取）。
let notifyPendingTasks = [];
// 这个对象用于标记“正在触发中”的任务，避免重复触发。
let notifyTaskInFlightMap = {};
// 这个变量保存“通知任务轮询”定时器（无任务时会停掉）。
let notifyTasksPollTimer = null;
// 这个变量保存“每日日报”当前查看的日期偏移：0=今天，-1=昨天。
let dailyReportDayOffset = 0;
// 这个变量保存“最近一次日报原始数据”，给统计弹窗复用。
let latestDailyReportData = null;
// 这个定时器用于控制“开发中提示条”的渐变消失。
let cuteDevToastTimer = null;
// 这个标记表示：后台重连时先记住“待刷新”，等页面回到前台再刷新。
let pendingReloadWhenVisible = false;

// 这个函数根据面板开关状态，更新任务栏按钮高亮。
function refreshTaskbarActiveButtons() {
  if (taskbarSettingsButtonElement) {
    taskbarSettingsButtonElement.classList.toggle(
      "taskbar-button-active",
      Boolean(settingsPanelElement && settingsPanelElement.hidden === false)
    );
  }

  if (taskbarRecordsButtonElement) {
    taskbarRecordsButtonElement.classList.toggle(
      "taskbar-button-active",
      Boolean(recordsPanelElement && recordsPanelElement.hidden === false)
    );
  }

  if (taskbarToolsButtonElement) {
    taskbarToolsButtonElement.classList.toggle(
      "taskbar-button-active",
      Boolean(toolsPanelElement && toolsPanelElement.hidden === false)
    );
  }

  if (taskbarStatsButtonElement) {
    taskbarStatsButtonElement.classList.toggle(
      "taskbar-button-active",
      Boolean(statsPanelElement && statsPanelElement.hidden === false)
    );
  }
}

// 这个函数显示“开发中”提示，并让它渐变消失。
function showCuteDevelopingToast(event) {
  // 只响应“真实鼠标/触控抬起”，避免刷新/恢复焦点时被动触发 click。
  if (!event || event.type !== "pointerup" || event.isTrusted !== true) {
    return;
  }

  if (event.button !== 0) {
    return;
  }

  if (!cuteDevToastElement) {
    return;
  }

  cuteDevToastElement.classList.remove("toast-show");
  void cuteDevToastElement.offsetWidth;
  cuteDevToastElement.classList.add("toast-show");

  if (cuteDevToastTimer !== null) {
    window.clearTimeout(cuteDevToastTimer);
  }

  cuteDevToastTimer = window.setTimeout(function () {
    cuteDevToastElement.classList.remove("toast-show");
    cuteDevToastTimer = null;
  }, 1700);
}

// 这个函数把导航栏贴到页面边缘（上/下/左/右，类似开始菜单停靠）。
function applyNavPosition(positionValue) {
  if (!navBarCardElement) {
    return;
  }

  const allowed = {
    top: "nav-top",
    bottom: "nav-bottom",
    left: "nav-left",
    right: "nav-right",
  };

  const safePosition = String(positionValue || "top").toLowerCase();
  const targetClass = allowed[safePosition] || allowed.top;

  navBarCardElement.classList.remove("nav-top", "nav-bottom", "nav-left", "nav-right");
  navBarCardElement.classList.add(targetClass);

  // 任务栏换边后，重新给主内容让出对应空间，避免内容被挡住。
  syncMainRootOffset();

  if (navPositionSelectElement) {
    navPositionSelectElement.value = safePosition in allowed ? safePosition : "top";
  }
}

// 这个函数负责显示或隐藏“设置弹窗”。
function setSettingsPanelVisible(visible) {
  if (!settingsPanelElement) {
    return;
  }

  if (visible) {
    settingsPanelElement.hidden = false;
    refreshTaskbarActiveButtons();
    return;
  }

  settingsPanelElement.hidden = true;
  refreshTaskbarActiveButtons();
}

// 这个函数负责显示或隐藏“统计弹窗”。
function setStatsPanelVisible(visible) {
  if (!statsPanelElement) {
    return;
  }

  if (visible) {
    statsPanelElement.hidden = false;
    refreshTaskbarActiveButtons();
    return;
  }

  statsPanelElement.hidden = true;
  refreshTaskbarActiveButtons();
}

// 这个函数负责显示或隐藏“记录弹窗”。
function setRecordsPanelVisible(visible) {
  if (!recordsPanelElement) {
    return;
  }

  if (visible) {
    recordsPanelElement.hidden = false;
    refreshTaskbarActiveButtons();
    return;
  }

  recordsPanelElement.hidden = true;
  refreshTaskbarActiveButtons();
}

// 这个函数负责显示或隐藏“工具弹窗”。
function setToolsPanelVisible(visible) {
  if (!toolsPanelElement) {
    return;
  }

  if (visible) {
    toolsPanelElement.hidden = false;
    refreshTaskbarActiveButtons();
    return;
  }

  toolsPanelElement.hidden = true;
  refreshTaskbarActiveButtons();
}

// 这个函数用于一次性关闭任务栏相关弹窗，避免多个弹窗同时打开。
function closeAllTaskbarPanels() {
  setSettingsPanelVisible(false);
  setStatsPanelVisible(false);
  setRecordsPanelVisible(false);
  setToolsPanelVisible(false);
}

// 这个函数判断：目标节点是否在某个容器里（含容器自身）。
function isInsideElement(containerElement, targetNode) {
  if (!containerElement || !targetNode) {
    return false;
  }
  return containerElement.contains(targetNode);
}

// 这个函数根据任务栏当前位置，给主内容设置安全边距。
function syncMainRootOffset() {
  if (!mainRootElement || !navBarCardElement) {
    return;
  }

  const barHeight = navBarCardElement.offsetHeight;
  const barWidth = navBarCardElement.offsetWidth;
  const barRect = navBarCardElement.getBoundingClientRect();
  const statusRect = serviceStatusElement ? serviceStatusElement.getBoundingClientRect() : null;

  // 先清空，再按方向加一个边距。
  mainRootElement.style.marginTop = "0px";
  mainRootElement.style.marginBottom = "0px";
  mainRootElement.style.marginLeft = "0px";
  mainRootElement.style.marginRight = "0px";

  // 额外预留 10 像素，避免视觉上贴得太紧。
  const safeGap = 10;

  if (navBarCardElement.classList.contains("nav-top")) {
    let topOffset = barHeight + safeGap;

    // 顶部时如果和右上角 Status 区域重叠，就让内容再下移，避免被挡。
    if (statusRect) {
      const isHorizontalOverlap = !(barRect.right < statusRect.left || barRect.left > statusRect.right);
      if (isHorizontalOverlap) {
        const maxBottom = Math.max(barRect.bottom, statusRect.bottom);
        topOffset = Math.ceil(maxBottom + safeGap);
      }
    }

    mainRootElement.style.marginTop = String(topOffset) + "px";
    return;
  }

  if (navBarCardElement.classList.contains("nav-bottom")) {
    mainRootElement.style.marginBottom = String(barHeight + safeGap) + "px";
    return;
  }

  if (navBarCardElement.classList.contains("nav-left")) {
    mainRootElement.style.marginLeft = String(barWidth + safeGap) + "px";
    return;
  }

  if (navBarCardElement.classList.contains("nav-right")) {
    mainRootElement.style.marginRight = String(barWidth + safeGap) + "px";
  }
}

// 这个函数根据当前偏移更新“每日日报”的左右按钮状态。
function renderDailyReportSwitchButtons() {
  if (dailyReportPrevDayButtonElement) {
    dailyReportPrevDayButtonElement.disabled = false;
  }

  if (dailyReportNextDayButtonElement) {
    // 0 代表今天，不允许再往“未来日期”切换。
    dailyReportNextDayButtonElement.disabled = dailyReportDayOffset >= 0;
  }
}

// 这个函数按“是否有待触发任务”决定是否轮询后端。
function syncNotifyTasksPollingByPendingCount() {
  const hasPendingTasks = Array.isArray(notifyPendingTasks) && notifyPendingTasks.length > 0;

  // 有任务：确保轮询开启（每 15 秒对后端同步一次）。
  if (hasPendingTasks) {
    if (notifyTasksPollTimer === null) {
      notifyTasksPollTimer = window.setInterval(loadNotifyTasksFromServer, 15000);
    }
    return;
  }

  // 无任务：立刻停止轮询，避免持续 GET /api/notify-tasks。
  if (notifyTasksPollTimer !== null) {
    window.clearInterval(notifyTasksPollTimer);
    notifyTasksPollTimer = null;
  }
}

// 这个函数返回“当前周期开始时间戳（秒）”。
function getCurrentCycleStartTsSeconds() {
  const now = new Date();
  const cycleStart = new Date(now);

  // 周期从每天 4:00 开始。
  cycleStart.setHours(4, 0, 0, 0);

  // 如果现在还没到今天 4:00，说明当前周期是从昨天 4:00 开始。
  if (now.getTime() < cycleStart.getTime()) {
    cycleStart.setDate(cycleStart.getDate() - 1);
  }

  return Math.floor(cycleStart.getTime() / 1000);
}

// 这个函数把“当前周期 DP 变更”显示到 DP 旁边。
function renderCurrentCycleDpDelta(deltaValue) {
  if (!currentCycleDpDeltaElement) {
    return;
  }

  const delta = Number(deltaValue);
  if (Number.isNaN(delta)) {
    currentCycleDpDeltaElement.textContent = "(0)";
    currentCycleDpDeltaElement.className = "";
    return;
  }

  const safeDelta = Math.floor(delta);
  if (safeDelta > 0) {
    currentCycleDpDeltaElement.textContent = "(+" + String(safeDelta) + ")";
    currentCycleDpDeltaElement.className = "dp-plus";
    return;
  }

  if (safeDelta < 0) {
    currentCycleDpDeltaElement.textContent = "(" + String(safeDelta) + ")";
    currentCycleDpDeltaElement.className = "dp-minus";
    return;
  }

  currentCycleDpDeltaElement.textContent = "(0)";
  currentCycleDpDeltaElement.className = "";
}

// 这个函数从历史记录计算“当前周期 DP 总变更”。
function calculateCurrentCycleDpDeltaFromHistory(historyRecords) {
  if (!Array.isArray(historyRecords) || historyRecords.length === 0) {
    return 0;
  }

  const cycleStartTs = getCurrentCycleStartTsSeconds();
  let totalDelta = 0;

  for (let i = 0; i < historyRecords.length; i = i + 1) {
    const item = historyRecords[i] || {};
    const itemTs = Number(item.ts);
    if (Number.isNaN(itemTs) || itemTs < cycleStartTs) {
      continue;
    }

    if (!Array.isArray(item.changes)) {
      continue;
    }

    for (let j = 0; j < item.changes.length; j = j + 1) {
      const ch = item.changes[j] || {};
      if (String(ch.path || "") !== "dp") {
        continue;
      }

      const fromValue = Number(ch.from);
      const toValue = Number(ch.to);
      if (Number.isNaN(fromValue) || Number.isNaN(toValue)) {
        continue;
      }

      totalDelta += toValue - fromValue;
    }
  }

  return Math.floor(totalDelta);
}

// 这个函数负责把内存中的数值显示到页面上。
function render() {
  // 这行把 DP 显示为整数文本。
  currentDpElement.textContent = currentDp;
  // 这行把 GP 保留两位小数后再显示。
  currentGpElement.textContent = currentGp.toFixed(2);
}

// 这个函数负责把历史记录显示到页面上。
function renderHistory(historyRecords) {
  // 如果后端没返回数组，就显示“暂无”。
  if (!Array.isArray(historyRecords) || historyRecords.length === 0) {
    historyListElement.textContent = "（暂无）";
    return;
  }

  // 每条记录一行，尽量用最直白的文字展示。
  // 显示格式（定宽对齐）：
  // 2026-03-14 12:00:00  save_dp        dp: 10 -> 12 (+2)   备注
  const lines = [];

  // 简单对齐用的宽度（不用 CSS，只靠空格对齐）。
  // 注意：这里的“完全对齐”只在等宽字体里成立；<pre> 默认是等宽字体。
  const typeWidth = 14;
  const changeWidth = 34;

  function fitText(text, width) {
    // 把文本限制在固定宽度内，避免某一列太长把后面的列挤歪。
    // 如果超长，用 "..." 截断（只用 ASCII）。
    const s = String(text || "");
    if (s.length <= width) {
      return s;
    }
    if (width <= 3) {
      return s.slice(0, width);
    }
    return s.slice(0, width - 3) + "...";
  }

  function padRight(text, width) {
    const s = fitText(text, width);
    if (s.length >= width) {
      return s;
    }
    return s + " ".repeat(width - s.length);
  }

  for (let i = 0; i < historyRecords.length; i = i + 1) {
    const item = historyRecords[i] || {};
    const text = String(item.text || "");
    const type = String(item.type || "");
    const note = String(item.note || "");

    // 把 changes 里 dp/gp 的变化简单拼出来。
    let changeText = "";
    if (Array.isArray(item.changes)) {
      const parts = [];
      for (let j = 0; j < item.changes.length; j = j + 1) {
        const ch = item.changes[j] || {};
        const path = String(ch.path || "");
        const fromValue = ch.from;
        const toValue = ch.to;
        if (path === "dp" || path === "gp") {
          // 尽量把“变化值(delta)”也显示出来，方便一眼看懂。
          const fromNumber = Number(fromValue);
          const toNumber = Number(toValue);

          let deltaText = "";
          if (!Number.isNaN(fromNumber) && !Number.isNaN(toNumber)) {
            const delta = toNumber - fromNumber;
            // dp 一般是整数；gp 可能是小数。
            let deltaDisplay = String(delta);
            if (path === "dp") {
              deltaDisplay = String(Math.floor(delta));
            } else {
              deltaDisplay = String(delta.toFixed(2));
            }

            if (delta > 0) {
              deltaText = " (+" + deltaDisplay + ")";
            } else if (delta < 0) {
              deltaText = " (" + deltaDisplay + ")";
            } else {
              deltaText = " (0)";
            }
          }

          parts.push(path + ": " + String(fromValue) + " -> " + String(toValue) + " " + deltaText);
        }
      }
      if (parts.length > 0) {
        changeText = parts.join("; ");
      }
    }

    // 时间固定 19 位：YYYY-MM-DD HH:MM:SS
    const left = padRight(text, 19);
    const midType = padRight(type, typeWidth);
    const midChange = padRight(changeText, changeWidth);
    const rightNote = note;
    // 用 2 个空格当“列分隔”，更容易看。
    lines.push(left + "  " + midType + "  " + midChange + "  " + rightNote);
  }

  historyListElement.textContent = lines.join("\n");
}

// 这个函数把“带正负号”的数字格式化为文本（例如：+3、-2、0）。
function formatSignedNumber(value, fixedDigits) {
  const n = Number(value);
  if (Number.isNaN(n) || !Number.isFinite(n)) {
    return "0";
  }

  let text = "0";
  if (typeof fixedDigits === "number") {
    text = n.toFixed(fixedDigits);
  } else {
    text = String(Math.floor(n));
  }

  if (n > 0) {
    return "+" + text;
  }
  return text;
}

// 这个函数把“每日日报（简略）”渲染到首页。
function renderDailyReportSimple(data) {
  if (!dailyReportSimpleElement) {
    return;
  }

  if (!data || data.ok !== true) {
    dailyReportSimpleElement.textContent = "（日报读取失败）";
    return;
  }

  const totalEvents = Math.floor(Number(data.total_events) || 0);
  const dpChangeCount = Math.floor(Number(data.dp_change_count) || 0);
  const gpChangeCount = Math.floor(Number(data.gp_change_count) || 0);
  const dpDeltaTotal = Math.floor(Number(data.dp_delta_total) || 0);
  const gpDeltaTotal = Number(data.gp_delta_total) || 0;
  const dpMaxGain = Math.floor(Number(data.dp_max_gain) || 0);
  const dpMaxCost = Math.floor(Number(data.dp_max_cost) || 0);
  let reportDate = String(data.report_date || "").trim();
  if (reportDate === "") {
    const dayStartText = String(data.day_start_text || "").trim();
    reportDate = dayStartText.slice(0, 10);
  }

  const lines = [];
  lines.push("统计日期：" + reportDate);
  lines.push("有效变更条数：" + String(totalEvents));

  // 没有变更的项目不显示，只展示当天实际发生变更的条目。
  if (dpChangeCount > 0) {
    lines.push("DP 变更次数：" + String(dpChangeCount) + "，合计：" + formatSignedNumber(dpDeltaTotal));
    lines.push("单日最大DP获取：+" + String(Math.max(0, dpMaxGain)));
    lines.push("单日最大DP消耗：-" + String(Math.max(0, dpMaxCost)));
  }
  if (gpChangeCount > 0) {
    lines.push("GP 变更次数：" + String(gpChangeCount) + "，合计：" + formatSignedNumber(gpDeltaTotal, 2));
  }

  if (dpChangeCount <= 0 && gpChangeCount <= 0) {
    lines.push("（当天没有 DP/GP 变更）");
  }

  dailyReportSimpleElement.textContent = lines.join("\n");
}

// 这个函数把统计数据渲染到“统计弹窗”。
function renderStatsPanel(data) {
  if (!statsPanelContentElement) {
    return;
  }

  if (!data || data.ok !== true) {
    statsPanelContentElement.textContent = "（统计读取失败）";
    return;
  }

  const historyDayDpMaxGain = Math.floor(Number(data.history_day_dp_max_gain) || 0);
  const historyDayDpMaxGainDate = String(data.history_day_dp_max_gain_date || "").trim();
  const historyDayDpMaxCost = Math.floor(Number(data.history_day_dp_max_cost) || 0);
  const historyDayDpMaxCostDate = String(data.history_day_dp_max_cost_date || "").trim();

  const lines = [];
  if (historyDayDpMaxGainDate !== "") {
    lines.push(
      "历史单日DP最大增量：+"
        + String(Math.max(0, historyDayDpMaxGain))
        + "（"
        + historyDayDpMaxGainDate
        + "）"
    );
  } else {
    lines.push("历史单日DP最大增量：+0");
  }

  if (historyDayDpMaxCostDate !== "") {
    lines.push(
      "历史单日DP最大减量：-"
        + String(Math.max(0, historyDayDpMaxCost))
        + "（"
        + historyDayDpMaxCostDate
        + "）"
    );
  } else {
    lines.push("历史单日DP最大减量：-0");
  }

  statsPanelContentElement.textContent = lines.join("\n");
}

// 这个函数打开统计弹窗，并显示最新统计内容。
function openStatsPanel() {
  const shouldCloseCurrent = statsPanelElement && statsPanelElement.hidden === false;
  closeAllTaskbarPanels();
  if (shouldCloseCurrent) {
    return;
  }

  renderStatsPanel(latestDailyReportData);
  setStatsPanelVisible(true);
}

// 这个函数打开记录弹窗。
function openRecordsPanel() {
  const shouldCloseCurrent = recordsPanelElement && recordsPanelElement.hidden === false;
  closeAllTaskbarPanels();
  if (shouldCloseCurrent) {
    return;
  }

  setRecordsPanelVisible(true);
}

// 这个函数打开工具弹窗。
function openToolsPanel() {
  const shouldCloseCurrent = toolsPanelElement && toolsPanelElement.hidden === false;
  closeAllTaskbarPanels();
  if (shouldCloseCurrent) {
    return;
  }

  setToolsPanelVisible(true);
}

// 这个函数从后端读取“每日日报（简略）”。
async function loadDailyReportSimpleFromServer() {
  if (!dailyReportSimpleElement) {
    return;
  }

  try {
    const response = await fetch("/api/daily-report-simple?day_offset=" + String(dailyReportDayOffset), {
      cache: "no-store",
    });

    const result = await response.json();
    if (!response.ok) {
      dailyReportSimpleElement.textContent = "（日报读取失败）";
      latestDailyReportData = null;
      renderStatsPanel(null);
      return;
    }

    latestDailyReportData = result;
    renderDailyReportSimple(result);
    renderStatsPanel(result);
  } catch (error) {
    dailyReportSimpleElement.textContent = "（日报读取失败）";
    latestDailyReportData = null;
    renderStatsPanel(null);
  }
}

// 这个函数切换到“前一天”的每日日报。
function showPreviousDailyReportDay() {
  dailyReportDayOffset = dailyReportDayOffset - 1;
  renderDailyReportSwitchButtons();
  loadDailyReportSimpleFromServer();
}

// 这个函数切换到“后一天”的每日日报。
function showNextDailyReportDay() {
  // 不允许切到未来日期（今天之后）。
  if (dailyReportDayOffset >= 0) {
    renderDailyReportSwitchButtons();
    return;
  }

  dailyReportDayOffset = dailyReportDayOffset + 1;
  renderDailyReportSwitchButtons();
  loadDailyReportSimpleFromServer();
}

// 这个函数从后端读取历史记录。
async function loadHistoryFromServer() {
  try {
    const response = await fetch("/api/state-history?limit=" + HISTORY_FETCH_LIMIT, {
      cache: "no-store",
    });
    const result = await response.json();
    const items = Array.isArray(result.items) ? result.items : [];
    // 服务端返回的 items 是“最新在上”。
    renderHistory(items);
    renderCurrentCycleDpDelta(calculateCurrentCycleDpDeltaFromHistory(items));
  } catch (error) {
    // 读取失败就显示一行提示，不影响 DP/GP 使用。
    historyListElement.textContent = "（历史记录读取失败）";
    renderCurrentCycleDpDelta(0);
  }
}

// 这个函数从后端读取便签内容，并显示到右侧输入框。
async function loadNoteFromServer() {
  // 如果页面上没有便签框，就直接结束。
  if (!noteInputElement || !noteSaveStatusElement) {
    return;
  }

  noteSaveStatusElement.textContent = "（正在读取便签...）";

  try {
    const response = await fetch("/api/note", {
      cache: "no-store",
    });
    const result = await response.json();

    if (!result || result.ok !== true) {
      noteSaveStatusElement.textContent = "（便签读取失败）";
      return;
    }

    noteInputElement.value = String(result.note || "");
    noteSaveStatusElement.textContent = "（已读取）";
  } catch (error) {
    noteSaveStatusElement.textContent = "（便签读取失败）";
  }
}

// 这个函数把便签内容保存到后端文件。
async function saveNoteToServer(noteText) {
  if (!noteSaveStatusElement) {
    return;
  }

  noteSaveStatusElement.textContent = "（保存中...）";

  try {
    const response = await fetch("/api/save-note", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        note: String(noteText || ""),
      }),
    });

    const result = await response.json();
    if (!response.ok || !result || result.ok !== true) {
      noteSaveStatusElement.textContent = "（保存失败）";
      return;
    }

    noteSaveStatusElement.textContent = "（已自动保存）";
  } catch (error) {
    noteSaveStatusElement.textContent = "（保存失败）";
  }
}

// 这个函数请求后端打开悬浮窗。
async function openFloatingWindowFromServer() {
  try {
    const response = await fetch("/api/open-floating-window", {
      method: "POST",
    });

    if (!response.ok) {
      console.log("打开悬浮窗失败");
      return;
    }

    try {
      const result = await response.json();
      if (!result || result.ok !== true) {
        console.log("打开悬浮窗失败", result);
      }
    } catch (error) {
      console.log("打开悬浮窗失败", error);
    }
  } catch (error) {
    console.log("打开悬浮窗失败", error);
  }
}

// 这个函数在输入后稍等一下再保存，避免每个字符都发请求。
function scheduleNoteAutoSave() {
  if (!noteInputElement) {
    return;
  }

  if (noteAutoSaveTimer !== null) {
    window.clearTimeout(noteAutoSaveTimer);
  }

  noteAutoSaveTimer = window.setTimeout(function () {
    saveNoteToServer(noteInputElement.value);
  }, 300);
}

// 这个函数统一处理 DP 更新，保证规则一致。
function applyDp(nextDp, baseDp) {
  let safeDp = Number(nextDp);

  if (Number.isNaN(safeDp)) {
    return;
  }

  const safeBaseDp = Number(baseDp);
  if (Number.isNaN(safeBaseDp)) {
    return;
  }

  if (safeDp < 0) {
    safeDp = 0;
  }

  currentDp = Math.floor(safeDp);
  render();
  saveDpToFile(Math.floor(safeDp), Math.floor(safeBaseDp));
}

// 这个函数负责从项目里的 JSON 文件读取 DP 和 GP。
async function loadStateFromFile() {
  // 这行请求 data/state.json 文件。
  const response = await fetch("./data/state.json", {
    // 这行告诉浏览器不要缓存，确保拿到最新文件内容。
    cache: "no-store",
  });
  // 这行把 JSON 文本解析成 JavaScript 对象。
  const state = await response.json();

  // 这行把读到的 DP 先转成数字。
  const dpNumber = Number(state.dp);
  // 这行把读到的 GP 先转成数字。
  const gpNumber = Number(state.gp);

  // 这段判断确保 DP 是有效数字并且不小于 0。
  if (!Number.isNaN(dpNumber) && dpNumber >= 0) {
    // 这行把有效的 DP 取整后保存。
    currentDp = Math.floor(dpNumber);
  }

  // 这段判断确保 GP 是有效数字并且不小于 0。
  if (!Number.isNaN(gpNumber) && gpNumber >= 0) {
    // 这行把有效的 GP 保存下来。
    currentGp = gpNumber;
  }

  // 这行把读取后的数值渲染到页面。
  render();
}

// 这个函数连接后端的 SSE 统一事件通道：只要 state.json 有变化，后端会通知我们。
function startStateEventStream() {
  // EventSource 会一直保持连接，不需要计时器。
  const source = new EventSource("/api/events");

  // 第一次连接只做标记；后续如果是“重连成功”，说明后端很可能重启过。
  // 如果页面正在前台，就立刻整页刷新；如果页面在后台，就等用户切回前台时再刷新。
  source.onopen = function () {
    serviceStatusElement.textContent = "🟢 Connected";

    if (!hasOpenedStateStreamOnce) {
      hasOpenedStateStreamOnce = true;
      return;
    }

    if (document.visibilityState === "visible") {
      window.location.reload();
      return;
    }

    pendingReloadWhenVisible = true;
  };

  // 收到名为 state 的事件时，重新读取 data/state.json。
  source.addEventListener("state", function () {
    loadStateFromFile();
    loadHistoryFromServer();
    loadDailyReportSimpleFromServer();
  });

  // 收到名为 notify_tasks 的事件时，重新读取通知任务列表。
  source.addEventListener("notify_tasks", function () {
    loadNotifyTasksFromServer();
  });

  // 连接出错时，浏览器会自动重连。
  // 这里留一个提示，方便排查。
  source.onerror = function () {
    serviceStatusElement.textContent = "🔴 Disconnected";
    console.log("SSE 连接异常，浏览器将自动重连");
  };
}

// 这个函数把当前 DP 发给后端接口，后端会写入 state.json。
async function saveDpToFile(targetDp, baseDp) {
  try {
    const response = await fetch("/api/save-dp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        dp: Number(targetDp),
        base_dp: Number(baseDp),
      }),
    });

    if (!response.ok) {
      // 后端拒绝保存时，重新拉取最新状态。
      await loadStateFromFile();
      await loadHistoryFromServer();
      return;
    }

    try {
      const result = await response.json();
      if (!result || result.ok !== true) {
        await loadStateFromFile();
        await loadHistoryFromServer();
      }
    } catch (error) {
      // JSON 解析失败时也刷新一次，避免 UI 停留在旧值。
      await loadStateFromFile();
      await loadHistoryFromServer();
    }
  } catch (error) {
    // 保存失败时，只在控制台提示，不打断页面使用。
    console.error("保存 DP 失败", error);
  }
}

// 这个函数请求后端执行撤销。
async function undoLastChange() {
  try {
    const response = await fetch("/api/undo", {
      method: "POST",
    });

    const result = await response.json();
    if (!result.ok) {
      console.log("没有可撤销的记录", result);
    }
  } catch (error) {
    console.error("撤销失败", error);
  }
}

// 这行执行读取 JSON 并更新页面的流程。
loadStateFromFile();
loadHistoryFromServer();
renderDailyReportSwitchButtons();
loadDailyReportSimpleFromServer();
loadNoteFromServer();
startStateEventStream();

// 这个函数把 DP 增加 1，并刷新页面。
function addDp() {
  applyDp(currentDp + 1, currentDp);
}

// 这个函数把 DP 减少 1，但不会小于 0，然后刷新页面。
function minusDp() {
  applyDp(currentDp - 1, currentDp);
}

// 这个函数读取表达式，在当前 DP 的基础上做增减。
async function setDpFromInput() {
  // 这行拿到输入框里的原始文本。
  const rawExpression = dpInputElement.value;
  // 这行去掉表达式里的空格，避免空格影响解析。
  let expression = rawExpression.replace(/\s+/g, "");

  // 如果输入为空，就直接结束，不做修改。
  if (expression === "") {
    return;
  }

  // 如果第一个字符是数字，就自动当作加法，例如 10-3 会变成 +10-3。
  if (/^\d/.test(expression)) {
    expression = "+" + expression;
  }

  // 这行按“符号 + 数字”提取片段，例如 +10、-3。
  const parts = expression.match(/[+-]\d+/g);

  // 如果提取结果为空，或者和原表达式不一致，说明格式不合法。
  if (!parts || parts.join("") !== expression) {
    return;
  }

  // 在计算前先读取最新的 DP，避免用旧值导致偏差。
  try {
    await loadStateFromFile();
  } catch (error) {
    // 读取失败时就继续使用当前内存里的数值。
  }

  // 这行先从当前 DP 开始计算。
  let nextDp = currentDp;

  // 这段把每个片段转成数字并累加。
  for (let i = 0; i < parts.length; i = i + 1) {
    nextDp = nextDp + Number(parts[i]);
  }

  // 这行把计算结果交给统一更新函数。
  applyDp(nextDp, currentDp);

  // 应用成功后清空输入框，方便下一次输入。
  dpInputElement.value = "";
}

// 点击 DP +1 按钮时，执行加 1。
addDpButtonElement.addEventListener("click", addDp);
// 点击 DP -1 按钮时，执行减 1。
minusDpButtonElement.addEventListener("click", minusDp);
// 点击设置 DP 按钮时，执行输入框设置逻辑。
setDpButtonElement.addEventListener("click", setDpFromInput);

// 在 DP 输入框按下 Enter 时，也执行“应用表达式”。
dpInputElement.addEventListener("keydown", function (event) {
  if (event.key !== "Enter") {
    return;
  }

  // 阻止默认行为，避免出现意外提交或提示音。
  event.preventDefault();
  setDpFromInput();
});

// 点击撤销按钮时，请求后端撤销。
undoButtonElement.addEventListener("click", undoLastChange);

// 点击“日报左箭头”时，切到前一天。
if (dailyReportPrevDayButtonElement) {
  dailyReportPrevDayButtonElement.addEventListener("click", showPreviousDailyReportDay);
}

// 点击“日报右箭头”时，切到后一天。
if (dailyReportNextDayButtonElement) {
  dailyReportNextDayButtonElement.addEventListener("click", showNextDailyReportDay);
}

// 输入便签时，自动触发保存。
if (noteInputElement) {
  noteInputElement.addEventListener("input", scheduleNoteAutoSave);
}

// 点击“打开悬浮窗”按钮时，请求后端启动悬浮窗。
if (openFloatingWindowButtonElement) {
  openFloatingWindowButtonElement.addEventListener("click", openFloatingWindowFromServer);
}

// 下拉框一变化就立即切换位置，不需要再点按钮。
if (navPositionSelectElement) {
  navPositionSelectElement.addEventListener("change", function () {
    applyNavPosition(navPositionSelectElement.value);
  });

  // 页面启动时先应用一次默认位置。
  applyNavPosition(navPositionSelectElement.value);
}

// 点击“设置”按钮时，打开设置弹窗。
if (taskbarSettingsButtonElement) {
  taskbarSettingsButtonElement.addEventListener("click", function () {
    const shouldCloseCurrent = settingsPanelElement && settingsPanelElement.hidden === false;
    closeAllTaskbarPanels();
    if (shouldCloseCurrent) {
      return;
    }

    setSettingsPanelVisible(true);
  });
}

// 点击“状态”按钮时，显示“开发中”提示。
if (taskbarStatusButtonElement) {
  taskbarStatusButtonElement.addEventListener("pointerup", function (event) {
    showCuteDevelopingToast(event);
  });
}

// 点击“物品”按钮时，显示“开发中”提示。
if (taskbarItemsButtonElement) {
  taskbarItemsButtonElement.addEventListener("pointerup", function (event) {
    showCuteDevelopingToast(event);
  });
}

// 点击“商店”按钮时，显示“开发中”提示。
if (taskbarStoreButtonElement) {
  taskbarStoreButtonElement.addEventListener("pointerup", function (event) {
    showCuteDevelopingToast(event);
  });
}

// 点击“工具”按钮时，打开工具弹窗。
if (taskbarToolsButtonElement) {
  taskbarToolsButtonElement.addEventListener("click", openToolsPanel);
}

// 点击“记录”按钮时，打开记录弹窗。
if (taskbarRecordsButtonElement) {
  taskbarRecordsButtonElement.addEventListener("click", openRecordsPanel);
}

// 点击“统计”按钮时，跳到统计区域。
if (taskbarStatsButtonElement) {
  taskbarStatsButtonElement.addEventListener("click", openStatsPanel);
}

// 点击“关闭统计弹窗”按钮时，关闭统计弹窗。
if (closeStatsPanelButtonElement) {
  closeStatsPanelButtonElement.addEventListener("click", function () {
    setStatsPanelVisible(false);
  });
}

// 点击“关闭记录弹窗”按钮时，关闭记录弹窗。
if (closeRecordsPanelButtonElement) {
  closeRecordsPanelButtonElement.addEventListener("click", function () {
    setRecordsPanelVisible(false);
  });
}

// 点击“关闭工具弹窗”按钮时，关闭工具弹窗。
if (closeToolsPanelButtonElement) {
  closeToolsPanelButtonElement.addEventListener("click", function () {
    setToolsPanelVisible(false);
  });
}

// 点击“关闭”按钮时，关闭设置弹窗。
if (closeSettingsPanelButtonElement) {
  closeSettingsPanelButtonElement.addEventListener("click", function () {
    setSettingsPanelVisible(false);
  });
}

// 窗口尺寸变化时重新计算一次，保证不遮挡。
window.addEventListener("resize", syncMainRootOffset);

// 点击任务栏和弹窗外部区域时，自动关闭任务栏弹窗。
document.addEventListener("click", function (event) {
  const target = event.target;

  // 点在任务栏按钮区时，不执行外部关闭。
  if (isInsideElement(navBarCardElement, target)) {
    return;
  }

  // 点在任一弹窗内部时，也不关闭。
  if (isInsideElement(settingsPanelElement, target)) {
    return;
  }
  if (isInsideElement(statsPanelElement, target)) {
    return;
  }
  if (isInsideElement(recordsPanelElement, target)) {
    return;
  }
  if (isInsideElement(toolsPanelElement, target)) {
    return;
  }

  closeAllTaskbarPanels();
});

// 按下 Esc 键时，关闭当前任务栏弹窗。
document.addEventListener("keydown", function (event) {
  if (event.key !== "Escape") {
    return;
  }

  closeAllTaskbarPanels();
});

// ---------------------------
// 通知功能（只做“接线”，逻辑在 notify.js）
// ---------------------------

// 这行代码拿到“通知测试”按钮。
const notifyButtonElement = document.getElementById("notifyButton");

// 这个函数负责把数字补成两位字符串（例如：5 -> 05）。
function padTwoDigits(value) {
  const safeValue = Math.floor(Math.max(0, Number(value) || 0));
  if (safeValue < 10) {
    return "0" + String(safeValue);
  }
  return String(safeValue);
}

// 这个函数把“总秒数”转成可读文本（例如：01:02:03）。
function formatDelaySecondsAsHms(totalSeconds) {
  let safeTotal = Math.floor(Number(totalSeconds) || 0);
  if (safeTotal < 0) {
    safeTotal = 0;
  }

  const hours = Math.floor(safeTotal / 3600);
  const minutes = Math.floor((safeTotal % 3600) / 60);
  const seconds = Math.floor(safeTotal % 60);

  return padTwoDigits(hours) + ":" + padTwoDigits(minutes) + ":" + padTwoDigits(seconds);
}

// 这个函数把时间戳（秒）转成 HH:MM:SS 文本。
function formatClockByTs(tsSeconds) {
  const d = new Date(Number(tsSeconds) * 1000);
  return padTwoDigits(d.getHours()) + ":" + padTwoDigits(d.getMinutes()) + ":" + padTwoDigits(d.getSeconds());
}

// 这个函数把“分/秒”限制在 0-59，避免输入超出范围。
function clampMinuteAndSecondInputs() {
  if (notifyDelayMinutesInputElement) {
    let m = Number(notifyDelayMinutesInputElement.value);
    if (Number.isNaN(m) || !Number.isFinite(m)) {
      m = 0;
    }
    m = Math.floor(m);
    if (m < 0) {
      m = 0;
    }
    if (m > 59) {
      m = 59;
    }
    notifyDelayMinutesInputElement.value = String(m);
  }

  if (notifyDelaySecondsInputElement) {
    let s = Number(notifyDelaySecondsInputElement.value);
    if (Number.isNaN(s) || !Number.isFinite(s)) {
      s = 0;
    }
    s = Math.floor(s);
    if (s < 0) {
      s = 0;
    }
    if (s > 59) {
      s = 59;
    }
    notifyDelaySecondsInputElement.value = String(s);
  }
}

// 这个函数读取“时分秒”输入，并换算成总秒数。
function getNotifyDelaySecondsFromInputs() {
  clampMinuteAndSecondInputs();

  let hours = 0;
  let minutes = 0;
  let seconds = 5;

  if (notifyDelayHoursInputElement) {
    const inputHours = Number(notifyDelayHoursInputElement.value);
    if (!Number.isNaN(inputHours) && Number.isFinite(inputHours) && inputHours >= 0) {
      hours = Math.floor(inputHours);
    }
  }

  if (notifyDelayMinutesInputElement) {
    const inputMinutes = Number(notifyDelayMinutesInputElement.value);
    if (!Number.isNaN(inputMinutes) && Number.isFinite(inputMinutes) && inputMinutes >= 0) {
      minutes = Math.floor(inputMinutes);
    }
  }

  if (notifyDelaySecondsInputElement) {
    const inputSeconds = Number(notifyDelaySecondsInputElement.value);
    if (!Number.isNaN(inputSeconds) && Number.isFinite(inputSeconds) && inputSeconds >= 0) {
      seconds = Math.floor(inputSeconds);
    }
  }

  return hours * 3600 + minutes * 60 + seconds;
}

// 这个函数把“预计通知时间”显示出来（例如：将在 14:30:05 通知）。
function renderNotifySchedulePreview() {
  if (!notifySchedulePreviewElement) {
    return;
  }

  const delaySeconds = getNotifyDelaySecondsFromInputs();
  const notifyAt = new Date(Date.now() + delaySeconds * 1000);

  const hh = padTwoDigits(notifyAt.getHours());
  const mm = padTwoDigits(notifyAt.getMinutes());
  const ss = padTwoDigits(notifyAt.getSeconds());

  notifySchedulePreviewElement.textContent = "将在 " + hh + ":" + mm + ":" + ss + " 通知";
}

// 这个函数把“待触发任务”列表渲染到页面。
function renderNotifyTaskList() {
  if (!notifyTaskListElement) {
    return;
  }

  if (!Array.isArray(notifyPendingTasks) || notifyPendingTasks.length === 0) {
    notifyTaskListElement.textContent = "（暂无）";
    return;
  }

  const lines = [];
  for (let i = 0; i < notifyPendingTasks.length; i = i + 1) {
    const task = notifyPendingTasks[i] || {};
    const title = String(task.title || "ChronOS 通知");
    const body = String(task.body || "");
    const dueTs = Number(task.due_ts || 0);
    const dueText = formatClockByTs(dueTs);

    const remainSeconds = Math.max(0, Math.floor(dueTs - Date.now() / 1000));
    const remainText = formatDelaySecondsAsHms(remainSeconds);

    let oneLine = "- [" + dueText + "] " + title + "（剩余 " + remainText + "）";
    if (body !== "") {
      oneLine = oneLine + " " + body;
    }
    lines.push(oneLine);
  }

  notifyTaskListElement.textContent = lines.join("\n");
}

// 这个函数从后端读取通知任务，并只保留 pending 状态。
async function loadNotifyTasksFromServer() {
  try {
    const response = await fetch("/api/notify-tasks", {
      cache: "no-store",
    });

    const result = await response.json();
    if (!response.ok || !result || result.ok !== true) {
      return;
    }

    const items = Array.isArray(result.items) ? result.items : [];
    const pending = [];
    for (let i = 0; i < items.length; i = i + 1) {
      const item = items[i] || {};
      if (String(item.status || "") !== "pending") {
        continue;
      }
      pending.push(item);
    }

    // 按到点时间升序，越早到点越靠前。
    pending.sort(function (a, b) {
      return Number(a.due_ts || 0) - Number(b.due_ts || 0);
    });

    notifyPendingTasks = pending;
    syncNotifyTasksPollingByPendingCount();
    renderNotifyTaskList();
  } catch (error) {
    // 忽略读取失败，不打断其他功能。
  }
}

// 这个函数把某个任务标记为已完成（写回后端文件）。
async function markNotifyTaskDone(taskId) {
  try {
    await fetch("/api/notify-task-complete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: String(taskId || ""),
      }),
    });
  } catch (error) {
    // 完成标记失败就先忽略，下轮会再尝试。
  }
}

// 这个函数尝试触发一个已到点的通知任务。
async function triggerNotifyTask(task) {
  const taskId = String(task.id || "");
  if (taskId === "") {
    return;
  }

  if (notifyTaskInFlightMap[taskId] === true) {
    return;
  }
  notifyTaskInFlightMap[taskId] = true;

  try {
    const title = String(task.title || "ChronOS 通知");
    const body = String(task.body || "");
    const finalBody = body === "" ? "到点了。" : body;

    if (typeof window.sendSystemNotification === "function") {
      // 自动触发任务使用“静默模式”：不在刷新后弹权限申请。
      await window.sendSystemNotification(title, finalBody, {
        allowPermissionPrompt: false,
      });
    }

    await markNotifyTaskDone(taskId);
    await loadNotifyTasksFromServer();
  } finally {
    delete notifyTaskInFlightMap[taskId];
  }
}

// 这个函数每秒检查一次：凡是到点的 pending 任务，立即触发。
function tickNotifyTasks() {
  const nowTs = Math.floor(Date.now() / 1000);

  for (let i = 0; i < notifyPendingTasks.length; i = i + 1) {
    const task = notifyPendingTasks[i] || {};
    const dueTs = Number(task.due_ts || 0);
    if (Number.isNaN(dueTs)) {
      continue;
    }
    if (dueTs > nowTs) {
      continue;
    }

    triggerNotifyTask(task);
  }

  // 同时刷新“到点预览”和“剩余时间”显示，避免静止。
  renderNotifySchedulePreview();
  renderNotifyTaskList();
}

// 这个函数负责发布一个新的通知任务到后端。
async function createNotifyTaskToServer(delaySeconds) {
  const safeDelaySeconds = Math.max(0, Math.floor(Number(delaySeconds) || 0));

  try {
    const response = await fetch("/api/notify-task-create", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: "ChronOS 通知",
        body: "这是你设置的延迟通知（" + String(safeDelaySeconds) + " 秒后）。",
        delay_seconds: safeDelaySeconds,
      }),
    });

    const result = await response.json();
    if (!response.ok || !result || result.ok !== true) {
      return;
    }

    await loadNotifyTasksFromServer();
  } catch (error) {
    // 创建失败只记控制台，不打断页面。
    console.log("创建通知任务失败", error);
  }
}

// 输入变化时，实时刷新“预计通知时间”。
if (notifyDelayHoursInputElement) {
  notifyDelayHoursInputElement.addEventListener("input", renderNotifySchedulePreview);
}
if (notifyDelayMinutesInputElement) {
  notifyDelayMinutesInputElement.addEventListener("input", renderNotifySchedulePreview);
}
if (notifyDelaySecondsInputElement) {
  notifyDelaySecondsInputElement.addEventListener("input", renderNotifySchedulePreview);
}

// 页面加载后先渲染一次预览。
renderNotifySchedulePreview();

// 启动任务列表读取：刷新页面后也能恢复未到点任务。
loadNotifyTasksFromServer();

// 每秒更新一次，解决“预计通知时间静止”的问题。
window.setInterval(tickNotifyTasks, 1000);

// 页面回到前台时，如果之前有“待刷新”，就在这里补一次整页刷新。
// 没有待刷新时，只补拉通知任务，避免极端情况下错过 SSE 事件。
document.addEventListener("visibilitychange", function () {
  if (document.visibilityState === "visible") {
    if (pendingReloadWhenVisible) {
      pendingReloadWhenVisible = false;
      window.location.reload();
      return;
    }

    loadNotifyTasksFromServer();
  }
});

// 点击“通知测试”按钮时，调用通知模块。
notifyButtonElement.addEventListener("click", async function () {
  // 这里不写通知细节，只负责调用。
  if (typeof window.sendSystemNotification !== "function") {
    console.log("通知模块未加载：请确认 notify.js 已被引入。");
    return;
  }

  // 先读输入框里的“时分秒”，并换算成总秒数，然后创建任务。
  const delaySeconds = getNotifyDelaySecondsFromInputs();
  await createNotifyTaskToServer(delaySeconds);
});
