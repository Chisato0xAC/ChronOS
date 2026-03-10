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

// 这个函数负责把内存中的数值显示到页面上。
function render() {
  // 这行把 DP 显示为整数文本。
  currentDpElement.textContent = currentDp;
  // 这行把 GP 保留两位小数后再显示。
  currentGpElement.textContent = currentGp.toFixed(2);
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
  const response = await fetch("./data/state.json");
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

// 这行执行读取 JSON 并更新页面的流程。
loadStateFromFile();

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
