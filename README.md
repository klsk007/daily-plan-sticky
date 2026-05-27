# 每日计划便签

一个轻量的 Windows 桌面悬浮便签，用来记录每日任务、完成时间和今日工作统计。

## 功能

- 手动输入任务，按 Enter 或点击 `+` 添加。
- 窗口默认置顶，拖动顶部标题栏即可移动。
- 每条任务右侧有完成方框，勾选后会先灰色停留一下，再从当前列表隐藏。
- 每条任务可以编辑或删除，也可以双击任务文字编辑。
- 完成记录写入 `completed_tasks.csv`，包含任务、开始时间、完成时间、花费时间、花费秒数和日期。
- 底部显示未完成数量、今日完成数量和今日累计耗时。
- 未完成任务保存在 `active_tasks.json`，下次打开继续显示。
- 窗口位置、大小、是否置顶保存在 `settings.json`。
- 支持开机启动和系统托盘。

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

## 启动

```powershell
python daily_plan_sticky.py
```

在 Windows 上也可以双击：

```text
启动每日计划便签.bat
```

## 文件说明

- `daily_plan_sticky.py`：主程序。
- `启动每日计划便签.bat`：Windows 双击启动脚本。
- `alipay_qr.png`：支持作者二维码，可替换为自己的收款码。
- `active_tasks.json`：本地未完成任务，默认不会提交到 GitHub。
- `completed_tasks.csv`：本地完成记录，默认不会提交到 GitHub。
- `settings.json`：本地窗口和启动设置，默认不会提交到 GitHub。

## 隐私

这个工具默认在本地保存任务和完成记录，不需要账号，也不会主动上传任务数据。
如果这个小工具帮你少写了几次日报，欢迎请作者喝杯咖啡。
软件会继续保持轻量、本地、无账号、无广告。
