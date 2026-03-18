// 这个文件专门放“系统通知”的功能。
// 目的：把通知逻辑和主程序（main.js）分开，避免混在一起。

// 这个函数负责发送一条系统通知。
// 注意：浏览器的系统通知必须先获得用户授权。
async function sendSystemNotification(title, body) {
  // 第一步：检查浏览器是否支持通知功能。
  if (!("Notification" in window)) {
    alert("你的浏览器不支持系统通知（Notification）。");
    return;
  }

  // 第二步：如果还没授权，就弹出授权请求。
  if (Notification.permission === "default") {
    try {
      await Notification.requestPermission();
    } catch (error) {
      alert("请求通知权限失败。");
      return;
    }
  }

  // 第三步：如果用户拒绝了，就提示如何开启。
  if (Notification.permission === "denied") {
    alert("你已拒绝通知权限。请在浏览器网站设置里允许通知后再试。");
    return;
  }

  // 第四步：真正发出系统通知。
  const safeTitle = String(title || "ChronOS 通知");
  const safeBody = String(body || "");

  new Notification(safeTitle, {
    body: safeBody,
  });
}

// 把函数挂到 window 上，这样 main.js 可以直接调用。
window.sendSystemNotification = sendSystemNotification;
