# Mobian WeChat Helper

[中文](README.md) · [Download v0.1.1](https://github.com/SharkUI/mobian-wechat-helper/releases/tag/v0.1.1) · [Report an issue](https://github.com/SharkUI/mobian-wechat-helper/issues)

A small experimental companion for **Linux WeChat on Mobian / Phosh phones**. It converts vertical touch gestures to wheel scrolling, works around lost on-screen keyboard focus, and corrects the main window's startup placement.

This project grew out of troubleshooting a real OnePlus 6. It is a compatibility workaround for the desktop Linux client, not Android WeChat or a replacement mobile interface.

## What it addresses

| Symptom | Workaround |
| --- | --- |
| Chat lists, messages and Channels ignore swipes or treat them as mouse drags | Recognize vertical gestures inside WeChat windows and emit wheel events, including short diagonal thumb arcs |
| The keyboard is visible and a caret blinks, but typing stops after changing contacts or using search | After an eligible tap with the keyboard visible and missing X11 focus, briefly unmap/remap the main window to restore focus |
| Main/Moments windows do not fill the work area, or extend below it | Maximize each ordinary main-process window once when discovered and align it to the desktop work area |
| Closing the window leaves background processes running | Add an Exit WeChat desktop action that also stops the companion |

## Tested configuration and limitations

| Component | Verified configuration |
| --- | --- |
| Phone | OnePlus 6 |
| OS | Mobian 13, Debian 13 (trixie), ARM64 |
| Desktop | Phosh 0.46.0 + Phoc 0.46.0 |
| WeChat | Official Linux 4.1.13.29 ARM64 `.deb` |
| Display backend | `QT_QPA_PLATFORM=xcb` through XWayland |

Real-device user validation covers chat scrolling, left/right thumb arcs, Channels navigation, repeated contact/search input, and **a full application exit/reopen from the icon with placement, input and scrolling working automatically**.

Since v0.1.1, maximization is remembered per window rather than per process. This covers Moments and other ordinary content windows opened later in the same WeChat process. Only owned, ordinary, non-transient, non-modal, non-fullscreen windows are eligible. No titles or Moments content are read. Manually restoring a window does not continuously force it back to maximized.

- Other phones, desktop versions, WeChat versions and x86_64 are unverified. Process recognition requires the official package paths below; Flatpak, Waydroid and Android packages are not supported directly.
- Scrolling uses discrete wheel steps, without native touch inertia or pixel-perfect tracking. All AppEx web windows receive one wheel step per gesture: Channels was tested, other applets and web controls may behave differently.
- The keyboard does not open automatically. On Phosh, hold the middle of the bottom bar for about one second, then tap the text field again. A focus repair may cause a brief window blink.
- Placement prefers `_NET_WORKAREA`. If unavailable, it assumes the tested Phosh 0.46 top/bottom insets of 32/15 logical pixels. Other panel layouts, landscape and multiple displays are unverified.
- The underlying input failure is not fully explained. This release has not been validated across a full phone reboot, manual restore, live voice recording/sending, or all input methods.

## Installation

Run these commands in **Console / Terminal on the phone, as the logged-in desktop user**. Mobian / Phosh and official Linux WeChat must already be installed. This repository does not distribute WeChat or provide an account.

### 1. Install dependencies

```sh
sudo apt update
sudo apt install python3 python3-gi xwayland libx11-6 libxi6 libxtst6 pulseaudio-utils curl ca-certificates
```

Use the system `/usr/bin/python3`; no `pip` packages or virtual environment are needed. GI reads desktop state. `pulseaudio-utils` supplies `pactl` to inspect recording-stream process metadata; no audio is captured and replacing an existing PipeWire setup with PulseAudio is unnecessary. See Debian's [python3-gi](https://packages.debian.org/trixie/arm64/python3-gi), [libxi6](https://packages.debian.org/trixie/libxi6), [libxtst6](https://packages.debian.org/trixie/arm64/libxtst6) and [pulseaudio-utils](https://packages.debian.org/trixie/arm64/pulseaudio-utils) package descriptions.

### 2. Download a fixed release

```sh
curl --fail --location --output mobian-wechat-helper-v0.1.1.tar.gz \
  https://github.com/SharkUI/mobian-wechat-helper/archive/refs/tags/v0.1.1.tar.gz
tar -xzf mobian-wechat-helper-v0.1.1.tar.gz
cd mobian-wechat-helper-0.1.1
```

Review this README and the source before running the installer. Downloading does not execute it. Alternatively, clone the repository and check out `v0.1.1`.

### 3. Check the package paths and install

```sh
ls /usr/bin/wechat /opt/wechat/wechat /usr/share/applications/wechat.desktop
/usr/bin/python3 install.py
```

**Do not use `sudo` for `install.py`, or Python's `-O` option.** The installer snapshots existing user files and prints a `restore snapshot:` path. Keep that path and the matching release source for restoration.

| Location | Purpose |
| --- | --- |
| `~/.local/lib/wechat-mobile/` | Eight helper scripts |
| `~/.local/share/applications/wechat.desktop` | Per-user launcher and desktop actions |
| `~/.local/state/wechat-mobile/` | Snapshots, hashes, state and helper logs |
| `/run/user/YOUR_UID/wechat-…` | Session-local locks and communication socket |

The system desktop entry, WeChat program and chat data are preserved. No system service, boot job, global touch mapping or root input permission is installed. An unfamiliar custom launcher is rejected for manual review.

### 4. Fully exit and reopen

Long-press the WeChat icon, select **退出微信 (Exit WeChat)**, then launch it again and wait about 2–3 seconds. Merely closing the window may leave the previous process running and prevent the display-backend change from taking effect.

## Daily use

Launching from the application icon enables `xcb` and the companion automatically. Newly opened owned WeChat windows are discovered. The companion stops after all main WeChat processes exit. Running `/usr/bin/wechat` directly bypasses the wrapper.

The icon's long-press actions currently have Chinese labels:

- **开启微信触控修复** — enable/resume handling for the current WeChat session.
- **暂停微信触控修复** — stop scrolling, placement and focus handling while leaving WeChat open. Launching from the icon enables it again.
- **退出微信** — stop the companion, then request termination of this user's WeChat main and bundled background processes. It does not send `SIGKILL` to WeChat.

If the on-screen keyboard does not appear, hold the middle of the Phosh bottom bar for about one second. **Tap the intended text field after opening the keyboard** to trigger the focus check. Taps, mostly horizontal drags and long presses are handed back to WeChat where possible. Gesture conflicts can still occur; pause the companion for comparison.

Equivalent commands, in the phone's desktop session:

```sh
/usr/bin/python3 ~/.local/lib/wechat-mobile/control.py stop
/usr/bin/python3 ~/.local/lib/wechat-mobile/control.py start
/usr/bin/python3 ~/.local/lib/wechat-mobile/quit.py
```

## Restore the previous state

First fully exit WeChat using its icon action. From the **same release's source directory**, inspect the installation receipt:

```sh
cat ~/.local/state/wechat-mobile/installation.json
```

Find its `backup` path and replace `YOUR_SNAPSHOT_ID` below with that actual directory name:

```sh
/usr/bin/python3 install.py --restore "$HOME/.local/state/wechat-mobile/installs/YOUR_SNAPSHOT_ID"
```

Restore verifies the installed hashes before stopping the controller and restoring previous files or removing newly installed files. Locally modified files cause it to refuse rather than overwrite. It reverses **one installation**: installing over an older helper means restoring that older helper; only the first-install snapshot removes the helper entirely. Snapshots/logs are retained, and WeChat, chat data and system packages are not deleted.

The source includes installation-failure rollback and manual restore logic; **manual restore has not been exercised on the phone**. Use Pause to disable handling without restoring.

## Troubleshooting

| Problem | Check |
| --- | --- |
| `No module named gi` | Use `/usr/bin/python3`, install `python3-gi`, and leave any virtual environment |
| Installer assertion or custom-launcher refusal | Check package paths, current user and the original desktop entry's `Exec`; do not delete originals or bypass checks with `sudo` |
| Companion does not start | Fully exit/reopen from the icon; try `control.py start` in the local desktop terminal; an SSH shell may lack the session environment |
| Typing still fails | Open the keyboard and tap the text field again; recovery applies only when X11 focus is zero, not to every input problem |
| Swipes fail or interfere with controls | Compare Pause/Enable and check window failure counts; the touch worker currently uses XI2 master device 2 from the verified setup |
| Incorrect placement | Check Phosh/Phoc versions, orientation and panel layout; other configurations may require adaptation |

Inspect helper summaries locally:

```sh
cat ~/.local/state/wechat-mobile/controller-status.json
tail -n 40 ~/.local/state/wechat-mobile/controller.log
```

`running` may be stale after an abnormal exit. Check the current boot ID, live controller PID and WeChat state together. Status `version: 5` is the inherited internal format; the public release is `v0.1.1`.

Common `lastFocusRepair.result` values: `repaired`, `keyboard-hidden`, `focus-present`, `controls-held`, `microphone-busy`, and `state-unknown`. Unknown desktop/audio state or an active WeChat recording stream skips recovery conservatively.

## Design and privacy

`launch.py` starts WeChat → `control.py` manages one `controller.py` → one `touch-wheel.py` runs for each mapped main/AppEx window whose UID and real executable path match the expected bundle.

Touch conversion uses **per-window** XI2 passive touch grabs. A recognized vertical gesture is accepted and converted into XTest buttons 4/5; other gestures are handed back. Wheel delivery moves the pointer to the gesture origin and can affect hover state. No left-click, text or keyboard events are synthesized.

Focus requests carry only a window ID and monotonic timestamp over a private per-user socket. Stale/unrelated requests are rejected. Recovery requires a recent tap on an ordinary main window, an unlocked session, a visible keyboard, a closed overview, no held controls and no WeChat recording stream; it has a cooldown. It does not continuously force focus or refresh when another X11 window already has focus.

The helper does not read chat databases, titles, message text or account sessions, or listen to/decode/log keyboard input. Its held-control guard queries pointer button state and **whether Space is down**. Audio inspection reads process metadata only. Gesture coordinates exist temporarily in memory, never in logs. Persisted summaries contain counters, window/process IDs, boot ID, times and error reasons. The helper contains no networking or telemetry logic.

## Development and feedback

Offline checks need no WeChat, GUI, GI bindings or phone:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s . -p 'test_*.py' -v
python3 -m compileall -q .
```

`test_gestures.py` runs 19 synthetic cases against the retained legacy `motion-wheel.py` classifier. The current controller uses `touch-wheel.py`; **these classifier tests do not cover the current event loop**. `test_focus_requests.py` checks 15 request examples, including stale requests, abnormal numbers and unrelated windows. CI runs offline checks only and does not certify device support.

In [Issues](https://github.com/SharkUI/mobian-wechat-helper/issues), include the phone model, OS/Phosh/Phoc/WeChat versions, package source and concise reproduction steps. Share only redacted counters/error reasons. Do not upload chat screenshots, raw WeChat logs, user-data directories, installation snapshots or complete session details.

The initial code preserves the verified behavior. Useful future work includes touch-device discovery, scrolling feel and support for more desktop versions. Dependencies and protocols come from [X.Org](https://www.x.org/), [Phosh](https://phosh.mobi/) and [PyGObject](https://pygobject.gnome.org/).

## License

[MIT](LICENSE). This repository contains companion code only, no WeChat binaries, brand assets or user data. It is an independent community project, unaffiliated with Tencent/WeChat.
