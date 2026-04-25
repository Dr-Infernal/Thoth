---
name: updater_guide
display_name: Auto-Update Guide
icon: "⬆"
description: Guidance for checking for and installing Thoth updates.
tools:
  - thoth_updater
tags: []
---
THOTH AUTO-UPDATE:
- Thoth checks GitHub Releases automatically in the background. There is
  no opt-in toggle: when Internet is available, the assistant polls
  https://github.com/siddsachar/Thoth for new releases and silently
  ignores network failures.
- Updates are NEVER installed automatically. The user must always
  approve installation.

WHEN TO MENTION UPDATES:
- The injected dynamic state will include an "Update available: v…" line
  when one exists. If the user asks "what's new" / "is there an update",
  surface the version + a one-line summary.
- Do NOT nag — mention proactively at most once per conversation.
- If an update is in `skipped_versions`, do not re-offer it unless the
  user explicitly asks.

CHECKING (thoth_check_for_updates):
- Read-only. Polls GitHub once and returns the available version (if any),
  channel, summary, and release page URL.
- Honors the user's channel: 'stable' (default) or 'beta'.
- Failures (offline, rate-limited) are reported but not treated as errors.

INSTALLING (thoth_install_update):
- Always asks the user for confirmation via an interrupt.
- On approval: downloads the asset to ~/.thoth/updates/, verifies SHA256,
  verifies the OS code signature (signtool/codesign), then hands off to
  the OS installer and exits Thoth.
- Windows: launches `ThothSetup_x.y.z.exe /SILENT /CLOSEAPPLICATIONS
  /RESTARTAPPLICATIONS`. The new version starts automatically after install.
- macOS: opens the DMG in Finder; the user drags Thoth.app into
  /Applications.
- Refuses to install when running from a development checkout
  (presence of `.git/` next to the app).

CHANNEL & SKIPPING:
- The channel is set in Settings → Preferences → Updates and persisted in
  ~/.thoth/update_config.json. Do not change it without asking.
- Users can skip a specific version from the "What's New" dialog. Skipped
  versions are surfaced via thoth_status category='updates'.

ERROR HANDLING:
- SHA256 mismatch or signature failure: do NOT retry blindly — surface the
  message verbatim and suggest the user open the GitHub release page.
- Network failure: a one-line "couldn't reach GitHub" suffices.
