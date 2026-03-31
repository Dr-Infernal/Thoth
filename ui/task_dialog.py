"""Thoth UI — task editor dialog.

Self-contained task creation / editing dialog.  Receives ``state`` and
``p`` explicitly, and a callback ``on_done`` to notify the caller when
the dialog completes.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from nicegui import ui

from ui.state import AppState, P
from ui.constants import ICON_OPTIONS

logger = logging.getLogger(__name__)


def show_task_dialog(
    task: dict | None,
    on_done: Callable[[], None],
    *,
    state: AppState,
    p: P,
) -> None:
    """Open the task editor dialog.

    *task=None* → create mode (blank fields).
    *task=dict* → edit mode (pre-populated).
    """
    from models import (
        list_local_models,
        is_tool_compatible,
        is_cloud_available,
        list_starred_cloud_models,
        get_current_model,
        get_provider_emoji,
    )
    from tasks import (
        get_run_history,
        create_task,
        update_task,
        delete_task,
        duplicate_task,
        list_tasks,
    )

    is_new = task is None
    title = "New Task" if is_new else "Edit Task"

    # Editable data holders
    _name = task["name"] if task else ""
    _icon = task["icon"] if task else "⚡"
    _desc = task.get("description", "") if task else ""
    _enabled = task.get("enabled", True) if task else True
    _model_ov = task.get("model_override") or "" if task else ""
    _prompts_data: list[str] = list(task["prompts"]) if task else [""]

    # Parse schedule
    _current_sched = (task.get("schedule") or "") if task else ""
    if _current_sched.startswith("daily"):
        _sched_mode = "Daily"
    elif _current_sched.startswith("weekly"):
        _sched_mode = "Weekly"
    elif _current_sched.startswith("interval_minutes"):
        _sched_mode = "Interval (min)"
    elif _current_sched.startswith("interval"):
        _sched_mode = "Interval (hrs)"
    elif _current_sched.startswith("cron"):
        _sched_mode = "Cron"
    else:
        _sched_mode = "Manual"

    _sched_time = "08:00"
    _sched_day = "mon"
    _sched_interval = "1"
    _sched_cron = ""
    _FULL_TO_ABBR = {
        "monday": "mon", "tuesday": "tue", "wednesday": "wed",
        "thursday": "thu", "friday": "fri", "saturday": "sat",
        "sunday": "sun",
    }
    if _current_sched.startswith("daily:"):
        _sched_time = _current_sched.split(":", 1)[1]
    elif _current_sched.startswith("weekly:"):
        parts = _current_sched.split(":")
        if len(parts) >= 3:
            raw_day = parts[1].lower()
            _sched_day = _FULL_TO_ABBR.get(raw_day, raw_day[:3] if len(raw_day) > 3 else raw_day)
            _sched_time = f"{parts[2]}:{parts[3]}" if len(parts) >= 4 else "08:00"
    elif _current_sched.startswith("interval_minutes:"):
        _sched_interval = _current_sched.split(":", 1)[1]
    elif _current_sched.startswith("interval:"):
        _sched_interval = _current_sched.split(":", 1)[1]
    elif _current_sched.startswith("cron:"):
        _sched_cron = _current_sched.split(":", 1)[1]

    # Parse delivery
    _del_channel = (task.get("delivery_channel") or "") if task else ""
    _del_target = (task.get("delivery_target") or "") if task else ""

    p.task_dlg.clear()
    with p.task_dlg, ui.card().classes("q-pa-none").style(
        "width: 860px; max-width: 92vw; height: 90vh; max-height: 94vh;"
        "border-radius: 16px; overflow: hidden;"
        "background: #1a1a2e; border: 1px solid #2a2a4a;"
        "display: flex; flex-direction: column;"
    ):
        # ── Header ──
        with ui.row().classes("w-full items-center q-pa-md").style(
            "background: linear-gradient(135deg, #2d1b00 0%, #1a1a2e 100%);"
            "border-bottom: 1px solid #3d2e00;"
        ):
            ui.icon("edit_note", size="28px", color="amber")
            ui.label(title).style(
                "font-size: 1.15rem; font-weight: 700; color: #f0c040; margin-left: 8px;"
            )

        # ── Body (scrollable) ──
        with ui.scroll_area().style("flex: 1; min-height: 0;"):
            with ui.column().classes("w-full q-pa-lg gap-3"):
                # Name + Icon row
                with ui.row().classes("w-full items-center gap-2"):
                    _wf_icon_opts = list(ICON_OPTIONS)
                    if _icon not in _wf_icon_opts:
                        _wf_icon_opts.insert(0, _icon)
                    icon_sel = ui.select(
                        label="Icon", options=_wf_icon_opts, value=_icon,
                    ).classes("w-20")
                    name_input = ui.input(
                        "Name", value=_name,
                    ).classes("flex-grow")

                desc_input = ui.input(
                    "Description (optional)", value=_desc,
                ).classes("w-full")

                # Enabled toggle
                enabled_switch = ui.switch("Enabled", value=_enabled)

                # Model override dropdown
                _local = list_local_models()
                _compat = [m for m in _local if is_tool_compatible(m)]
                if is_cloud_available():
                    _compat.extend(list_starred_cloud_models())
                _default_label = f"Default ({get_current_model()})"
                _model_opts_map = {_default_label: _default_label}
                for _m in sorted(_compat):
                    _model_opts_map[_m] = f"{get_provider_emoji(_m)} {_m}"
                _model_val = _model_ov if _model_ov in _compat else _default_label
                model_sel = ui.select(
                    _model_opts_map, value=_model_val, label="Model",
                ).classes("w-full").tooltip(
                    "Choose which LLM runs this task. "
                    "Only tool-compatible models are listed."
                )

                ui.separator()

                # Prompts editor
                ui.label("Prompts (executed in order)").style(
                    "font-weight: 600; font-size: 0.9rem; color: #d0d0e0;"
                )
                ui.label(
                    "Leave empty for notification-only tasks (reminders). "
                    "Variables: {{date}}, {{day}}, {{time}}, {{month}}, {{year}}"
                ).style("font-size: 0.75rem; color: #666;")

                prompt_inputs: list[ui.textarea] = []
                prompt_container = ui.column().classes("w-full")

                def _rebuild_prompts():
                    for i, ta in enumerate(prompt_inputs):
                        if i < len(_prompts_data):
                            _prompts_data[i] = ta.value
                    prompt_container.clear()
                    prompt_inputs.clear()
                    with prompt_container:
                        for i, p_text in enumerate(_prompts_data):
                            with ui.row().classes("w-full items-start gap-1"):
                                ta = ui.textarea(
                                    f"Step {i+1}", value=p_text,
                                ).classes("flex-grow")
                                prompt_inputs.append(ta)
                                if len(_prompts_data) > 1:
                                    def _remove(idx=i):
                                        for j, _ta in enumerate(prompt_inputs):
                                            if j < len(_prompts_data):
                                                _prompts_data[j] = _ta.value
                                        _prompts_data.pop(idx)
                                        _rebuild_prompts()
                                    ui.button(
                                        icon="close", on_click=_remove,
                                    ).props("flat dense round")

                        def _add():
                            for j, _ta in enumerate(prompt_inputs):
                                if j < len(_prompts_data):
                                    _prompts_data[j] = _ta.value
                            _prompts_data.append("")
                            _rebuild_prompts()

                        ui.button("＋ Add step", on_click=_add).props("flat dense")

                _rebuild_prompts()

                ui.separator()

                # Schedule section
                ui.label("Schedule").style(
                    "font-weight: 600; font-size: 0.9rem; color: #d0d0e0;"
                )

                sched_options = ["Manual", "Daily", "Weekly", "Interval (hrs)", "Interval (min)", "Cron"]
                day_options = {
                    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday",
                    "thu": "Thursday", "fri": "Friday", "sat": "Saturday",
                    "sun": "Sunday",
                }

                with ui.column().classes("w-full gap-2"):
                    sched_sel = ui.select(
                        label="Type", options=sched_options, value=_sched_mode,
                    ).classes("w-48")

                    sched_time_input = ui.input(
                        label="Time", value=_sched_time,
                    ).classes("w-28").props('mask="##:##" placeholder="HH:MM"')
                    sched_time_input.visible = _sched_mode in ("Daily", "Weekly")

                    sched_day_sel = ui.select(
                        label="Day", options=day_options, value=_sched_day,
                    ).classes("w-36")
                    sched_day_sel.visible = _sched_mode == "Weekly"

                    sched_interval_input = ui.input(
                        label="Every", value=_sched_interval,
                    ).classes("w-28")
                    sched_interval_input.visible = _sched_mode in ("Interval (hrs)", "Interval (min)")

                    sched_cron_input = ui.input(
                        label="Cron expression", value=_sched_cron,
                    ).classes("w-full")
                    sched_cron_input.visible = _sched_mode == "Cron"

                def _on_sched_change(e):
                    sched_time_input.visible = e.value in ("Daily", "Weekly")
                    sched_day_sel.visible = e.value == "Weekly"
                    sched_interval_input.visible = e.value in ("Interval (hrs)", "Interval (min)")
                    sched_cron_input.visible = e.value == "Cron"

                sched_sel.on_value_change(_on_sched_change)

                ui.separator()

                # Delivery (collapsed)
                with ui.expansion("📡 Delivery channel (optional)").classes("w-full"):
                    ui.label(
                        "Optionally send task output via Telegram or email. "
                        "Desktop notification always fires."
                    ).style("font-size: 0.75rem; color: #666;")
                    del_ch_sel = ui.select(
                        label="Channel",
                        options=["", "telegram", "email"],
                        value=_del_channel,
                    ).classes("w-48")
                    del_tgt_input = ui.input(
                        "Target (email address)", value=_del_target,
                    ).classes("w-full")
                    del_tgt_input.set_visibility(_del_channel == "email")
                    del_ch_sel.on_value_change(
                        lambda e: del_tgt_input.set_visibility(e.value == "email")
                    )

                # Background permissions (collapsed)
                _allowed_cmds = task.get("allowed_commands", []) if task else []
                _allowed_recip = task.get("allowed_recipients", []) if task else []
                with ui.expansion("🔒 Background permissions (optional)").classes("w-full"):
                    ui.label(
                        "When this task runs in the background, it cannot "
                        "send emails or run shell commands unless you "
                        "explicitly allow them here."
                    ).style("font-size: 0.75rem; color: #666;")

                    ui.label("Allowed email recipients").style(
                        "font-size: 0.8rem; color: #c0c0d0; margin-top: 8px;"
                    )
                    ui.label(
                        "Email addresses this task may send to (one per line)."
                    ).style("font-size: 0.7rem; color: #666;")
                    allowed_recip_input = ui.textarea(
                        value="\n".join(_allowed_recip),
                    ).classes("w-full").props('rows="3"')

                    ui.label("Allowed shell commands").style(
                        "font-size: 0.8rem; color: #c0c0d0; margin-top: 8px;"
                    )
                    ui.label(
                        "Command prefixes this task may run, e.g. 'git pull' "
                        "or 'python backup.py' (one per line). Permanently "
                        "blocked commands like rm -rf / are never allowed."
                    ).style("font-size: 0.7rem; color: #666;")
                    allowed_cmds_input = ui.textarea(
                        value="\n".join(_allowed_cmds),
                    ).classes("w-full").props('rows="3"')

                # ── Skills override (optional) ───────────────────────
                import skills as _task_skills_mod
                _task_skills_mod.load_skills()
                _task_all_skills = _task_skills_mod.get_enabled_skills()
                _task_sk_override = task.get("skills_override") if task else None
                _task_enabled_names = set(sk.name for sk in _task_all_skills)
                _task_sk_active = (
                    set(_task_sk_override) & _task_enabled_names
                    if _task_sk_override is not None
                    else set(_task_enabled_names)
                )
                _task_sk_checkboxes: dict = {}
                if _task_all_skills:
                    with ui.expansion("✨ Skills override (optional)").classes("w-full"):
                        ui.label(
                            "Choose which skills are active when this task runs. "
                            "Leave unchecked to use the global default."
                        ).style("font-size: 0.75rem; color: #666;")
                        for _tsk in _task_all_skills:
                            _tcb = ui.checkbox(
                                f"{_tsk.icon} {_tsk.display_name}",
                                value=_tsk.name in _task_sk_active,
                            ).classes("text-sm")
                            _task_sk_checkboxes[_tsk.name] = _tcb

                # Run history (edit mode only)
                if not is_new:
                    runs = get_run_history(task["id"], limit=5)
                    if runs:
                        with ui.expansion("📜 Recent runs").classes("w-full"):
                            for r in runs:
                                r_icon = "✅" if r["status"] == "completed" else (
                                    "🔄" if r["status"] == "running" else "❌"
                                )
                                started = datetime.fromisoformat(
                                    r["started_at"]
                                ).strftime("%b %d, %I:%M %p")
                                ui.label(
                                    f"{r_icon} {started} — "
                                    f"{r['steps_done']}/{r['steps_total']} steps"
                                ).classes("text-xs")

        # ── Footer ──
        with ui.row().classes("w-full items-center q-pa-md gap-2").style(
            "border-top: 1px solid #2a2a4a;"
        ):
            # Left cluster — duplicate + delete (edit only)
            if not is_new:
                def _dup_task():
                    duplicate_task(task["id"])
                    p.task_dlg.close()
                    on_done()

                def _del_task():
                    delete_task(task["id"])
                    p.task_dlg.close()
                    on_done()

                ui.button("📋 Duplicate", on_click=_dup_task).props(
                    "flat no-caps"
                ).style("font-size: 0.85rem;")
                ui.button("🗑️ Delete", on_click=_del_task).props(
                    "flat no-caps"
                ).style("color: #ff6b6b; font-size: 0.85rem;")

            # Spacer
            ui.element("div").classes("flex-grow")

            # Right cluster — cancel + save
            ui.button("Cancel", on_click=p.task_dlg.close).props(
                "flat no-caps"
            ).style(
                "color: #8888aa; font-weight: 600; font-size: 0.9rem;"
                "padding: 8px 20px; border-radius: 8px;"
            )

            def _save():
                # Sync prompt textareas
                for j, _ta in enumerate(prompt_inputs):
                    if j < len(_prompts_data):
                        _prompts_data[j] = _ta.value
                clean_prompts = [pp for pp in _prompts_data if pp.strip()]

                # Build schedule string
                sv = sched_sel.value
                final_schedule = None
                if sv == "Daily":
                    t = sched_time_input.value.strip() or "08:00"
                    final_schedule = f"daily:{t}"
                elif sv == "Weekly":
                    t = sched_time_input.value.strip() or "08:00"
                    d = sched_day_sel.value or "mon"
                    final_schedule = f"weekly:{d}:{t}"
                elif sv == "Interval (hrs)":
                    v = sched_interval_input.value.strip() or "1"
                    final_schedule = f"interval:{v}"
                elif sv == "Interval (min)":
                    v = sched_interval_input.value.strip() or "30"
                    final_schedule = f"interval_minutes:{v}"
                elif sv == "Cron":
                    v = sched_cron_input.value.strip()
                    if v:
                        final_schedule = f"cron:{v}"

                cur_name = name_input.value.strip() or "New Task"
                cur_icon = icon_sel.value or "⚡"
                cur_desc = desc_input.value.strip()
                cur_enabled = enabled_switch.value
                cur_del_ch = del_ch_sel.value or None
                cur_del_tgt = del_tgt_input.value.strip() or None if cur_del_ch == "email" else None
                _def_label = f"Default ({get_current_model()})"
                cur_model_ov = model_sel.value if model_sel.value != _def_label else None

                # Parse background permissions
                cur_allowed_cmds = [
                    ln.strip() for ln in allowed_cmds_input.value.split("\n")
                    if ln.strip()
                ]
                cur_allowed_recip = [
                    ln.strip() for ln in allowed_recip_input.value.split("\n")
                    if ln.strip()
                ]

                # Parse skills override
                cur_skills_override = None
                if _task_sk_checkboxes:
                    _checked = [n for n, cb in _task_sk_checkboxes.items() if cb.value]
                    cur_skills_override = _checked if _checked else []

                try:
                    if is_new:
                        _notify_only = len(clean_prompts) == 0
                        create_task(
                            name=cur_name,
                            prompts=clean_prompts,
                            description=cur_desc,
                            icon=cur_icon,
                            schedule=final_schedule,
                            notify_only=_notify_only,
                            delivery_channel=cur_del_ch,
                            delivery_target=cur_del_tgt,
                            model_override=cur_model_ov,
                            skills_override=cur_skills_override,
                        )
                        all_t = list_tasks()
                        if all_t:
                            newest = all_t[-1]
                            perm_updates = {}
                            if cur_allowed_cmds:
                                perm_updates["allowed_commands"] = cur_allowed_cmds
                            if cur_allowed_recip:
                                perm_updates["allowed_recipients"] = cur_allowed_recip
                            if not cur_enabled:
                                perm_updates["enabled"] = False
                            if perm_updates:
                                update_task(newest["id"], **perm_updates)
                        ui.notify("✅ Task created", type="positive")
                    else:
                        updates = {}
                        if cur_name != task["name"]:
                            updates["name"] = cur_name
                        if cur_icon != task["icon"]:
                            updates["icon"] = cur_icon
                        if cur_desc != (task.get("description") or ""):
                            updates["description"] = cur_desc
                        if clean_prompts != task["prompts"]:
                            updates["prompts"] = clean_prompts
                        if final_schedule != task.get("schedule"):
                            updates["schedule"] = final_schedule
                        if cur_enabled != task.get("enabled", True):
                            updates["enabled"] = cur_enabled
                        if cur_del_ch != task.get("delivery_channel"):
                            updates["delivery_channel"] = cur_del_ch
                        if cur_del_tgt != task.get("delivery_target"):
                            updates["delivery_target"] = cur_del_tgt
                        if cur_model_ov != (task.get("model_override") or None):
                            updates["model_override"] = cur_model_ov
                        if cur_allowed_cmds != (task.get("allowed_commands") or []):
                            updates["allowed_commands"] = cur_allowed_cmds
                        if cur_allowed_recip != (task.get("allowed_recipients") or []):
                            updates["allowed_recipients"] = cur_allowed_recip
                        if cur_skills_override != task.get("skills_override"):
                            updates["skills_override"] = cur_skills_override

                        if updates:
                            update_task(task["id"], **updates)
                            ui.notify("💾 Saved", type="positive")
                        else:
                            ui.notify("No changes.", type="info")
                except ValueError as ve:
                    ui.notify(str(ve), type="negative")
                    return

                p.task_dlg.close()
                on_done()

            ui.button("Save", on_click=_save).props(
                "unelevated no-caps"
            ).style(
                "background: #2d8a4e; color: white; font-weight: 600;"
                "font-size: 0.9rem; padding: 8px 28px; border-radius: 8px;"
            )

    p.task_dlg.open()
