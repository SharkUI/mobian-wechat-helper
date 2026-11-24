# Changelog

## v0.1.1 — 2026-11-24

- Maximize each eligible main-process window once per XID/PID pair, instead of once per process. Moments shares the main WeChat process, so the previous bookkeeping skipped it after maximizing the chat window.
- Keep transient/dialog/fullscreen exclusions and additionally skip modal windows during maximization and alignment.
- Preserve title-free window discovery, manual window restores, touch handling and keyboard-focus recovery.

## v0.1.0 — 2026-11-24

First public experimental release, extracted from a working OnePlus 6 / Mobian 13 installation.

- Launch Linux WeChat 4.1.13.29 ARM64 through XWayland with `QT_QPA_PLATFORM=xcb`.
- Convert vertical touch gestures to wheel steps within owned WeChat windows; one step per gesture for AppEx windows.
- Restore missing X11 keyboard focus after an eligible recent tap, without injecting keys or text.
- Maximize the main window at startup and correct its position within the Phosh work area.
- Add user desktop actions to pause, resume, and fully exit WeChat and its helpers.
- Include a user-only installer with snapshots and a guarded restore command.
- Document Chinese and English setup, privacy, limitations and the exact scope of testing.

Real-device validation covers scrolling, contact/search input, placement and a full application exit/reopen. Full phone reboot, manual restore, live voice recording/sending, other devices and other desktop versions remain unverified. CI covers only synthetic offline checks; see the README.
