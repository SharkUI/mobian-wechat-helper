# Mobian WeChat Helper

[English](README.en.md) · [下载 v0.1.1](https://github.com/SharkUI/mobian-wechat-helper/releases/tag/v0.1.1) · [反馈问题](https://github.com/SharkUI/mobian-wechat-helper/issues)

让 **Mobian / Phosh 手机上的 Linux 微信**更容易使用的小工具：把手指上下划动转换成滚轮、在需要时恢复屏幕键盘的输入焦点，并修正启动时的窗口位置。

这是从真实手机排障中整理出的实验性工具。首个版本在一加 6 上验证，适合遇到相同问题的人试用和继续完善。它不是 Android 微信，也不会把桌面版界面变成手机版。

## 解决哪些问题

| 原来的现象 | 工具的处理方式 |
| --- | --- |
| 聊天列表、聊天内容、视频号不响应上下划，或把滑动当成鼠标拖动 | 只在微信窗口内识别纵向手势，转换成鼠标滚轮；支持左右手拇指的短斜弧线 |
| 屏幕键盘能弹出，有光标，但切换联系人或搜索后打不出字 | 在键盘已展开、点过微信文字框且 X11 焦点丢失时，短暂隐藏并重新显示窗口，尝试恢复焦点 |
| 主窗口或朋友圈没有铺满可用区域，或底部出屏幕 | 每个普通主进程窗口首次出现时分别最大化，再按桌面可用区域校正位置 |
| 关闭窗口后微信仍留在后台 | 图标长按菜单增加“退出微信”，同时停止本工具 |

## 已验证环境与限制

| 项目 | 已验证版本 |
| --- | --- |
| 手机 | OnePlus 6 / 一加 6 |
| 系统 | Mobian 13，Debian 13（trixie）ARM64 |
| 桌面 | Phosh 0.46.0 + Phoc 0.46.0 |
| 微信 | 官方 Linux 微信 4.1.13.29，ARM64 `.deb` |
| 运行方式 | `QT_QPA_PLATFORM=xcb`，通过 XWayland 显示 |

用户已验证：聊天滚动、左右手短弧线、视频号切换、连续更换联系人和搜索输入，以及**彻底退出后从图标重开，定位、输入、滑动自动生效**。

从 v0.1.1 起，最大化记录由“每个进程一次”改成“每个窗口一次”，覆盖同一微信进程后来打开的朋友圈等普通内容窗口。只处理已核对所有权、非临时、非模态、非全屏的普通窗口；不通过标题识别或读取朋友圈内容。手动恢复窗口后不会持续强制最大化。

窗口结构事件会立即唤醒控制器；同一进程后开的内容窗口跳过主窗口启动时的 1.5 秒稳定等待，可用区校正紧接最大化处理，不再额外等待一秒。结构事件观察不选择键盘或触摸输入事件。

v0.1.1 在上述实机上另经用户反复关闭／重开朋友圈验证：明显变快、基本一次铺满，关闭与上下滑动正常。

- 其他手机、桌面、微信版本和 x86_64 尚未验证；本工具按下列官方包路径识别进程，不支持直接用于 Flatpak、Waydroid 或 Android 微信。
- 滚动仍然是分步滚轮，没有原生手机那样的逐像素跟手和惯性。微信 AppEx 网页窗口统一按“一次手势一格滚轮”处理，视频号已验证，其他小程序／网页控件可能不合适。
- 键盘不会自动弹出。必要时长按 Phosh 底栏中间约一秒，再点文字输入框。焦点恢复可能让窗口短暂闪一下。
- 窗口定位优先使用 `_NET_WORKAREA`；缺失时按已测试的 Phosh 0.46 顶栏 32、底栏 15 个逻辑像素处理。其他桌面、横屏、多屏和面板布局未验证。
- 根因没有完全证实；这里提供的是可撤回的兼容处理。尚未验收本版本的整机重启、实际恢复操作、真实语音录制／发送及所有输入法组合。

## 安装

在**手机自己的 Console / 终端、当前桌面用户**下操作。手机应已经运行 Mobian / Phosh，并已安装官方 Linux 微信。本仓库不提供微信安装包或账号。

### 1. 安装依赖

```sh
sudo apt update
sudo apt install python3 python3-gi xwayland libx11-6 libxi6 libxtst6 pulseaudio-utils curl ca-certificates
```

使用系统的 `/usr/bin/python3`，不需要 `pip` 或虚拟环境。`python3-gi` 用于读取桌面状态；`pulseaudio-utils` 提供 `pactl`，用于检查微信是否正在占用录音流元数据，不采集音频，也不要求把现有 PipeWire 换成 PulseAudio。依赖说明见 Debian 的 [python3-gi](https://packages.debian.org/trixie/arm64/python3-gi)、[libxi6](https://packages.debian.org/trixie/libxi6)、[libxtst6](https://packages.debian.org/trixie/arm64/libxtst6) 和 [pulseaudio-utils](https://packages.debian.org/trixie/arm64/pulseaudio-utils) 包页面。

### 2. 下载固定版本

```sh
curl --fail --location --output mobian-wechat-helper-v0.1.1.tar.gz \
  https://github.com/SharkUI/mobian-wechat-helper/archive/refs/tags/v0.1.1.tar.gz
tar -xzf mobian-wechat-helper-v0.1.1.tar.gz
cd mobian-wechat-helper-0.1.1
```

先阅读本 README 和源码；下载不会自动执行安装。也可以用 Git 获取并检出 `v0.1.1`。

### 3. 检查包路径并安装

```sh
ls /usr/bin/wechat /opt/wechat/wechat /usr/share/applications/wechat.desktop
/usr/bin/python3 install.py
```

**`install.py` 不加 `sudo`，不要使用 Python 的 `-O` 优化选项。** 安装器会保留原用户文件的快照，并显示 `restore snapshot:` 路径。请保留这个路径和下载的同版本源码，以便恢复。

它只安装到当前用户的目录：

| 路径 | 用途 |
| --- | --- |
| `~/.local/lib/wechat-mobile/` | 8 个辅助脚本 |
| `~/.local/share/applications/wechat.desktop` | 用户专用启动项和长按动作 |
| `~/.local/state/wechat-mobile/` | 安装快照、摘要、状态和辅助日志 |
| `/run/user/你的UID/wechat-…` | 当前登录期间的锁和本地通信 socket |

系统的 `/usr/share/applications/wechat.desktop`、微信程序和聊天数据保持原样。不创建系统服务、开机任务、全局触屏映射或 root 输入权限。安装器遇到不认识的自定义启动命令会拒绝覆盖，请先人工确认差异。

### 4. 从图标重开微信

长按微信图标 → **退出微信** → 再点图标打开，等待约 2～3 秒。只关闭窗口可能没有退出后台，不能保证启动方式已经切换。

## 日常使用

从应用列表里的微信图标打开时，自动使用 `xcb` 并启动辅助进程；之后新开的微信窗口也会被识别。关闭微信所有主进程后，辅助进程会自行结束。从命令行直接执行 `/usr/bin/wechat` 不经过此启动包装器。

长按微信图标可看到：

- **开启微信触控修复**：为当前微信开启／恢复处理。
- **暂停微信触控修复**：停止滑动、定位和焦点处理，微信继续运行；下次从图标打开会再次开启。
- **退出微信**：先停止本工具，再向当前用户的微信主进程及其包内后台进程请求退出；不使用强制 `SIGKILL`。

点输入框后键盘不弹出时，长按底栏中间约一秒。**键盘展开后，再点一下要输入的文字框**，这是触发焦点检查的关键。普通点按、主要为横向的拖动和长按尽量交还微信处理；仍可能有手势冲突，可用“暂停”对照。

命令行等价操作（在当前手机桌面会话中执行）：

```sh
/usr/bin/python3 ~/.local/lib/wechat-mobile/control.py stop
/usr/bin/python3 ~/.local/lib/wechat-mobile/control.py start
/usr/bin/python3 ~/.local/lib/wechat-mobile/quit.py
```

## 恢复安装前状态

先使用图标菜单**退出微信**。回到下载的**同版本源码**目录，查看安装回执：

```sh
cat ~/.local/state/wechat-mobile/installation.json
```

找到其中的 `backup` 路径，用真实的快照目录名替换下面的 `YOUR_SNAPSHOT_ID`：

```sh
/usr/bin/python3 install.py --restore "$HOME/.local/state/wechat-mobile/installs/YOUR_SNAPSHOT_ID"
```

恢复器会先核对当前辅助文件与安装时摘要一致，再停止控制器、恢复原文件或删除本次新增的辅助文件。已有自定义修改时会拒绝继续，避免覆盖。它只撤回**该次安装**：覆盖过旧版工具时，恢复得到的是旧版工具；首次安装的快照才会恢复到未安装状态。快照和日志保留供核对，不删除微信、聊天数据或系统包。

安装时的自动失败回滚和上述手动恢复逻辑均在源码中；**手动恢复尚未在实机上验收**。无需恢复即可先用“暂停”停止兼容处理。

## 排查问题

| 现象 | 先检查 |
| --- | --- |
| 安装提示 `No module named gi` | 用 `/usr/bin/python3`，确认已安装 `python3-gi`；退出虚拟环境 |
| 安装出现断言或提示检查自定义启动项 | 确认官方包路径、当前用户及原 `wechat.desktop` 的 `Exec`；不要删除原文件或用 `sudo` 绕过检查 |
| 从图标启动没有修复 | 先“退出微信”再重开；在手机本地终端尝试 `control.py start`；不要从没有桌面环境变量的 SSH 会话启动 |
| 仍不能输入 | 展开键盘后再次点文字框；只有 X11 焦点为零才尝试恢复，不会对所有输入故障强行刷新 |
| 滑动不生效／原操作冲突 | 暂停／恢复作对照；检查窗口失败计数；XI2 触摸设备固定为已验证环境的 master device 2，其他设备配置可能需要适配 |
| 启动位置仍错误 | 核对 Phosh / Phoc 版本、屏幕方向和缩放；不要通过修改全局缩放来掩盖日志中的窗口失败 |

可在手机本地查看辅助摘要：

```sh
cat ~/.local/state/wechat-mobile/controller-status.json
tail -n 40 ~/.local/state/wechat-mobile/controller.log
```

摘要中的 `running` 可能是上次异常退出留下的旧值；应同时核对当前开机的 `bootId`、存活的 `controllerPid` 和微信状态。`version: 5` 是沿用的内部状态格式，公开发行版本是 `v0.1.1`。

`lastFocusRepair.result` 常见值：`repaired` 已恢复，`keyboard-hidden` 键盘没展开，`focus-present` 已有 X11 焦点，`controls-held` 正有鼠标按键／空格按住，`microphone-busy` 微信存在录音流，`state-unknown` 无法确认桌面或音频状态。后两种情况会保守跳过，不反复刷新窗口。

## 工作原理与隐私

`launch.py` 启动微信 → `control.py` 管理单个 `controller.py` → 为核对过 UID、真实可执行路径的微信主窗口和 `WeChatAppEx` 窗口各启一个 `touch-wheel.py`。

触摸处理使用 XI2 的**窗口级**被动触摸抓取；确认纵向滑动后接管并输出 XTest 滚轮按钮 4/5，点按等交回应用。它会把鼠标指针移到手势起点，可能影响鼠标悬停。不会生成左键点击、文字或键盘事件。

焦点请求只含窗口 ID 和单调时间戳，经当前用户私有 socket 传递；控制器拒绝过期请求和非目标窗口。焦点恢复仅在最近点过普通微信主窗口、手机已解锁、键盘可见、总览关闭、无按住操作且无微信录音流时尝试，带冷却时间。它不持续抢焦点，也不会在别的应用已有 X11 焦点时刷新。

不读取聊天数据库、窗口标题、聊天文字或账号会话；不监听、解码或记录键盘输入。防止打断操作时会查询指针按键状态及 **Space 是否按住**，音频检查只看 `pactl` 的进程元数据，不录音。触摸轨迹只在内存里判定，不落盘；状态仅保存计数、窗口／进程 ID、开机标识、时间和错误原因。工具没有联网或遥测逻辑。

## 开发与反馈

离线检查不需要微信、GUI、GI 或手机：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s . -p 'test_*.py' -v
python3 -m compileall -q .
```

测试范围：`test_gestures.py` 的 19 组合成轨迹针对保留的旧版 `motion-wheel.py` 分类器；当前控制器使用 `touch-wheel.py`，**不能把旧分类器测试视为当前触摸循环的覆盖**。`test_focus_requests.py` 覆盖 15 个焦点请求输入示例，包括过期、异常数字和非目标窗口。CI 仅验证这些离线检查，不证明实机兼容性。

请在 [Issues](https://github.com/SharkUI/mobian-wechat-helper/issues) 提供手机型号、系统／Phosh／Phoc／微信版本、安装来源，以及简洁的复现步骤。只分享脱敏后的计数和错误原因；不要上传聊天截图、微信原始日志、用户数据目录、安装快照或完整会话信息。

当前代码优先保留已验证行为，后续适合改进触摸设备发现、分步滚动手感和更多桌面版本适配。协议与实现依赖来自 [X.Org](https://www.x.org/)、[Phosh](https://phosh.mobi/) 和 [PyGObject](https://pygobject.gnome.org/)。

## 许可

[MIT License](LICENSE)。本仓库只包含辅助代码，不包含微信程序、品牌资产或任何用户数据；与腾讯／微信官方无隶属关系。
