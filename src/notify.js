// 这个文件专门放“系统通知”的功能。
// 目的：把通知逻辑和主程序（main.js）分开，避免混在一起。

// 这个函数负责发送一条系统通知。
// 注意：浏览器的系统通知必须先获得用户授权。
// 第三个参数 options 用于控制是否允许弹权限请求。
async function sendSystemNotification(title, body, options) {
  const safeOptions = options && typeof options === "object" ? options : {};
  const allowPermissionPrompt = safeOptions.allowPermissionPrompt !== false;

  // 第一步：检查浏览器是否支持通知功能。
  if (!("Notification" in window)) {
    // 刷新页面或自动任务场景下不弹窗，只记日志。
    console.log("你的浏览器不支持系统通知（Notification）。");
    return;
  }

  // 第二步：如果还没授权，就弹出授权请求。
  if (Notification.permission === "default") {
    if (!allowPermissionPrompt) {
      // 静默模式：不主动弹权限请求。
      return;
    }

    try {
      await Notification.requestPermission();
    } catch (error) {
      console.log("请求通知权限失败。");
      return;
    }
  }

  // 第三步：如果用户拒绝了，就提示如何开启。
  if (Notification.permission === "denied") {
    console.log("你已拒绝通知权限。请在浏览器网站设置里允许通知后再试。");
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
