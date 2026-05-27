# Daily Plan Sticky / 每日计划便签

A lightweight Windows desktop sticky daily planner and worklog app with time tracking, tray icon, startup launch, local CSV export, and a donation QR window.

一个轻量的 Windows 桌面悬浮每日计划便签：写下任务、勾选完成、自动记录完成时间和耗时，所有数据默认保存在本地。

![Daily Plan Sticky screenshot](assets/screenshot-main.png)

## Why

Most todo apps are too heavy for daily work notes. Daily Plan Sticky stays on your desktop, keeps tasks visible, and turns completed items into a simple worklog that can become daily reports, weekly reports, or billing records.

很多计划工具太重，而这个工具只做一件事：把当天任务贴在桌面上。完成后自动沉淀为“完成事项 + 花费时间 + 日期”，方便写日报、周报或工时记录。

## Features / 功能

- Floating always-on-top Windows sticky note for daily tasks.
- Tray-first behavior: the app keeps its icon in the system tray and does not occupy the Windows taskbar.
- Add tasks manually with Enter or the `+` button.
- Edit or delete each task; double-click task text to edit.
- Check the box on the right to complete a task.
- Completed tasks fade briefly, disappear from the active list, and are appended to `completed_tasks.csv`.
- Local worklog fields: task, start time, completion time, duration, duration seconds, date.
- Footer statistics: active tasks, today's completed count, today's total time.
- Window position, size, startup setting, and topmost setting are remembered locally.
- Optional startup launch and system tray menu.
- Optional Alipay donation QR window via `alipay_qr.png`.

## Install / 安装

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run from source:

```powershell
python daily_plan_sticky.py
```

On Windows, you can also double-click:

```text
启动每日计划便签.bat
```

## Download / 下载

Packaged Windows builds are published from GitHub Releases when available:

[Releases](https://github.com/klsk007/daily-plan-sticky/releases)

## Build EXE / 打包

```powershell
python -m pip install pyinstaller
pyinstaller --onefile --windowed --name DailyPlanSticky --add-data "alipay_qr.png;." daily_plan_sticky.py
```

The executable will be created under `dist/DailyPlanSticky.exe`.

## Local Files / 本地文件

- `active_tasks.json`: active tasks, ignored by Git.
- `completed_tasks.csv`: completed worklog, ignored by Git.
- `settings.json`: local window and startup settings, ignored by Git.
- `alipay_qr.png`: optional donation QR code image.

## Privacy / 隐私

Daily Plan Sticky is local-first. It does not require an account and does not upload your tasks or worklog data by itself.

每日计划便签默认只在本地保存任务和完成记录，不需要账号，也不会主动上传任务数据。

## Keywords

Windows desktop app, sticky notes, todo list, daily planner, worklog, time tracking, productivity, local-first, Python, Tkinter, tray icon, CSV export, daily report.

## License

MIT License.
