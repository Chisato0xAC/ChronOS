// 这两个变量用于保存当前的 DP 和 GP 数值。
let currentDp = 0;
// 这里把 GP 的初始值设为 0。
let currentGp = 0;

// 这行代码拿到页面里显示 DP 的标签。
const currentDpElement = document.getElementById("currentDp");
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

// 这个函数从后端读取历史记录。
async function loadHistoryFromServer() {
  try {
    const response = await fetch("/api/state-history?limit=50", {
      cache: "no-store",
    });
    const result = await response.json();
    // 服务端返回的 items 是“最新在上”。
    renderHistory(result.items);
  } catch (error) {
    // 读取失败就显示一行提示，不影响 DP/GP 使用。
    historyListElement.textContent = "（历史记录读取失败）";
  }
}

// 这个函数统一处理 DP 更新，保证规则一致。
function applyDp(nextDp) {
  let safeDp = Number(nextDp);

  if (Number.isNaN(safeDp)) {
    return;
  }

  if (safeDp < 0) {
    safeDp = 0;
  }

  currentDp = Math.floor(safeDp);
  render();
  saveDpToFile();
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

// 这个函数连接后端的 SSE 接口：只要 state.json 有变化，后端会通知我们。
function startStateEventStream() {
  // EventSource 会一直保持连接，不需要计时器。
  const source = new EventSource("/api/state-events");

  // 收到名为 state 的事件时，重新读取 data/state.json。
  source.addEventListener("state", function () {
    loadStateFromFile();
    loadHistoryFromServer();
  });

  // 连接出错时，浏览器会自动重连。
  // 这里留一个提示，方便排查。
  source.onerror = function () {
    console.log("SSE 连接异常，浏览器将自动重连");
  };
}

// 这个函数把当前 DP 发给后端接口，后端会写入 state.json。
async function saveDpToFile() {
  try {
    await fetch("/api/save-dp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        dp: currentDp,
      }),
    });
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
startStateEventStream();

// 这个函数把 DP 增加 1，并刷新页面。
function addDp() {
  applyDp(currentDp + 1);
}

// 这个函数把 DP 减少 1，但不会小于 0，然后刷新页面。
function minusDp() {
  applyDp(currentDp - 1);
}

// 这个函数读取表达式，在当前 DP 的基础上做增减。
function setDpFromInput() {
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

  // 这行先从当前 DP 开始计算。
  let nextDp = currentDp;

  // 这段把每个片段转成数字并累加。
  for (let i = 0; i < parts.length; i = i + 1) {
    nextDp = nextDp + Number(parts[i]);
  }

  // 这行把计算结果交给统一更新函数。
  applyDp(nextDp);
}

// 点击 DP +1 按钮时，执行加 1。
addDpButtonElement.addEventListener("click", addDp);
// 点击 DP -1 按钮时，执行减 1。
minusDpButtonElement.addEventListener("click", minusDp);
// 点击设置 DP 按钮时，执行输入框设置逻辑。
setDpButtonElement.addEventListener("click", setDpFromInput);

// 点击撤销按钮时，请求后端撤销。
undoButtonElement.addEventListener("click", undoLastChange);
