import tkinter as tk


def blend_hex_color(start_hex: str, end_hex: str, ratio: float) -> str:
    # 把两个颜色按比例混合，ratio=0 用起始色，ratio=1 用结束色。
    s = start_hex.lstrip("#")
    e = end_hex.lstrip("#")

    sr = int(s[0:2], 16)
    sg = int(s[2:4], 16)
    sb = int(s[4:6], 16)

    er = int(e[0:2], 16)
    eg = int(e[2:4], 16)
    eb = int(e[4:6], 16)

    rr = int(sr + (er - sr) * ratio)
    rg = int(sg + (eg - sg) * ratio)
    rb = int(sb + (eb - sb) * ratio)

    return f"#{rr:02x}{rg:02x}{rb:02x}"


def main() -> None:
    # 第一步：创建一个空的悬浮窗。
    root = tk.Tk()

    # 第二步：设置无窗框，并始终置顶。
    root.overrideredirect(True)
    root.attributes("-topmost", True)

    # 第三步：设置半透明（0.0~1.0，数值越大越不透明）。
    root.attributes("-alpha", 0.9)

    # 第四步：给一个固定大小，并尽量居中显示。
    width = 240
    height = 140
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width - width) / 2)
    y = int((screen_height - height) / 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    # 第五步：不允许手动拉伸窗口大小。
    root.resizable(False, False)

    # 第六步：设置更干净的浅色背景。
    base_bg = "#f8fafc"
    root.configure(bg=base_bg)

    # 第七步：用一个内层框做细边框，整体更清爽。
    frame = tk.Frame(
        root,
        bg=base_bg,
        highlightthickness=1,
        highlightbackground="#d6ddea",
    )
    frame.pack(fill="both", expand=True)

    # 第八步：在内层框里绘制一个纵向渐变背景。
    gradient_canvas = tk.Canvas(frame, bd=0, highlightthickness=0)
    gradient_canvas.place(x=1, y=1, relwidth=1, relheight=1, width=-2, height=-2)

    def redraw_gradient(event=None):
        canvas_width = gradient_canvas.winfo_width()
        canvas_height = gradient_canvas.winfo_height()

        if canvas_width <= 0 or canvas_height <= 0:
            return

        gradient_canvas.delete("all")
        start_color = "#f8fafc"
        end_color = "#e9eef5"

        for row in range(canvas_height):
            ratio = row / max(canvas_height - 1, 1)
            line_color = blend_hex_color(start_color, end_color, ratio)
            gradient_canvas.create_line(0, row, canvas_width, row, fill=line_color)

    gradient_canvas.bind("<Configure>", redraw_gradient)

    # 第九步：右上角放一个简洁的关闭按钮（不加顶栏）。
    close_button = tk.Button(
        frame,
        text="X",
        bd=0,
        relief="flat",
        bg=base_bg,
        fg="#444444",
        activebackground="#e2e8f0",
        activeforeground="#000000",
        highlightthickness=0,
    )
    close_button.place(x=width - 22, y=6, width=16, height=16)

    # 第十步：支持拖动窗口（按住任意位置都能拖）。
    drag_state = {"x": 0, "y": 0}

    def on_drag_start(event):
        # 记录鼠标按下时的位置。
        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root

    def on_drag_move(event):
        # 根据鼠标移动的距离，更新窗口位置。
        dx = event.x_root - drag_state["x"]
        dy = event.y_root - drag_state["y"]

        x = root.winfo_x() + dx
        y = root.winfo_y() + dy

        root.geometry(f"+{x}+{y}")

        drag_state["x"] = event.x_root
        drag_state["y"] = event.y_root

    # 只在主体区域处理拖动，避免和关闭按钮冲突。
    frame.bind("<ButtonPress-1>", on_drag_start)
    frame.bind("<B1-Motion>", on_drag_move)
    gradient_canvas.bind("<ButtonPress-1>", on_drag_start)
    gradient_canvas.bind("<B1-Motion>", on_drag_move)

    # 第十一步：关闭按钮防误触。
    # 只有“按下后基本没移动”才算点击关闭。
    close_state = {"x": 0, "y": 0, "dragged": False}

    def on_close_press(event):
        close_state["x"] = event.x_root
        close_state["y"] = event.y_root
        close_state["dragged"] = False
        return "break"

    def on_close_motion(event):
        dx = abs(event.x_root - close_state["x"])
        dy = abs(event.y_root - close_state["y"])
        if dx >= 4 or dy >= 4:
            close_state["dragged"] = True
        return "break"

    def on_close_release(event):
        if not close_state["dragged"]:
            root.destroy()
        return "break"

    close_button.bind("<ButtonPress-1>", on_close_press)
    close_button.bind("<B1-Motion>", on_close_motion)
    close_button.bind("<ButtonRelease-1>", on_close_release)

    # 第十一步：进入窗口主循环。
    root.mainloop()


if __name__ == "__main__":
    main()
