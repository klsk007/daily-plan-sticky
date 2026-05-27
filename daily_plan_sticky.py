import csv
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog


APP_DIR = Path(__file__).resolve().parent
TASKS_FILE = APP_DIR / "active_tasks.json"
COMPLETED_FILE = APP_DIR / "completed_tasks.csv"
SETTINGS_FILE = APP_DIR / "settings.json"
ALIPAY_QR_FILE = APP_DIR / "alipay_qr.png"
STARTUP_SHORTCUT_NAME = "每日计划便签.lnk"


try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
except Exception:
    pystray = None
    Image = None
    ImageDraw = None
    ImageTk = None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if not parts:
        parts.append(f"{secs}秒")
    return "".join(parts)


@dataclass
class Task:
    id: str
    text: str
    created_at: str


class DailyPlanSticky:
    def __init__(self) -> None:
        self.settings = self.load_settings()
        self.tasks: list[Task] = self.load_tasks()
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.geometry_save_after: str | None = None
        self.tray_icon = None
        self.tray_thread: threading.Thread | None = None
        self.is_exiting = False

        self.root = tk.Tk()
        self.root.title("每日计划")
        self.root.geometry(self.settings.get("geometry", "360x520+80+80"))
        self.root.minsize(320, 280)
        self.root.attributes("-topmost", bool(self.settings.get("topmost", True)))
        self.root.configure(bg="#f7f1d5")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Configure>", self.on_configure)

        self.ensure_startup_shortcut()
        self.build_ui()
        self.render_tasks()

    def build_ui(self) -> None:
        self.header = tk.Frame(self.root, bg="#283845", height=36, cursor="fleur")
        self.header.pack(fill="x")
        self.header.bind("<ButtonPress-1>", self.start_move)
        self.header.bind("<B1-Motion>", self.do_move)
        self.header.bind("<ButtonRelease-1>", lambda _event: self.save_settings())

        title = tk.Label(
            self.header,
            text="每日计划",
            bg="#283845",
            fg="white",
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        title.pack(side="left", padx=10)
        title.bind("<ButtonPress-1>", self.start_move)
        title.bind("<B1-Motion>", self.do_move)

        close_btn = tk.Button(
            self.header,
            text="×",
            command=self.hide_to_tray,
            bg="#283845",
            fg="white",
            activebackground="#3e5263",
            activeforeground="white",
            bd=0,
            font=("Microsoft YaHei UI", 13),
            width=3,
        )
        close_btn.pack(side="right")

        self.pin_btn = tk.Button(
            self.header,
            text=self.topmost_button_text(),
            command=self.toggle_topmost,
            bg="#283845",
            fg="white",
            activebackground="#3e5263",
            activeforeground="white",
            bd=0,
            font=("Microsoft YaHei UI", 9),
            padx=6,
        )
        self.pin_btn.pack(side="right", padx=(0, 4))

        self.startup_btn = tk.Button(
            self.header,
            text=self.startup_button_text(),
            command=self.toggle_startup,
            bg="#283845",
            fg="white",
            activebackground="#3e5263",
            activeforeground="white",
            bd=0,
            font=("Microsoft YaHei UI", 9),
            padx=6,
        )
        self.startup_btn.pack(side="right", padx=(0, 4))

        donate_btn = tk.Button(
            self.header,
            text="支持",
            command=self.show_donation,
            bg="#283845",
            fg="white",
            activebackground="#3e5263",
            activeforeground="white",
            bd=0,
            font=("Microsoft YaHei UI", 9),
            padx=6,
        )
        donate_btn.pack(side="right", padx=(0, 4))

        entry_row = tk.Frame(self.root, bg="#f7f1d5")
        entry_row.pack(fill="x", padx=12, pady=(12, 8))

        self.task_entry = tk.Entry(
            entry_row,
            font=("Microsoft YaHei UI", 10),
            relief="solid",
            bd=1,
        )
        self.task_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.task_entry.bind("<Return>", lambda _event: self.add_task())

        add_btn = tk.Button(
            entry_row,
            text="+",
            command=self.add_task,
            bg="#2f6f73",
            fg="white",
            activebackground="#24595c",
            activeforeground="white",
            bd=0,
            font=("Microsoft YaHei UI", 15, "bold"),
            width=3,
        )
        add_btn.pack(side="right", padx=(8, 0), ipady=1)

        self.list_outer = tk.Frame(self.root, bg="#f7f1d5")
        self.list_outer.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.canvas = tk.Canvas(
            self.list_outer,
            bg="#f7f1d5",
            highlightthickness=0,
            borderwidth=0,
        )
        self.scrollbar = tk.Scrollbar(self.list_outer, orient="vertical", command=self.canvas.yview)
        self.tasks_frame = tk.Frame(self.canvas, bg="#f7f1d5")

        self.tasks_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.tasks_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", self.resize_task_frame)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        footer = tk.Frame(self.root, bg="#eadfba")
        footer.pack(fill="x")
        self.status = tk.Label(
            footer,
            text="",
            bg="#eadfba",
            fg="#35424b",
            anchor="w",
            font=("Microsoft YaHei UI", 9),
        )
        self.status.pack(side="left", fill="x", expand=True, padx=10, pady=6)

        open_log_btn = tk.Button(
            footer,
            text="记录",
            command=self.open_completed_file,
            bg="#eadfba",
            fg="#35424b",
            activebackground="#ded0a7",
            bd=0,
            font=("Microsoft YaHei UI", 9),
        )
        open_log_btn.pack(side="right", padx=8)

    def show_donation(self) -> None:
        if not ALIPAY_QR_FILE.exists():
            messagebox.showinfo(
                "支持作者",
                f"把支付宝收款码图片保存为：\n{ALIPAY_QR_FILE}\n\n之后点“支持”就会显示收款码。",
                parent=self.root,
            )
            return

        if Image is None:
            try:
                os.startfile(ALIPAY_QR_FILE)
            except Exception as exc:
                messagebox.showerror("打开失败", f"无法打开收款码：\n{exc}", parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("支持作者")
        win.configure(bg="#f7f1d5")
        win.resizable(False, False)
        win.attributes("-topmost", bool(self.root.attributes("-topmost")))

        try:
            original = Image.open(ALIPAY_QR_FILE)
            original.thumbnail((320, 320))
            photo = ImageTk.PhotoImage(original)
        except Exception as exc:
            messagebox.showerror("读取失败", f"无法读取收款码图片：\n{exc}", parent=self.root)
            win.destroy()
            return

        label = tk.Label(win, text="如果这个小工具帮你少写了几次日报，欢迎支持维护。", bg="#f7f1d5", fg="#283845")
        label.pack(padx=14, pady=(12, 8))
        image_label = tk.Label(win, image=photo, bg="#f7f1d5")
        image_label.image = photo
        image_label.pack(padx=14, pady=(0, 12))
        close_btn = tk.Button(win, text="关闭", command=win.destroy, bg="#2f6f73", fg="white", bd=0, padx=18, pady=5)
        close_btn.pack(pady=(0, 12))

    def load_settings(self) -> dict:
        if not SETTINGS_FILE.exists():
            return {"geometry": "360x520+80+80", "topmost": True, "startup": True}
        try:
            settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings.setdefault("geometry", "360x520+80+80")
            settings.setdefault("topmost", True)
            settings.setdefault("startup", True)
            return settings
        except Exception:
            return {"geometry": "360x520+80+80", "topmost": True, "startup": True}

    def save_settings(self) -> None:
        if self.is_exiting:
            return
        if self.root.state() == "normal":
            self.settings["geometry"] = self.root.geometry()
        self.settings["topmost"] = bool(self.root.attributes("-topmost"))
        SETTINGS_FILE.write_text(
            json.dumps(self.settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def on_configure(self, _event: tk.Event) -> None:
        if self.geometry_save_after is not None:
            self.root.after_cancel(self.geometry_save_after)
        self.geometry_save_after = self.root.after(500, self.save_settings)

    def start_move(self, event: tk.Event) -> None:
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def do_move(self, event: tk.Event) -> None:
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    def resize_task_frame(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def topmost_button_text(self) -> str:
        return "置顶" if bool(self.settings.get("topmost", True)) else "普通"

    def toggle_topmost(self) -> None:
        new_value = not bool(self.root.attributes("-topmost"))
        self.root.attributes("-topmost", new_value)
        self.settings["topmost"] = new_value
        self.pin_btn.configure(text="置顶" if new_value else "普通")
        self.save_settings()

    def startup_button_text(self) -> str:
        return "开机" if self.settings.get("startup", True) else "手动"

    def startup_shortcut_path(self) -> Path:
        startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return startup / STARTUP_SHORTCUT_NAME

    def ensure_startup_shortcut(self) -> None:
        if self.settings.get("startup", True):
            self.create_shortcut(self.startup_shortcut_path())

    def toggle_startup(self) -> None:
        enabled = not bool(self.settings.get("startup", True))
        self.settings["startup"] = enabled
        shortcut = self.startup_shortcut_path()
        if enabled:
            self.create_shortcut(shortcut)
        elif shortcut.exists():
            shortcut.unlink()
        self.startup_btn.configure(text=self.startup_button_text())
        self.save_settings()

    def create_shortcut(self, shortcut_path: Path) -> None:
        try:
            shortcut_path.parent.mkdir(parents=True, exist_ok=True)
            from win32com.client import Dispatch

            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(str(shortcut_path))
            shortcut.TargetPath = str(APP_DIR / "启动每日计划便签.bat")
            shortcut.WorkingDirectory = str(APP_DIR)
            shortcut.WindowStyle = 7
            shortcut.Description = "每日计划悬浮便签"
            shortcut.Save()
        except Exception:
            try:
                import pythoncom
                from win32com.client import Dispatch

                pythoncom.CoInitialize()
                shell = Dispatch("WScript.Shell")
                shortcut = shell.CreateShortcut(str(shortcut_path))
                shortcut.TargetPath = str(APP_DIR / "启动每日计划便签.bat")
                shortcut.WorkingDirectory = str(APP_DIR)
                shortcut.WindowStyle = 7
                shortcut.Description = "每日计划悬浮便签"
                shortcut.Save()
            except Exception:
                pass

    def load_tasks(self) -> list[Task]:
        if not TASKS_FILE.exists():
            return []
        try:
            raw_tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            return [Task(**item) for item in raw_tasks]
        except Exception as exc:
            messagebox.showwarning("读取失败", f"任务文件读取失败，将从空列表开始。\n{exc}")
            return []

    def save_tasks(self) -> None:
        TASKS_FILE.write_text(
            json.dumps([asdict(task) for task in self.tasks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_task(self) -> None:
        text = self.task_entry.get().strip()
        if not text:
            return
        self.tasks.append(Task(id=str(uuid.uuid4()), text=text, created_at=now_iso()))
        self.task_entry.delete(0, tk.END)
        self.save_tasks()
        self.render_tasks()

    def render_tasks(self) -> None:
        for child in self.tasks_frame.winfo_children():
            child.destroy()

        if not self.tasks:
            empty = tk.Label(
                self.tasks_frame,
                text="今天还没有任务",
                bg="#f7f1d5",
                fg="#7b735f",
                font=("Microsoft YaHei UI", 10),
                pady=20,
            )
            empty.pack(fill="x")
        else:
            for task in self.tasks:
                self.add_task_row(task)

        self.update_status()

    def add_task_row(self, task: Task) -> None:
        row = tk.Frame(self.tasks_frame, bg="#fff8dc", highlightthickness=1, highlightbackground="#dfd2a4")
        row.pack(fill="x", pady=4)

        label = tk.Label(
            row,
            text=task.text,
            bg="#fff8dc",
            fg="#20272b",
            justify="left",
            anchor="w",
            wraplength=210,
            font=("Microsoft YaHei UI", 10),
            padx=8,
            pady=8,
        )
        label.pack(side="left", fill="both", expand=True)
        label.bind("<Double-Button-1>", lambda _event, task_id=task.id: self.edit_task(task_id))

        done_var = tk.BooleanVar(value=False)
        done = tk.Checkbutton(
            row,
            variable=done_var,
            command=lambda task_id=task.id, task_row=row: self.complete_task(task_id, task_row),
            bg="#fff8dc",
            activebackground="#fff8dc",
            width=3,
        )
        done.pack(side="right", padx=(2, 6))

        delete_btn = tk.Button(
            row,
            text="删",
            command=lambda task_id=task.id: self.delete_task(task_id),
            bg="#fff8dc",
            fg="#8c3d2f",
            activebackground="#efe4bd",
            bd=0,
            font=("Microsoft YaHei UI", 9),
            width=3,
        )
        delete_btn.pack(side="right", padx=(0, 2))

        edit_btn = tk.Button(
            row,
            text="改",
            command=lambda task_id=task.id: self.edit_task(task_id),
            bg="#fff8dc",
            fg="#35424b",
            activebackground="#efe4bd",
            bd=0,
            font=("Microsoft YaHei UI", 9),
            width=3,
        )
        edit_btn.pack(side="right", padx=(0, 2))

    def edit_task(self, task_id: str) -> None:
        task = next((item for item in self.tasks if item.id == task_id), None)
        if task is None:
            return
        new_text = simpledialog.askstring("编辑任务", "任务内容：", initialvalue=task.text, parent=self.root)
        if new_text is None:
            return
        new_text = new_text.strip()
        if not new_text:
            messagebox.showinfo("未修改", "任务内容不能为空。")
            return
        task.text = new_text
        self.save_tasks()
        self.render_tasks()

    def delete_task(self, task_id: str) -> None:
        task = next((item for item in self.tasks if item.id == task_id), None)
        if task is None:
            return
        if not messagebox.askyesno("删除任务", f"删除这条任务吗？\n\n{task.text}", parent=self.root):
            return
        self.tasks = [item for item in self.tasks if item.id != task_id]
        self.save_tasks()
        self.render_tasks()

    def complete_task(self, task_id: str, row: tk.Frame) -> None:
        task = next((item for item in self.tasks if item.id == task_id), None)
        if task is None:
            return

        completed_at = datetime.now()
        created_at = datetime.fromisoformat(task.created_at)
        spent_seconds = (completed_at - created_at).total_seconds()
        self.append_completed_task(task, completed_at, spent_seconds)

        self.tasks = [item for item in self.tasks if item.id != task_id]
        self.save_tasks()
        self.fade_completed_row(row)
        self.update_status()
        self.root.after(900, self.render_tasks)

    def fade_completed_row(self, row: tk.Frame) -> None:
        row.configure(bg="#d8dbc9", highlightbackground="#b5baa8")
        for child in row.winfo_children():
            try:
                child.configure(bg="#d8dbc9", fg="#6b715f", state="disabled")
            except tk.TclError:
                try:
                    child.configure(bg="#d8dbc9", state="disabled")
                except tk.TclError:
                    pass

    def append_completed_task(self, task: Task, completed_at: datetime, spent_seconds: float) -> None:
        needs_header = not COMPLETED_FILE.exists()
        with COMPLETED_FILE.open("a", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            if needs_header:
                writer.writerow(["任务", "开始时间", "完成时间", "花费时间", "花费秒数", "日期"])
            writer.writerow(
                [
                    task.text,
                    task.created_at,
                    completed_at.isoformat(timespec="seconds"),
                    format_duration(spent_seconds),
                    int(spent_seconds),
                    completed_at.strftime("%Y-%m-%d"),
                ]
            )

    def read_today_stats(self) -> tuple[int, int]:
        if not COMPLETED_FILE.exists():
            return 0, 0
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        seconds = 0
        try:
            with COMPLETED_FILE.open("r", newline="", encoding="utf-8-sig") as file:
                for row in csv.DictReader(file):
                    if row.get("日期") != today:
                        continue
                    count += 1
                    try:
                        seconds += int(float(row.get("花费秒数", "0") or 0))
                    except ValueError:
                        pass
        except Exception:
            return 0, 0
        return count, seconds

    def update_status(self) -> None:
        today_count, today_seconds = self.read_today_stats()
        self.status.configure(
            text=f"未完成：{len(self.tasks)}    今日完成：{today_count}    今日耗时：{format_duration(today_seconds)}"
        )

    def open_completed_file(self) -> None:
        if not COMPLETED_FILE.exists():
            self.append_empty_completed_header()
        try:
            os.startfile(COMPLETED_FILE)
        except Exception as exc:
            messagebox.showerror("打开失败", f"无法打开记录文件：\n{exc}")

    def append_empty_completed_header(self) -> None:
        with COMPLETED_FILE.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["任务", "开始时间", "完成时间", "花费时间", "花费秒数", "日期"])

    def make_tray_image(self):
        image = Image.new("RGBA", (64, 64), "#283845")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((10, 10, 54, 54), radius=8, fill="#f7f1d5")
        draw.rectangle((18, 24, 46, 28), fill="#2f6f73")
        draw.rectangle((18, 36, 38, 40), fill="#8c3d2f")
        return image

    def ensure_tray_icon(self) -> bool:
        if pystray is None or Image is None or ImageDraw is None:
            return False
        if self.tray_icon is not None:
            return True

        menu = pystray.Menu(
            pystray.MenuItem("显示每日计划", lambda _icon, _item: self.root.after(0, self.show_from_tray)),
            pystray.MenuItem("打开完成记录", lambda _icon, _item: self.root.after(0, self.open_completed_file)),
            pystray.MenuItem("支持作者", lambda _icon, _item: self.root.after(0, self.show_donation)),
            pystray.MenuItem("退出", lambda _icon, _item: self.root.after(0, self.exit_app)),
        )
        self.tray_icon = pystray.Icon("daily_plan_sticky", self.make_tray_image(), "每日计划", menu)
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()
        return True

    def hide_to_tray(self) -> None:
        self.save_tasks()
        self.save_settings()
        if self.ensure_tray_icon():
            self.root.withdraw()
        else:
            self.root.iconify()

    def show_from_tray(self) -> None:
        self.root.deiconify()
        self.root.lift()
        if bool(self.root.attributes("-topmost")):
            self.root.attributes("-topmost", False)
            self.root.attributes("-topmost", True)

    def exit_app(self) -> None:
        self.is_exiting = True
        self.save_tasks()
        self.save_settings()
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DailyPlanSticky().run()
