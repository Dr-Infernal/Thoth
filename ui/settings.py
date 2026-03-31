"""Thoth UI — Settings dialog with all configuration tabs.

Contains ``open_settings()`` plus 13+ tab builder helpers.
Receives ``state`` and ``p`` explicitly.
"""

from __future__ import annotations

import logging
import os
import pathlib
import tempfile
from typing import Callable

from nicegui import events, run, ui

from ui.state import AppState, P
from ui.constants import ICON_OPTIONS
from ui.helpers import browse_folder, browse_file

logger = logging.getLogger(__name__)


def open_settings(
    state: AppState,
    p: P,
    initial_tab: str = "Models",
) -> None:
    """Build and open the maximised settings dialog.

    Every tab builder is defined locally so it closes over ``state``
    and ``p``.  External deps are imported inside the tab builders to
    keep startup fast.
    """
    # ── imports used across multiple tabs ──
    from api_keys import get_key, set_key, get_cloud_config
    from agent import clear_agent_cache
    from tools import registry as tool_registry
    from models import (
        _ollama_reachable,
        fetch_trending_ollama_models,
        get_trending_models,
        list_local_models,
        list_cloud_models,
        list_cloud_vision_models,
        list_all_models,
        get_current_model,
        is_cloud_model,
        is_model_local,
        is_tool_compatible,
        check_tool_support,
        pull_model,
        set_model,
        get_provider_emoji,
        get_user_context_size,
        set_context_size,
        get_model_max_context,
        refresh_cloud_models,
        star_cloud_model,
        unstar_cloud_model,
        validate_openrouter_key,
        CONTEXT_SIZE_OPTIONS,
        CONTEXT_SIZE_LABELS,
        is_cloud_available,
        _cloud_model_cache,
    )
    from vision import POPULAR_VISION_MODELS, list_cameras
    from documents import load_processed_files, load_and_vectorize_document, reset_vector_store

    # ── Recursive reopen helper ──
    def _reopen(tab: str = initial_tab):
        p.settings_dlg.close()
        open_settings(state, p, initial_tab=tab)

    # ══════════════════════════════════════════════════════════════════
    # TAB BUILDERS
    # ══════════════════════════════════════════════════════════════════

    def _build_documents_tab() -> None:
        ui.label("📄 Local Documents").classes("text-h6")
        ui.label(
            "Upload your own files (PDF, TXT, DOCX, etc.) to build a local knowledge base. "
            "Documents are chunked, vectorized, and stored in a local FAISS database "
            "for fast semantic search. When enabled, the agent will search these "
            "documents to answer questions about your personal content."
        ).classes("text-grey-6 text-sm")

        async def _handle_doc_upload(e: events.UploadEventArguments):
            name = e.file.name
            data = await e.file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=pathlib.Path(name).suffix) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                await run.io_bound(load_and_vectorize_document, tmp_path, True, name)
                ui.notify(f"✅ {name} indexed", type="positive")
            except Exception as exc:
                ui.notify(f"Failed: {exc}", type="negative")
            finally:
                os.unlink(tmp_path)

        ui.upload(
            label="Upload documents (PDF, DOCX, TXT)",
            on_upload=_handle_doc_upload,
            auto_upload=True,
            multiple=True,
        ).classes("w-full")

        ui.separator()
        processed = load_processed_files()
        if processed:
            ui.label(f"📚 {len(processed)} indexed document(s)").classes("font-bold")
            for f in sorted(processed):
                ui.label(f"  • {f}").classes("text-sm")
        else:
            ui.label("No documents indexed yet.").classes("text-grey-6")

        ui.separator()

        def _clear_docs():
            reset_vector_store()
            ui.notify("🗑️ Vector store cleared.", type="info")
            _reopen()

        ui.button("🗑️ Clear all documents", on_click=_clear_docs).props("flat color=negative")

    # ── Models Tab ───────────────────────────────────────────────────

    def _build_models_tab() -> None:
        _ollama_up = _ollama_reachable()
        fetch_trending_ollama_models()
        trending = get_trending_models()

        ui.label("🤖 Models").classes("text-h6")
        ui.label(
            "Thoth uses two models: a Brain model for reasoning, tool use, "
            "and conversation, and a Vision model for camera-based image "
            "analysis. Local models are served through Ollama; cloud models "
            "use your configured API keys."
        ).classes("text-grey-6 text-sm")

        ui.label("✅ Downloaded  ⬇️ Available  🆕 Trending  🟢 OpenAI  🌐 OpenRouter").classes("text-xs text-grey-5 q-mt-xs")
        ui.label("🔑 API keys can be managed in the Cloud tab.").classes("text-xs text-grey-5")

        ui.separator()
        ui.label("🧠 Brain Model").classes("text-h6")
        ui.label(
            "The main reasoning model that powers Thoth's conversations and "
            "tool use. Recommended: 14B+ for best accuracy. "
            "Minimum: 8B — smaller models may struggle with complex tasks."
        ).classes("text-grey-6 text-sm")

        local = list_local_models()
        cloud = list_cloud_models()
        current = state.current_model

        if _ollama_up:
            all_models = sorted(set(list_all_models() + cloud))
        else:
            all_models = sorted(set(cloud + ([current] if not is_cloud_model(current) else [])))

        if current not in all_models:
            all_models = sorted(set(all_models + [current]))

        def _model_label(m, local_override=None):
            loc = local_override if local_override is not None else local
            if is_cloud_model(m):
                return f"{get_provider_emoji(m)}  {m}"
            if m in loc:
                warn = '' if is_tool_compatible(m) else '  ⚠️ may not support tools'
                return f"✅  {m}{warn}"
            if m in trending:
                return f"🆕  {m}"
            warn = '' if is_tool_compatible(m) else '  ⚠️ may not support tools'
            return f"⬇️  {m}{warn}"

        model_opts = {m: _model_label(m) for m in all_models}

        model_select = ui.select(
            label="Select model",
            options=model_opts,
            value=current,
        ).classes("w-full").props('use-input input-debounce=300')

        brain_dl_btn = ui.button(f"⬇️ Download {current}").props("color=primary outline")
        brain_dl_btn.visible = _ollama_up and not is_cloud_model(current) and current not in local

        import sys as _sys
        if _sys.platform == "win32":
            _ollama_install_steps = (
                "1. Download Ollama from ollama.com/download\n"
                "2. Run the installer\n"
                "3. Ollama starts automatically — re-open Settings → Models"
            )
        elif _sys.platform == "darwin":
            _ollama_install_steps = (
                "1. Download Ollama from ollama.com/download (or: brew install ollama)\n"
                "2. Run: ollama serve\n"
                "3. Re-open Settings → Models"
            )
        else:
            _ollama_install_steps = (
                "1. Install: curl -fsSL https://ollama.com/install.sh | sh\n"
                "2. Run: ollama serve\n"
                "3. Re-open Settings → Models"
            )
        with ui.card().classes("w-full q-pa-md bg-amber-1") as ollama_guide:
            ui.label("🖥️ Want to use local models?").classes("text-weight-bold text-body1 text-brown-9")
            ui.label(
                "Local models run on your GPU with full privacy — no data leaves your machine. "
                "You need Ollama installed and running."
            ).classes("text-grey-8 text-sm q-mb-xs")
            ui.label(_ollama_install_steps).classes("text-grey-8 text-xs").style("white-space: pre-line")
            ui.link("Download Ollama →", "https://ollama.com/download", new_tab=True).classes("text-sm text-weight-bold")
        ollama_guide.visible = not _ollama_up

        async def _download_brain(e=None):
            sel = model_select.value
            if is_cloud_model(sel):
                ui.notify(f"{get_provider_emoji(sel)} {sel} is a cloud model — no download needed.", type="info")
                brain_dl_btn.visible = False
                return
            if is_model_local(sel):
                ui.notify(f"✅ {sel} is already downloaded.", type="info")
                brain_dl_btn.visible = False
                return
            if not _ollama_reachable():
                ui.notify("❌ Ollama is not running.", type="negative", close_button=True)
                return
            brain_dl_btn.disable()
            n = ui.notification(f"Downloading {sel}…", type="ongoing", spinner=True, timeout=None)
            await run.io_bound(lambda: list(pull_model(sel)))
            n.dismiss()
            ui.notify(f"✅ {sel} ready!", type="positive")
            brain_dl_btn.visible = False
            brain_dl_btn.enable()
            ollama_guide.visible = False
            refreshed_local = list_local_models()
            model_select.options = {m: _model_label(m, refreshed_local) for m in all_models}
            model_select.update()
            set_model(sel)
            state.current_model = sel
            clear_agent_cache()

        brain_dl_btn.on_click(_download_brain)

        _ctx_note_updater = [None]

        async def _on_model_change(e):
            sel = e.value
            if sel == state.current_model:
                return
            prev = state.current_model
            brain_dl_btn.text = f"⬇️ Download {sel}"
            brain_dl_btn.visible = _ollama_up and not is_cloud_model(sel) and not is_model_local(sel)
            if is_cloud_model(sel):
                set_model(sel)
                state.current_model = sel
                clear_agent_cache()
                if _ctx_note_updater[0]:
                    _ctx_note_updater[0]()
                return
            if not is_model_local(sel):
                return
            if not is_tool_compatible(sel):
                ui.notify(f"Checking tool support for {sel}…", type="info")
                ok = await run.io_bound(lambda: check_tool_support(sel))
                if not ok:
                    ui.notify(
                        f"⚠️ {sel} does not support tool calling. Reverting to {prev}.",
                        type="negative", close_button=True, timeout=10000,
                    )
                    model_select.value = prev
                    return
            set_model(sel)
            state.current_model = sel
            clear_agent_cache()
            if not is_cloud_model(sel):
                model_max = await run.io_bound(lambda: get_model_max_context(sel))
                user_val = get_user_context_size()
                if model_max is not None and user_val > model_max:
                    max_lbl = CONTEXT_SIZE_LABELS.get(model_max, f"{model_max:,}")
                    usr_lbl = CONTEXT_SIZE_LABELS.get(user_val, f"{user_val:,}")
                    ui.notify(
                        f"Context capped: {sel} max is {max_lbl} (you selected {usr_lbl}).",
                        type="warning", close_button=True, timeout=8000,
                    )
            if _ctx_note_updater[0]:
                _ctx_note_updater[0]()

        model_select.on_value_change(_on_model_change)

        ui.separator()

        # Context window
        _is_cloud_ctx = is_cloud_model(state.current_model)
        ctx_opts = {v: CONTEXT_SIZE_LABELS.get(v, str(v)) for v in CONTEXT_SIZE_OPTIONS}

        ctx_cloud_info = ui.label(
            "☁️ Cloud models automatically use their full native context window."
        ).classes("text-xs text-grey-6")
        ctx_cloud_info.visible = _is_cloud_ctx

        _cloud_max = get_model_max_context() if _is_cloud_ctx else None
        _cloud_max_lbl = (
            f"{_cloud_max // 1_000}K" if _cloud_max and _cloud_max < 1_000_000
            else f"{_cloud_max // 1_000_000}M" if _cloud_max else "?"
        )
        ctx_cloud_size = ui.label(
            f"Effective context: {_cloud_max_lbl} tokens"
        ).classes("text-xs text-cyan")
        ctx_cloud_size.visible = _is_cloud_ctx

        ctx_note = ui.label("").classes("text-xs text-warning")
        ctx_note.visible = False

        def _update_ctx_note():
            _cloud = is_cloud_model(state.current_model)
            ctx_cloud_info.visible = _cloud
            ctx_select.visible = not _cloud
            if _cloud:
                _cmax = get_model_max_context()
                if _cmax:
                    _clbl = (
                        f"{_cmax // 1_000}K" if _cmax < 1_000_000
                        else f"{_cmax // 1_000_000}M"
                    )
                    ctx_cloud_size.text = f"Effective context: {_clbl} tokens"
                ctx_cloud_size.visible = True
                ctx_note.visible = False
            else:
                ctx_cloud_size.visible = False
                model_max = get_model_max_context()
                user_val = get_user_context_size()
                if model_max is not None and user_val > model_max:
                    max_label = CONTEXT_SIZE_LABELS.get(model_max, f"{model_max:,}")
                    ctx_note.text = f"ℹ️ Model max is {max_label} — trimming will use {max_label}"
                    ctx_note.visible = True
                else:
                    ctx_note.visible = False

        def _on_ctx_change(e):
            set_context_size(e.value)
            state.context_size = e.value
            clear_agent_cache()
            _update_ctx_note()
            model_max = get_model_max_context()
            if model_max is not None and e.value > model_max:
                max_lbl = CONTEXT_SIZE_LABELS.get(model_max, f"{model_max:,}")
                usr_lbl = CONTEXT_SIZE_LABELS.get(e.value, f"{e.value:,}")
                ui.notify(
                    f"Context capped: model max is {max_lbl} (you selected {usr_lbl}).",
                    type="warning", close_button=True, timeout=8000,
                )

        ctx_select = ui.select(
            label="Local context window",
            options=ctx_opts,
            value=state.context_size,
            on_change=_on_ctx_change,
        ).classes("w-full").tooltip(
            "Controls how many tokens the local model can process. Higher values use more VRAM."
        )
        ctx_select.visible = not _is_cloud_ctx

        _update_ctx_note()
        _ctx_note_updater[0] = _update_ctx_note

        ui.separator()
        ui.label("👁️ Vision Model").classes("text-h6")
        ui.label(
            "The model used for camera and screen capture analysis."
        ).classes("text-grey-6 text-sm")

        vsvc = state.vision_service
        cloud_vision = list_cloud_vision_models()

        if _ollama_up:
            all_vision = sorted(set(
                POPULAR_VISION_MODELS
                + cloud_vision
                + ([vsvc.model] if vsvc.model not in POPULAR_VISION_MODELS and vsvc.model not in cloud_vision else [])
            ))
        else:
            extras = [vsvc.model] if not is_cloud_model(vsvc.model) else []
            all_vision = sorted(set(cloud_vision + extras))

        def _vision_label(m, local_override=None):
            loc = local_override if local_override is not None else local
            if is_cloud_model(m):
                return f"{get_provider_emoji(m)}  {m}"
            if m in loc:
                return f"✅  {m}"
            if m in trending:
                return f"🆕  {m}"
            return f"⬇️  {m}"

        vision_opts = {m: _vision_label(m) for m in all_vision}
        vision_select = ui.select(options=vision_opts, value=vsvc.model).classes("w-full").props('use-input input-debounce=300')

        vision_dl_btn = ui.button(f"⬇️ Download {vsvc.model}").props("color=primary outline")
        vision_dl_btn.visible = _ollama_up and not is_cloud_model(vsvc.model) and vsvc.model not in local

        async def _download_vision(e=None):
            sel = vision_select.value
            if is_cloud_model(sel):
                ui.notify(f"{get_provider_emoji(sel)} {sel} is a cloud model — no download needed.", type="info")
                vision_dl_btn.visible = False
                return
            if is_model_local(sel):
                ui.notify(f"✅ {sel} is already downloaded.", type="info")
                vision_dl_btn.visible = False
                return
            if not _ollama_reachable():
                ui.notify("❌ Ollama is not running.", type="negative", close_button=True)
                return
            vision_dl_btn.disable()
            n = ui.notification(f"Downloading {sel}…", type="ongoing", spinner=True, timeout=None)
            await run.io_bound(lambda: list(pull_model(sel)))
            n.dismiss()
            ui.notify(f"✅ {sel} ready!", type="positive")
            vision_dl_btn.visible = False
            vision_dl_btn.enable()
            refreshed_local = list_local_models()
            vision_select.options = {m: _vision_label(m, refreshed_local) for m in all_vision}
            vision_select.update()
            vsvc.model = sel
            clear_agent_cache()

        vision_dl_btn.on_click(_download_vision)

        async def _on_vision_change(e):
            sel = e.value
            is_cloud = is_cloud_model(sel)
            vision_dl_btn.text = f"⬇️ Download {sel}"
            vision_dl_btn.visible = _ollama_up and not is_cloud and not is_model_local(sel)
            if sel != vsvc.model:
                if is_cloud:
                    vsvc.model = sel
                    clear_agent_cache()
                    return
                if not is_model_local(sel):
                    return
                vsvc.model = sel
                clear_agent_cache()

        vision_select.on_value_change(_on_vision_change)

        cameras = list_cameras()
        if cameras:
            cam_opts = {i: f"Camera {i}" for i in cameras}
            ui.select(label="Camera", options=cam_opts, value=vsvc.camera_index,
                      on_change=lambda e: setattr(vsvc, "camera_index", e.value)).classes("w-full")
        else:
            ui.label("No cameras detected.").classes("text-grey-6 text-sm")

        ui.switch("Enable vision", value=vsvc.enabled,
                  on_change=lambda e: setattr(vsvc, "enabled", e.value)
        ).tooltip("Allow the agent to capture images from your webcam.")

    # ── Cloud Tab ────────────────────────────────────────────────────

    def _build_cloud_tab() -> None:
        ui.label("☁️ Cloud Models").classes("text-h6")
        ui.label(
            "Connect to cloud LLMs via OpenAI (direct) or OpenRouter (100+ models)."
        ).classes("text-grey-6 text-sm")

        _model_list_container = None
        _search_term = {"value": ""}

        def _refresh_model_list():
            nonlocal _model_list_container
            _model_list_container.clear()
            _starred_now = set(get_cloud_config().get("starred_models", []))
            all_models = list_cloud_models()
            if not all_models:
                with _model_list_container:
                    ui.label("No cloud models loaded. Enter a key and click Refresh.").classes("text-grey-6 text-sm")
                return
            q = _search_term["value"].strip().lower()
            if q:
                all_models = [m for m in all_models if q in m.lower()]
            with _model_list_container:
                if q and not all_models:
                    ui.label(f'No models matching "{q}"').classes("text-grey-6 text-sm")
                    return
                for prov_label, prov_key in [("OpenAI", "openai"), ("OpenRouter", "openrouter")]:
                    prov_models = [(m, _cloud_model_cache[m]) for m in all_models
                                   if _cloud_model_cache[m]["provider"] == prov_key]
                    if not prov_models:
                        continue
                    ui.label(f"{prov_label} ({len(prov_models)} models)").style(
                        "font-weight: 600; margin-top: 8px;"
                    )
                    for mid, info in prov_models:
                        with ui.row().classes("items-center gap-1 q-py-xs"):
                            is_starred = mid in _starred_now
                            ui.button(
                                icon="star" if is_starred else "star_border",
                                on_click=lambda _, m=mid: _toggle_star(m),
                            ).props("flat dense round size=sm").style(
                                f"color: {'gold' if is_starred else 'grey'};"
                            )
                            _emoji = get_provider_emoji(mid)
                            ui.label(_emoji).style("font-size: 1rem;")
                            ui.label(mid).style("font-weight: 500; font-size: 0.85rem;")
                            ctx_k = info["ctx"] // 1000 if info["ctx"] >= 1000 else info["ctx"]
                            ctx_label = f"{ctx_k}K" if info["ctx"] < 1_000_000 else f"{info['ctx'] // 1_000_000}M"
                            ui.label(f"({ctx_label} ctx)").classes("text-grey-6 text-xs")
                            if mid == get_current_model():
                                ui.badge("DEFAULT", color="cyan").props("dense")
                            else:
                                ui.button(
                                    "Set default", icon="check",
                                    on_click=lambda _, m=mid: _set_default_model(m),
                                ).props("flat dense size=xs")

        def _toggle_star(model_id):
            starred_now = set(get_cloud_config().get("starred_models", []))
            if model_id in starred_now:
                unstar_cloud_model(model_id)
            else:
                star_cloud_model(model_id)
            _refresh_model_list()

        def _set_default_model(model_id):
            set_model(model_id)
            state.current_model = model_id
            clear_agent_cache()
            ui.notify(f"Default model set to {model_id}", type="positive")
            _refresh_model_list()

        async def _do_refresh():
            n = ui.notification("Fetching models…", type="ongoing", spinner=True, timeout=None)
            count = await run.io_bound(refresh_cloud_models)
            n.dismiss()
            ui.notify(f"Found {count} cloud models", type="positive")
            _refresh_model_list()

        # API Keys
        ui.separator()
        with ui.expansion("🔑 OpenAI Direct", icon="key", value=bool(get_key("OPENAI_API_KEY"))).classes("w-full"):
            ui.label("Direct access to OpenAI models.").classes("text-grey-6 text-sm")
            _oai_key = get_key("OPENAI_API_KEY")
            oai_input = ui.input(
                "OpenAI API Key", value=_oai_key,
                password=True, password_toggle_button=True,
            ).classes("w-full")

            async def _save_oai():
                val = oai_input.value.strip()
                set_key("OPENAI_API_KEY", val)
                ui.notify("OpenAI key saved ✅", type="positive")
                if val:
                    await run.io_bound(refresh_cloud_models)
                    _refresh_model_list()
            ui.button("Save Key", icon="save", on_click=_save_oai).props("flat dense")

        with ui.expansion("🌐 OpenRouter", icon="language", value=bool(get_key("OPENROUTER_API_KEY"))).classes("w-full"):
            ui.label("One key for Claude, Gemini, Llama, and 100+ more.").classes("text-grey-6 text-sm")
            _or_key = get_key("OPENROUTER_API_KEY")
            or_input = ui.input(
                "OpenRouter API Key", value=_or_key,
                password=True, password_toggle_button=True,
            ).classes("w-full")

            async def _save_or():
                val = or_input.value.strip()
                if val:
                    valid = await run.io_bound(validate_openrouter_key, val)
                    if not valid:
                        ui.notify("❌ Invalid OpenRouter API key", type="negative")
                        return
                set_key("OPENROUTER_API_KEY", val)
                ui.notify("OpenRouter key saved ✅", type="positive")
                if val:
                    await run.io_bound(refresh_cloud_models)
                    _refresh_model_list()
            ui.button("Save Key", icon="save", on_click=_save_or).props("flat dense")

        # Setup Guide
        ui.separator()
        with ui.expansion("📖 Setup Guide", icon="help_outline").classes("w-full"):
            ui.markdown(
                "### OpenAI Direct\n\n"
                "1. Go to [platform.openai.com](https://platform.openai.com) → API Keys\n"
                "2. Create a new key and paste it above\n\n"
                "### OpenRouter\n\n"
                "1. Go to [openrouter.ai](https://openrouter.ai) and create an account\n"
                "2. Navigate to **Keys** → **Create Key** and paste it above\n\n"
                "### Usage\n\n"
                "- ⭐ **Star** models to add them to the chat header model picker\n"
                "- Click **Set default** to use a cloud model as your app-wide default\n"
                "- Use `/model <id>` in Telegram to switch models per-chat\n"
                "- Cloud models appear with provider-specific icons in the sidebar\n"
                "- All API keys are stored locally and never shared"
            )

        # Available Models
        ui.separator()
        with ui.row().classes("items-center gap-2"):
            ui.label("Available Models").style("font-weight: 600;")
            ui.button(icon="refresh", on_click=_do_refresh).props("flat round dense").tooltip(
                "Refresh model list from cloud providers"
            )
        ui.label(
            "⭐ Star models to show them in the thread model picker."
        ).classes("text-grey-6 text-sm")

        def _on_search(e):
            _search_term["value"] = e.value or ""
            _refresh_model_list()

        ui.input(
            placeholder="Search models…",
            on_change=_on_search,
        ).classes("w-full").props("outlined dense clearable").style("max-width: 400px;")

        _model_list_container = ui.column().classes("w-full")

        async def _initial_fetch():
            await run.io_bound(refresh_cloud_models)
            _refresh_model_list()
        ui.timer(0.5, _initial_fetch, once=True)

    # ── Skills Tab ───────────────────────────────────────────────────

    def _build_skills_tab() -> None:
        import skills as skills_mod

        ui.label("✨ Skills").classes("text-h6")
        ui.label(
            "Skills teach the agent step-by-step workflows using your existing tools."
        ).classes("text-grey-6 text-sm")
        ui.separator().classes("q-my-md")

        skills_container = ui.column().classes("w-full gap-2")

        def _refresh_skills_list():
            skills_container.clear()
            all_skills = skills_mod.get_all_skills()
            if not all_skills:
                with skills_container:
                    ui.label("No skills found. Create one to get started!").classes("text-grey-5 italic")
                return

            with skills_container:
                for sk in all_skills:
                    with ui.card().classes("w-full q-pa-sm"):
                        with ui.row().classes("w-full items-center no-wrap"):
                            ui.switch(
                                "",
                                value=skills_mod.is_enabled(sk.name),
                                on_change=lambda e, n=sk.name: skills_mod.set_enabled(n, e.value),
                            )
                            ui.label(f"{sk.icon} {sk.display_name}").classes("text-body1 text-weight-medium")
                            ui.space()
                            if sk.source == "bundled":
                                ui.badge("Bundled", color="blue-grey").props("outline")
                            else:
                                ui.badge("Custom", color="teal").props("outline")
                            tokens = skills_mod.estimate_tokens([sk.name])
                            if tokens > 0:
                                ui.badge(f"~{tokens} tokens", color="orange").props(
                                    "outline"
                                ).tooltip("Approximate tokens added to context when enabled")
                        ui.label(sk.description).classes("text-grey-6 text-sm q-pl-lg")

                        if sk.tools:
                            with ui.row().classes("q-pl-lg gap-1 q-mt-xs"):
                                ui.label("Tools:").classes("text-grey-5 text-xs")
                                for t in sk.tools:
                                    _enabled = tool_registry.is_enabled(t)
                                    _color = "positive" if _enabled else "warning"
                                    ui.badge(t, color=_color).props("outline dense")

                        with ui.row().classes("q-pl-lg q-mt-xs gap-1"):
                            if sk.source == "user":
                                ui.button(
                                    "Edit", icon="edit",
                                    on_click=lambda _, n=sk.name: _open_skill_editor(n),
                                ).props("flat dense size=sm")
                                ui.button(
                                    "Delete", icon="delete",
                                    on_click=lambda _, n=sk.name: _confirm_delete_skill(n),
                                ).props("flat dense size=sm color=negative")
                            else:
                                ui.button(
                                    "Duplicate & Customise", icon="content_copy",
                                    on_click=lambda _, n=sk.name: _duplicate_skill(n),
                                ).props("flat dense size=sm")

        def _open_skill_editor(name=None):
            skill = skills_mod.get_skill(name) if name else None
            is_edit = skill is not None

            with ui.dialog().props("persistent maximized=false") as dlg, ui.card().classes(
                "w-full"
            ).style("min-width: 600px; max-width: 800px;"):
                ui.label(f"{'Edit' if is_edit else 'Create'} Skill").classes("text-h6")
                name_input = ui.input(
                    "Name (identifier)",
                    value=skill.name if skill else "",
                    validation={"Required": lambda v: bool(v.strip())},
                ).classes("w-full")
                if is_edit:
                    name_input.props("readonly")

                display_input = ui.input(
                    "Display Name", value=skill.display_name if skill else "",
                ).classes("w-full")

                _wf_icon_opts = list(ICON_OPTIONS)
                _icon = skill.icon if skill else "✨"
                if _icon not in _wf_icon_opts:
                    _wf_icon_opts.insert(0, _icon)
                with ui.row().classes("w-full items-end gap-4"):
                    icon_sel = ui.select(label="Icon", options=_wf_icon_opts, value=_icon).classes("w-20")
                    desc_input = ui.input(
                        "Description (one line)", value=skill.description if skill else "",
                    ).classes("flex-grow")

                ui.label("Tool Dependencies (optional)").classes("text-sm font-bold mt-2")
                _all_tools = [t.name for t in tool_registry.get_all_tools()]
                _selected_tools = list(skill.tools) if skill else []
                tool_checkboxes = {}
                with ui.row().classes("w-full gap-4 flex-wrap"):
                    for tname in _all_tools:
                        cb = ui.checkbox(tname, value=tname in _selected_tools)
                        tool_checkboxes[tname] = cb

                tags_input = ui.input(
                    "Tags (comma-separated)",
                    value=", ".join(skill.tags) if skill and skill.tags else "",
                ).classes("w-full")

                ui.label("Instructions").classes("text-sm font-bold mt-4")
                instructions_input = ui.textarea(
                    value=skill.instructions if skill else "",
                ).classes("w-full").props('rows="12"')

                def _update_token_est():
                    txt = instructions_input.value or ""
                    est = len(txt) // 4
                    token_label.text = f"~{est} tokens"

                with ui.row().classes("w-full items-center"):
                    token_label = ui.label("~0 tokens").classes("text-grey-5 text-sm")
                    _update_token_est()
                    instructions_input.on("blur", lambda: _update_token_est())

                with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")

                    def _save():
                        _name = name_input.value.strip()
                        _display = display_input.value.strip() or _name.replace("_", " ").title()
                        _desc = desc_input.value.strip()
                        _icon_val = icon_sel.value
                        _instr = instructions_input.value.strip()
                        _tools = [n for n, cb in tool_checkboxes.items() if cb.value]
                        _tags = [t.strip() for t in tags_input.value.split(",") if t.strip()]
                        if not _name:
                            ui.notify("Name is required", type="warning")
                            return
                        if not _instr:
                            ui.notify("Instructions are required", type="warning")
                            return
                        if is_edit:
                            skills_mod.update_skill(
                                name=_name, display_name=_display, icon=_icon_val,
                                description=_desc, instructions=_instr, tools=_tools, tags=_tags,
                            )
                            ui.notify(f"✅ Skill '{_display}' updated", type="positive")
                        else:
                            skills_mod.create_skill(
                                name=_name, display_name=_display, icon=_icon_val,
                                description=_desc, instructions=_instr, tools=_tools, tags=_tags,
                            )
                            ui.notify(f"✅ Skill '{_display}' created", type="positive")
                        dlg.close()
                        _refresh_skills_list()

                    ui.button("Save", icon="save", on_click=_save).props("color=primary")

            dlg.open()

        def _confirm_delete_skill(name):
            sk = skills_mod.get_skill(name)
            if not sk:
                return
            with ui.dialog() as dlg, ui.card():
                ui.label(f"Delete skill '{sk.display_name}'?").classes("text-body1")
                ui.label("This will permanently remove the skill files.").classes("text-grey-6 text-sm")
                with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    def _do_delete():
                        skills_mod.delete_skill(name)
                        ui.notify(f"Skill '{sk.display_name}' deleted", type="info")
                        dlg.close()
                        _refresh_skills_list()
                    ui.button("Delete", on_click=_do_delete).props("color=negative")
            dlg.open()

        def _duplicate_skill(name):
            result = skills_mod.duplicate_skill(name)
            if result:
                ui.notify(f"✅ Duplicated as '{result.display_name}'", type="positive")
                _refresh_skills_list()
            else:
                ui.notify("Failed to duplicate skill", type="negative")

        with ui.row().classes("w-full justify-end q-mb-md"):
            ui.button("Create Skill", icon="add", on_click=lambda: _open_skill_editor()).props("color=primary")

        skills_mod.load_skills()
        _refresh_skills_list()

    # ── Search / Tools Tab ───────────────────────────────────────────

    def _build_tools_tab() -> None:
        ui.label("⚡ Retrieval Compression").classes("text-h6")
        ui.label(
            "Controls how search results are filtered before reaching the model."
        ).classes("text-grey-6 text-sm")
        _comp_options = {"smart": "Smart (fast)", "deep": "Deep (LLM)", "off": "Off"}
        ui.select(
            label="Compression mode",
            options=_comp_options,
            value=tool_registry.get_global_config("compression_mode", "smart"),
            on_change=lambda e: tool_registry.set_global_config("compression_mode", e.value),
        ).classes("w-60")
        ui.separator().classes("q-my-md")

        ui.label("🔍 Search & Knowledge Tools").classes("text-h6")
        ui.label("Enable or disable search and knowledge tools.").classes("text-grey-6 text-sm")
        ui.separator()

        skip_tools = {
            "filesystem", "shell", "gmail", "documents", "calendar", "timer",
            "url_reader", "calculator", "weather", "vision", "chart",
            "system_info", "conversation_search", "memory", "tracker",
            "browser", "telegram", "task",
        }
        for tool in tool_registry.get_all_tools():
            if tool.name in skip_tools:
                continue
            _build_tool_toggle(tool)
            ui.separator()

    def _build_tool_toggle(tool) -> None:
        ui.switch(
            tool.display_name,
            value=tool_registry.is_enabled(tool.name),
            on_change=lambda e, n=tool.name: tool_registry.set_enabled(n, e.value),
        ).tooltip(tool.description)

        if tool.name == "web_search":
            with ui.expansion("📋 Tavily Setup Instructions"):
                ui.markdown(
                    "1. Go to [app.tavily.com](https://app.tavily.com/) and sign up.\n"
                    "2. Create an API key.\n"
                    "3. Paste the key below.",
                    extras=['code-friendly', 'fenced-code-blocks', 'tables'],
                )
        elif tool.name == "wolfram_alpha":
            with ui.expansion("📋 Wolfram Alpha Setup Instructions"):
                ui.markdown(
                    "1. Go to [developer.wolframalpha.com](https://developer.wolframalpha.com/) and sign up.\n"
                    "2. Click **Get an AppID** and create an app.\n"
                    "3. Paste the AppID below.",
                    extras=['code-friendly', 'fenced-code-blocks', 'tables'],
                )

        if tool.required_api_keys:
            for label, env_var in tool.required_api_keys.items():
                current_val = get_key(env_var)
                ui.input(
                    label, value=current_val, password=True, password_toggle_button=True,
                    on_change=lambda e, ev=env_var: set_key(ev, e.value),
                ).classes("w-full")

        schema = tool.config_schema
        if schema:
            for cfg_key, spec in schema.items():
                cfg_type = spec.get("type", "text")
                cfg_label = spec.get("label", cfg_key)
                cfg_default = spec.get("default")
                current_cfg = tool.get_config(cfg_key, cfg_default)
                if cfg_type == "text":
                    ui.input(
                        cfg_label, value=current_cfg or "",
                        on_change=lambda e, t=tool, k=cfg_key: t.set_config(k, e.value),
                    ).classes("w-full")
                elif cfg_type == "multicheck":
                    options = spec.get("options", [])
                    current_list = current_cfg if isinstance(current_cfg, list) else (cfg_default or [])
                    ui.label(cfg_label).classes("text-sm font-bold mt-2")
                    for opt in options:
                        ui.checkbox(
                            opt, value=opt in current_list,
                            on_change=lambda e, t=tool, k=cfg_key, o=opt, cl=current_list: (
                                cl.append(o) if e.value and o not in cl else (cl.remove(o) if not e.value and o in cl else None),
                                t.set_config(k, list(cl)),
                            ),
                        )

    def _build_ops_checkboxes(groups, current_ops, tool, cfg_key="selected_operations"):
        ui.label("Allowed operations").classes("text-sm font-bold mt-2")
        selected = list(current_ops)

        def _toggle(op, val):
            if val and op not in selected:
                selected.append(op)
            elif not val and op in selected:
                selected.remove(op)
            tool.set_config(cfg_key, list(selected))

        with ui.row().classes("w-full gap-8"):
            for header, ops in groups:
                with ui.column():
                    ui.label(header).classes("font-bold text-sm")
                    for op in ops:
                        ui.checkbox(op, value=op in current_ops,
                                    on_change=lambda e, o=op: _toggle(o, e.value))

    # ── System Access Tab ────────────────────────────────────────────

    def _build_system_access_tab() -> None:
        from tools.filesystem_tool import _SAFE_OPS, _WRITE_OPS, _DESTRUCTIVE_OPS

        ui.label("🖥️ System Access").classes("text-h6")
        ui.label("Give Thoth access to your local system.").classes("text-grey-6 text-sm")

        fs_tool = tool_registry.get_tool("filesystem")
        if not fs_tool:
            ui.label("Filesystem tool not found.").classes("text-negative")
            return

        ui.separator()
        ui.label("📂 Workspace Folder").classes("text-subtitle1 font-bold")
        ui.label(
            "The Filesystem tool is sandboxed to this folder."
        ).classes("text-grey-6 text-xs")

        fs_root_default = fs_tool.config_schema.get("workspace_root", {}).get("default", "")
        current_root = fs_tool.get_config("workspace_root", fs_root_default)
        root_input = ui.input(
            "Workspace folder", value=current_root or "",
            on_change=lambda e: fs_tool.set_config("workspace_root", e.value),
        ).classes("w-full")

        async def _browse_ws():
            folder = await browse_folder("Select Workspace folder", current_root)
            if folder:
                root_input.value = folder
                fs_tool.set_config("workspace_root", folder)

        ui.button("Browse…", on_click=_browse_ws).props("flat dense")

        if current_root and not os.path.isdir(current_root):
            ui.label(f"⚠️ Folder not found: {current_root}").classes("text-warning text-sm")

        # Shell Access
        ui.separator()
        ui.label("🖥️ Shell Access").classes("text-subtitle1 font-bold")
        ui.label("Run shell commands directly on your system.").classes("text-grey-6 text-xs")

        shell_tool = tool_registry.get_tool("shell")
        if shell_tool:
            ui.switch(
                "Enable Shell tool",
                value=tool_registry.is_enabled("shell"),
                on_change=lambda e: tool_registry.set_enabled("shell", e.value),
            ).tooltip(shell_tool.description)

            shell_blocked = shell_tool.get_config("blocked_commands", "")
            ui.input(
                "Additional blocked patterns (comma-separated)",
                value=shell_blocked or "",
                on_change=lambda e: shell_tool.set_config("blocked_commands", e.value),
            ).classes("w-full")
        else:
            ui.label("Shell tool not found.").classes("text-grey-6 text-sm")

        # Browser Automation
        ui.separator()
        ui.label("🌐 Browser Automation").classes("text-subtitle1 font-bold")
        ui.label("Open a real browser window that you and the agent share.").classes("text-grey-6 text-xs")

        browser_tool = tool_registry.get_tool("browser")
        if browser_tool:
            ui.switch(
                "Enable Browser tool",
                value=tool_registry.is_enabled("browser"),
                on_change=lambda e: tool_registry.set_enabled("browser", e.value),
            ).tooltip(browser_tool.description)
        else:
            ui.label("Browser tool not found.").classes("text-grey-6 text-sm")

        # File Operations
        ui.separator()
        ui.label("📁 File Operations").classes("text-subtitle1 font-bold")
        ui.label("Read, write, search, copy, move, and delete files.").classes("text-grey-6 text-xs")

        ui.switch(
            "Enable Filesystem tool",
            value=tool_registry.is_enabled("filesystem"),
            on_change=lambda e: tool_registry.set_enabled("filesystem", e.value),
        ).tooltip(fs_tool.description)

        ops_default = fs_tool.config_schema.get("selected_operations", {}).get("default", [])
        current_ops = fs_tool.get_config("selected_operations", ops_default)
        if not isinstance(current_ops, list):
            current_ops = ops_default
        _build_ops_checkboxes(
            [("Read-only", _SAFE_OPS), ("Write", _WRITE_OPS), ("⚠️ Destructive", _DESTRUCTIVE_OPS)],
            current_ops, fs_tool,
        )

    # ── Gmail Tab ────────────────────────────────────────────────────

    def _build_gmail_tab() -> None:
        gmail_tool = tool_registry.get_tool("gmail")
        if not gmail_tool:
            ui.label("Gmail tool not found.").classes("text-negative")
            return

        ui.label("📧 Gmail Integration").classes("text-h6")
        ui.label("Connect Thoth to your Gmail account.").classes("text-grey-6 text-sm")

        ui.switch(
            "Enable Gmail tool",
            value=tool_registry.is_enabled("gmail"),
            on_change=lambda e: tool_registry.set_enabled("gmail", e.value),
        ).tooltip(gmail_tool.description)

        with ui.expansion("📋 Setup Instructions"):
            ui.markdown(
                "1. Go to [Google Cloud Console](https://console.cloud.google.com) → New Project\n"
                "2. Enable **Gmail API**\n"
                "3. Create OAuth client ID (Desktop app)\n"
                "4. Download credentials.json\n"
                "5. Click Authenticate below",
                extras=['code-friendly', 'fenced-code-blocks', 'tables'],
            )

        ui.separator()

        creds_default = gmail_tool.config_schema.get("credentials_path", {}).get("default", "")
        current_creds = gmail_tool.get_config("credentials_path", creds_default)
        creds_input = ui.input(
            "credentials.json path", value=current_creds or "",
            on_change=lambda e: gmail_tool.set_config("credentials_path", e.value),
        ).classes("w-full")

        async def _browse_creds():
            path = await browse_file(
                "Select credentials.json",
                os.path.dirname(current_creds) if current_creds else "",
                [("JSON files", "*.json")],
            )
            if path:
                creds_input.value = path
                gmail_tool.set_config("credentials_path", path)

        ui.button("Browse…", on_click=_browse_creds).props("flat dense")
        ui.separator()

        if gmail_tool.has_credentials_file():
            if gmail_tool.is_authenticated():
                ui.label("✅ Authenticated with Gmail").classes("text-positive")

                async def _reauth_gmail():
                    try:
                        token_path = gmail_tool._get_token_path()
                        if os.path.isfile(token_path):
                            os.remove(token_path)
                        await run.io_bound(gmail_tool.authenticate)
                        clear_agent_cache()
                        ui.notify("✅ Gmail re-authenticated!", type="positive")
                        _reopen("Gmail")
                    except Exception as e:
                        ui.notify(f"Auth failed: {e}", type="negative")

                ui.button("🔄 Re-authenticate", on_click=_reauth_gmail).props("flat dense")
            else:
                ui.label("🔑 Credentials found but not authenticated.").classes("text-warning")

                async def _auth_gmail():
                    try:
                        await run.io_bound(gmail_tool.authenticate)
                        clear_agent_cache()
                        ui.notify("✅ Gmail authenticated!", type="positive")
                        _reopen("Gmail")
                    except Exception as e:
                        ui.notify(f"Auth failed: {e}", type="negative")

                ui.button("Authenticate…", on_click=_auth_gmail)
        else:
            ui.label("Point path above to your credentials.json").classes("text-grey-6 text-sm")

        ui.separator()
        from tools.gmail_tool import _READ_OPS, _COMPOSE_OPS, _SEND_OPS
        ops_default = gmail_tool.config_schema.get("selected_operations", {}).get("default", [])
        current_ops = gmail_tool.get_config("selected_operations", ops_default)
        if not isinstance(current_ops, list):
            current_ops = ops_default
        _build_ops_checkboxes(
            [("Read", _READ_OPS), ("Compose", _COMPOSE_OPS), ("⚠️ Send", _SEND_OPS)],
            current_ops, gmail_tool,
        )

    # ── Calendar Tab ─────────────────────────────────────────────────

    def _build_calendar_tab() -> None:
        cal_tool = tool_registry.get_tool("calendar")
        if not cal_tool:
            ui.label("Calendar tool not found.").classes("text-negative")
            return

        ui.label("📅 Google Calendar").classes("text-h6")
        ui.label("Connect Thoth to Google Calendar.").classes("text-grey-6 text-sm")

        ui.switch(
            "Enable Calendar tool",
            value=tool_registry.is_enabled("calendar"),
            on_change=lambda e: tool_registry.set_enabled("calendar", e.value),
        ).tooltip(cal_tool.description)

        with ui.expansion("📋 Setup Instructions"):
            ui.markdown(
                "Uses the same Google Cloud credentials as Gmail.\n\n"
                "1. Enable **Google Calendar API**\n"
                "2. Point credentials path below\n"
                "3. Click Authenticate",
                extras=['code-friendly', 'fenced-code-blocks', 'tables'],
            )

        ui.separator()

        cal_creds_default = cal_tool.config_schema.get("credentials_path", {}).get("default", "")
        current_cal_creds = cal_tool.get_config("credentials_path", cal_creds_default)
        cal_creds_input = ui.input(
            "credentials.json path", value=current_cal_creds or "",
            on_change=lambda e: cal_tool.set_config("credentials_path", e.value),
        ).classes("w-full")

        async def _browse_cal_creds():
            path = await browse_file(
                "Select credentials.json",
                os.path.dirname(current_cal_creds) if current_cal_creds else "",
                [("JSON files", "*.json")],
            )
            if path:
                cal_creds_input.value = path
                cal_tool.set_config("credentials_path", path)

        ui.button("Browse…", on_click=_browse_cal_creds).props("flat dense")
        ui.separator()

        if cal_tool.has_credentials_file():
            if cal_tool.is_authenticated():
                ui.label("✅ Authenticated with Calendar").classes("text-positive")

                async def _reauth_cal():
                    try:
                        token_path = cal_tool._get_token_path()
                        if os.path.isfile(token_path):
                            os.remove(token_path)
                        await run.io_bound(cal_tool.authenticate)
                        clear_agent_cache()
                        ui.notify("✅ Calendar re-authenticated!", type="positive")
                        _reopen("Calendar")
                    except Exception as e:
                        ui.notify(f"Auth failed: {e}", type="negative")

                ui.button("🔄 Re-authenticate", on_click=_reauth_cal).props("flat dense")
            else:
                ui.label("🔑 Credentials found but not authenticated.").classes("text-warning")

                async def _auth_cal():
                    try:
                        await run.io_bound(cal_tool.authenticate)
                        clear_agent_cache()
                        ui.notify("✅ Calendar authenticated!", type="positive")
                        _reopen("Calendar")
                    except Exception as e:
                        ui.notify(f"Auth failed: {e}", type="negative")

                ui.button("Authenticate…", on_click=_auth_cal)
        else:
            ui.label("Point path above to your credentials.json").classes("text-grey-6 text-sm")

        ui.separator()
        from tools.calendar_tool import (
            _READ_OPS as CAL_READ_OPS,
            _WRITE_OPS as CAL_WRITE_OPS,
            _DESTRUCTIVE_OPS as CAL_DESTRUCTIVE_OPS,
        )
        cal_ops_default = cal_tool.config_schema.get("selected_operations", {}).get("default", [])
        current_cal_ops = cal_tool.get_config("selected_operations", cal_ops_default)
        if not isinstance(current_cal_ops, list):
            current_cal_ops = cal_ops_default
        _build_ops_checkboxes(
            [("Read", CAL_READ_OPS), ("Write", CAL_WRITE_OPS), ("⚠️ Destructive", CAL_DESTRUCTIVE_OPS)],
            current_cal_ops, cal_tool,
        )

    # ── Utilities Tab ────────────────────────────────────────────────

    def _build_utilities_tab() -> None:
        ui.label("🔧 Utility Tools").classes("text-h6")
        ui.label("Lightweight productivity tools.").classes("text-grey-6 text-sm")
        ui.separator()
        util_names = ["task", "timer", "url_reader", "calculator", "weather", "chart", "system_info", "conversation_search"]
        for uname in util_names:
            utool = tool_registry.get_tool(uname)
            if utool is None:
                continue
            ui.switch(
                utool.display_name,
                value=tool_registry.is_enabled(uname),
                on_change=lambda e, n=uname: tool_registry.set_enabled(n, e.value),
            ).tooltip(utool.description)
            ui.separator()

    # ── Tracker Tab ──────────────────────────────────────────────────

    def _build_tracker_tab() -> None:
        from tools.tracker_tool import _get_db, _get_all_trackers, _DB_PATH

        ui.label("\U0001f4cb Habit & Health Tracker").classes("text-h6")
        ui.label("Track recurring activities, habits, symptoms, and health events.").classes("text-grey-6 text-sm")

        tracker_tool = tool_registry.get_tool("tracker")
        if not tracker_tool:
            ui.label("Tracker tool not found.").classes("text-negative")
            return

        ui.switch(
            "Enable Habit Tracker",
            value=tool_registry.is_enabled("tracker"),
            on_change=lambda e: tool_registry.set_enabled("tracker", e.value),
        ).tooltip(tracker_tool.description)

        ui.separator()

        try:
            conn = _get_db()
            trackers = _get_all_trackers(conn)
            total_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            conn.close()
        except Exception:
            trackers = []
            total_entries = 0

        ui.label(f"Active trackers: {len(trackers)}  ·  Total entries: {total_entries}").classes("font-bold")

        if trackers:
            tracker_container = ui.column().classes("w-full")

            def _refresh_trackers():
                tracker_container.clear()
                try:
                    c = _get_db()
                    tlist = _get_all_trackers(c)
                    with tracker_container:
                        if not tlist:
                            ui.label("No trackers yet.").classes("text-grey-6")
                        else:
                            for t in tlist:
                                entry_count = c.execute(
                                    "SELECT COUNT(*) FROM entries WHERE tracker_id = ?",
                                    (t["id"],),
                                ).fetchone()[0]
                                last_entry = c.execute(
                                    "SELECT timestamp FROM entries WHERE tracker_id = ? ORDER BY timestamp DESC LIMIT 1",
                                    (t["id"],),
                                ).fetchone()
                                last_str = last_entry[0][:10] if last_entry else "never"
                                type_badge = t["type"]
                                if t.get("unit"):
                                    type_badge += f" ({t['unit']})"
                                with ui.row().classes("w-full items-center gap-2"):
                                    ui.label(f"● {t['name']}").classes("font-bold")
                                    ui.badge(type_badge).props("outline")
                                    ui.label(f"{entry_count} entries · last: {last_str}").classes("text-xs text-grey-6")
                                ui.separator()
                    c.close()
                except Exception as exc:
                    with tracker_container:
                        ui.label(f"Error loading trackers: {exc}").classes("text-negative")

            _refresh_trackers()

            ui.separator()

            async def _delete_all_tracker_data():
                confirm = await ui.run_javascript(
                    "confirm('Delete ALL tracker data? This cannot be undone.')",
                    timeout=30,
                )
                if confirm:
                    try:
                        c = _get_db()
                        c.execute("DELETE FROM entries")
                        c.execute("DELETE FROM trackers")
                        c.commit()
                        c.close()
                        ui.notify("All tracker data deleted.", type="info")
                        _refresh_trackers()
                    except Exception as exc:
                        ui.notify(f"Error: {exc}", type="negative")

            ui.button("🗑️ Delete All Tracker Data", on_click=_delete_all_tracker_data).props("flat dense color=negative")
        else:
            ui.label("No trackers yet.").classes("text-grey-6 mt-2")

    # ── Memory Tab ───────────────────────────────────────────────────

    def _build_memory_tab() -> None:
        import knowledge_graph as kg
        import memory as memory_db

        ui.label("🧠 Memory").classes("text-h6")
        ui.label("Thoth builds a memory map from your conversations.").classes("text-grey-6 text-sm")

        mem_tool = tool_registry.get_tool("memory")
        if mem_tool:
            ui.switch(
                "Enable Memory",
                value=tool_registry.is_enabled("memory"),
                on_change=lambda e: tool_registry.set_enabled("memory", e.value),
            )

        ui.separator()

        total = memory_db.count_memories()
        rel_count = kg.count_relations()

        with ui.row().classes("gap-6"):
            ui.label(f"Entities: {total}").classes("font-bold")
            ui.label(f"Relations: {rel_count}").classes("font-bold")

        if total > 0:
            try:
                stats = kg.get_graph_stats()
                type_parts = [f"{t}: {c}" for t, c in sorted(stats.get("entity_types", {}).items())]
                if type_parts:
                    ui.label(f"Types — {', '.join(type_parts)}").classes("text-xs text-grey-6")
                if stats.get("connected_components", 0) > 0:
                    ui.label(
                        f"Memory graph — {stats['connected_components']} component(s), "
                        f"largest: {stats['largest_component']} memories, "
                        f"{stats['isolated_entities']} isolated"
                    ).classes("text-xs text-grey-6")
            except Exception:
                pass

        ui.separator()

        if total > 0:
            cat_options = ["All"] + sorted(memory_db.VALID_CATEGORIES)
            cat_sel = ui.select(label="Filter by category", options=cat_options, value="All").classes("w-full")
            search_input = ui.input("Search memories", placeholder="Type a keyword…").classes("w-full")
            mem_container = ui.column().classes("w-full")

            def _refresh_memories():
                mem_container.clear()
                cat = None if cat_sel.value == "All" else cat_sel.value
                q = search_input.value
                if q:
                    memories = memory_db.search_memories(q, category=cat)
                else:
                    memories = memory_db.list_memories(category=cat)
                with mem_container:
                    if not memories:
                        ui.label("No matching memories.").classes("text-grey-6")
                    else:
                        for mem in memories:
                            with ui.expansion(f"**{mem['subject']}** — _{mem.get('category', mem.get('entity_type', ''))}_").classes("w-full"):
                                content = mem.get("content", mem.get("description", ""))
                                ui.markdown(content, extras=['code-friendly', 'fenced-code-blocks', 'tables'])
                                aliases = mem.get("aliases", "")
                                if aliases:
                                    ui.label(f"Aliases: {aliases}").classes("text-xs text-grey-6")
                                tags = mem.get("tags", "")
                                if tags:
                                    ui.label(f"Tags: {tags}").classes("text-xs text-grey-6")
                                try:
                                    rels = kg.get_relations(mem["id"])
                                    if rels:
                                        rel_lines = []
                                        for r in rels[:5]:
                                            arrow = "→" if r["direction"] == "outgoing" else "←"
                                            rel_lines.append(f"{arrow} {r['relation_type']}: {r['peer_subject']}")
                                        rel_text = " · ".join(rel_lines)
                                        if len(rels) > 5:
                                            rel_text += f" … +{len(rels) - 5} more"
                                        ui.label(f"🔗 {rel_text}").classes("text-xs text-blue-4")
                                except Exception:
                                    pass
                                ui.label(
                                    f"ID: {mem['id']} · Created: {mem['created_at'][:16]} · Updated: {mem['updated_at'][:16]}"
                                ).classes("text-xs text-grey-6")

                                def _del_mem(mid=mem["id"]):
                                    memory_db.delete_memory(mid)
                                    ui.notify("Memory deleted.", type="info")
                                    _refresh_memories()

                                ui.button("🗑️ Delete", on_click=_del_mem).props("flat dense color=negative")

            cat_sel.on("update:model-value", lambda _: _refresh_memories())
            search_input.on("update:model-value", lambda _: _refresh_memories())
            _refresh_memories()

            ui.separator()

            def _delete_all_memories():
                memory_db.delete_all_memories()
                ui.notify("All memories deleted.", type="info")
                _reopen("Memory")

            with ui.row().classes("w-full"):
                ui.button("🗑️ Delete all memories", on_click=_delete_all_memories).props("flat color=negative")

    # ── Voice Tab ────────────────────────────────────────────────────

    def _build_voice_tab() -> None:
        from voice import get_available_whisper_sizes
        from tts import VOICE_CATALOG

        ui.label("🎤 Voice Input").classes("text-h6")
        ui.label("Talk to Thoth hands-free using voice input.").classes("text-grey-6 text-sm")

        voice_svc = state.voice_service

        whisper_sizes = get_available_whisper_sizes()
        whisper_labels = {
            "tiny": "Tiny (~39 MB, fastest)", "base": "Base (~74 MB, balanced)",
            "small": "Small (~244 MB, accurate)", "medium": "Medium (~769 MB, best accuracy)",
        }
        whisper_opts = {s: whisper_labels.get(s, s) for s in whisper_sizes}
        ui.select(
            label="Whisper model size", options=whisper_opts,
            value=voice_svc.whisper_size,
            on_change=lambda e: setattr(voice_svc, "whisper_size", e.value),
        ).classes("w-full")

        ui.separator()

        ui.label("🔊 Text-to-Speech").classes("text-h6")
        ui.label("Enable text-to-speech to hear Thoth read responses aloud.").classes("text-grey-6 text-sm")

        tts = state.tts_service

        if not tts.is_installed():
            async def _install_kokoro():
                ui.notify("Downloading Kokoro TTS model & voices…", type="ongoing", timeout=0)
                await run.io_bound(tts.download_model)
                ui.notify("✅ Kokoro TTS installed!", type="positive")
                _reopen("Voice")

            ui.button("⬇️ Install Kokoro TTS", on_click=_install_kokoro).classes("w-full")
        else:
            ui.switch("Enable text-to-speech", value=tts.enabled,
                      on_change=lambda e: setattr(tts, "enabled", e.value))

            voice_opts = {v: VOICE_CATALOG.get(v, v) for v in tts.get_installed_voices()}
            if voice_opts:
                ui.select(label="Voice", options=voice_opts, value=tts.voice,
                          on_change=lambda e: setattr(tts, "voice", e.value)).classes("w-full")

            ui.label("Speech speed").classes("text-sm")
            ui.slider(
                min=0.5, max=2.0, step=0.1, value=tts.speed,
                on_change=lambda e: setattr(tts, "speed", e.value),
            ).classes("w-full")

            ui.switch("Auto-speak voice responses", value=tts.auto_speak,
                      on_change=lambda e: setattr(tts, "auto_speak", e.value))

            def _test():
                tts.speak_now("Hello! I'm Thoth, your knowledgeable personal agent.")

            ui.button("🔊 Test voice", on_click=_test).props("flat")

    # ── Channels Tab ─────────────────────────────────────────────────

    def _build_channels_tab() -> None:
        from channels.telegram import is_configured as tg_configured, is_running as tg_running
        from channels.telegram import start_bot as _tg_start_bot, stop_bot as _tg_stop_bot
        from channels.email import (
            is_configured as email_configured,
            is_running as email_running,
            get_last_error as email_last_error,
            start_polling as _email_start,
            stop_polling as _email_stop,
            get_poll_interval as _email_poll_interval,
            set_poll_interval as _email_set_poll_interval,
        )
        from channels import config as _ch_config

        ui.label("📱 Messaging Channels").classes("text-h6")
        ui.label("Connect Thoth to external messaging platforms.").classes("text-grey-6 text-sm")

        ui.separator()

        # ── Telegram ────────────────────────────────────────────────
        ui.label("Telegram Bot").classes("text-h6")
        ui.label("Chat with Thoth from Telegram using a personal bot.").classes("text-grey-6 text-sm")

        with ui.expansion("📖 Setup Guide", icon="help_outline").classes("w-full"):
            ui.markdown(
                "### Quick Setup\n"
                "1. Message [@BotFather](https://t.me/BotFather) → `/newbot`\n"
                "2. Copy the **Bot Token**\n"
                "3. Message [@userinfobot](https://t.me/userinfobot) for your **User ID**\n"
                "4. Paste both below and click **Save**\n"
                "5. Click **▶️ Start Bot**",
                extras=['code-friendly', 'fenced-code-blocks', 'tables'],
            ).classes("text-sm")

        ui.separator()

        tg_token = get_key("TELEGRAM_BOT_TOKEN")
        tg_user_id = get_key("TELEGRAM_USER_ID")

        token_input = ui.input(
            label="Bot Token", value=tg_token,
            password=True, password_toggle_button=True,
        ).classes("w-full")

        user_id_input = ui.input(
            label="Your Telegram User ID", value=tg_user_id,
        ).classes("w-full")

        status_container = ui.row().classes("items-center gap-2 mt-2")
        _update_tg_status(status_container, tg_configured, tg_running)

        def _save_tg_creds():
            set_key("TELEGRAM_BOT_TOKEN", token_input.value.strip())
            set_key("TELEGRAM_USER_ID", user_id_input.value.strip())
            _update_tg_status(status_container, tg_configured, tg_running)
            ui.notify("Telegram credentials saved", type="positive")

        ui.button("💾 Save", on_click=_save_tg_creds).classes("mt-2")

        ui.separator()
        ui.label("Bot Control").classes("text-subtitle2 mt-2")

        async def _start_tg():
            if not tg_configured():
                ui.notify("Please save your credentials first", type="warning")
                return
            try:
                ok = await _tg_start_bot()
                if ok:
                    _ch_config.set("telegram", "auto_start", True)
                    ui.notify("✅ Telegram bot started!", type="positive")
                else:
                    ui.notify("⚠️ Could not start — check credentials", type="warning")
            except Exception as exc:
                ui.notify(f"Error starting bot: {exc}", type="negative")
            _update_tg_status(status_container, tg_configured, tg_running)

        async def _stop_tg():
            try:
                await _tg_stop_bot()
                _ch_config.set("telegram", "auto_start", False)
                ui.notify("Telegram bot stopped", type="info")
            except Exception as exc:
                ui.notify(f"Error stopping bot: {exc}", type="negative")
            _update_tg_status(status_container, tg_configured, tg_running)

        with ui.row().classes("gap-2"):
            ui.button("▶️ Start Bot", on_click=_start_tg).props("color=positive")
            ui.button("⏹️ Stop Bot", on_click=_stop_tg).props("color=negative flat")

        # Telegram outbound tool
        tg_tool = tool_registry.get_tool("telegram")
        if tg_tool:
            ui.separator()
            ui.label("Outbound Messaging").classes("text-subtitle2 mt-2")
            ui.switch(
                "Enable Telegram tool",
                value=tool_registry.is_enabled("telegram"),
                on_change=lambda e: (
                    tool_registry.set_enabled("telegram", e.value),
                    clear_agent_cache(),
                ),
            ).tooltip(tg_tool.description)

        ui.separator().classes("mt-6")

        # ── Email ────────────────────────────────────────────────────
        ui.label("📧 Email Channel").classes("text-h6")
        ui.label("Send an email with [Thoth] in the subject line to run a query.").classes("text-grey-6 text-sm")

        with ui.expansion("📖 Setup Guide", icon="help_outline").classes("w-full"):
            ui.markdown(
                "### Quick Setup\n"
                "1. Enable **Gmail** tool and complete OAuth sign-in\n"
                "2. Click **▶️ Start Polling**\n"
                "3. Send yourself an email with `[Thoth]` in the subject",
                extras=['code-friendly', 'fenced-code-blocks', 'tables'],
            ).classes("text-sm")

        ui.separator()

        email_status_container = ui.row().classes("items-center gap-2 mt-2")
        _update_email_status(email_status_container, email_configured, email_running, email_last_error)

        current_interval = _email_poll_interval()
        interval_label = ui.label(f"Poll interval: {current_interval}s").classes("text-sm mt-2")

        def _on_interval_change(e):
            val = int(e.value)
            _email_set_poll_interval(val)
            interval_label.text = f"Poll interval: {val}s"

        ui.slider(
            min=10, max=300, step=10, value=current_interval,
            on_change=_on_interval_change
        ).classes("w-full")

        ui.separator()
        ui.label("Email Control").classes("text-subtitle2 mt-2")

        async def _start_email():
            if not email_configured():
                ui.notify("Gmail OAuth not set up — enable the Gmail tool first", type="warning")
                return
            try:
                ok = await _email_start()
                if ok:
                    _ch_config.set("email", "auto_start", True)
                    ui.notify("✅ Email polling started!", type="positive")
                else:
                    ui.notify("⚠️ Could not start — check Gmail OAuth", type="warning")
            except Exception as exc:
                ui.notify(f"Error: {exc}", type="negative")
            _update_email_status(email_status_container, email_configured, email_running, email_last_error)

        async def _stop_email():
            try:
                await _email_stop()
                _ch_config.set("email", "auto_start", False)
                ui.notify("Email polling stopped", type="info")
            except Exception as exc:
                ui.notify(f"Error: {exc}", type="negative")
            _update_email_status(email_status_container, email_configured, email_running, email_last_error)

        with ui.row().classes("gap-2"):
            ui.button("▶️ Start Polling", on_click=_start_email).props("color=positive")
            ui.button("⏹️ Stop Polling", on_click=_stop_email).props("color=negative flat")

    # ══════════════════════════════════════════════════════════════════
    # STATUS HELPERS (used by Channels tab)
    # ══════════════════════════════════════════════════════════════════

    def _update_tg_status(container, tg_configured, tg_running):
        container.clear()
        with container:
            if tg_running():
                ui.icon("check_circle", color="green").classes("text-lg")
                ui.label("Bot running — polling for messages").classes("text-green text-sm")
            elif tg_configured():
                ui.icon("pause_circle", color="blue").classes("text-lg")
                ui.label("Configured — click Start to begin").classes("text-blue text-sm")
            else:
                ui.icon("warning", color="orange").classes("text-lg")
                ui.label("Not configured").classes("text-orange text-sm")

    def _update_email_status(container, email_configured, email_running, email_last_error):
        container.clear()
        with container:
            last_err = email_last_error()
            if last_err:
                ui.icon("error", color="red").classes("text-lg")
                ui.label(last_err).classes("text-red text-sm")
            elif email_running():
                ui.icon("check_circle", color="green").classes("text-lg")
                ui.label("Polling — checking for [Thoth] emails").classes("text-green text-sm")
            elif email_configured():
                ui.icon("pause_circle", color="blue").classes("text-lg")
                ui.label("Gmail OAuth ready — click Start").classes("text-blue text-sm")
            else:
                ui.icon("warning", color="orange").classes("text-lg")
                ui.label("Gmail OAuth not set up").classes("text-orange text-sm")

    # ══════════════════════════════════════════════════════════════════
    # DIALOG SHELL
    # ══════════════════════════════════════════════════════════════════

    p.settings_dlg.clear()
    with p.settings_dlg:
        with ui.card().classes("w-full h-full no-shadow").style(
            "max-width: 64rem; margin: 0 auto;"
        ):
            with ui.row().classes("w-full items-center justify-between px-4 pt-3 pb-1"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("settings", size="sm")
                    ui.label("Settings").classes("text-h5")
                ui.button(icon="close", on_click=p.settings_dlg.close).props("flat round size=sm")

            ui.separator()

            _tab_map = {}
            with ui.splitter(value=18).classes("w-full flex-grow").props(
                "disable"
            ).style("height: calc(100vh - 100px);") as splitter:
                with splitter.before:
                    with ui.tabs().props("vertical").classes("w-full h-full") as tabs:
                        tab_models = ui.tab("Models", icon="smart_toy")
                        tab_cloud = ui.tab("Cloud", icon="cloud")
                        tab_mem = ui.tab("Memory", icon="psychology")
                        tab_voice = ui.tab("Voice", icon="mic")
                        tab_fs = ui.tab("System", icon="terminal")
                        tab_tracker = ui.tab("Tracker", icon="checklist")
                        tab_docs = ui.tab("Documents", icon="description")
                        tab_tools = ui.tab("Search", icon="search")
                        tab_skills = ui.tab("Skills", icon="auto_fix_high")
                        tab_gmail = ui.tab("Gmail", icon="email")
                        tab_cal = ui.tab("Calendar", icon="event")
                        tab_channels = ui.tab("Channels", icon="forum")
                        tab_utils = ui.tab("Utilities", icon="build")
                        _tab_map = {
                            "Models": tab_models, "Cloud": tab_cloud,
                            "Memory": tab_mem, "Voice": tab_voice,
                            "System": tab_fs, "Tracker": tab_tracker,
                            "Documents": tab_docs, "Search": tab_tools,
                            "Skills": tab_skills,
                            "Gmail": tab_gmail, "Calendar": tab_cal,
                            "Channels": tab_channels, "Utilities": tab_utils,
                        }

                _initial = _tab_map.get(initial_tab, tab_models)
                with splitter.after:
                    with ui.tab_panels(tabs, value=_initial).classes("w-full h-full"):
                        with ui.tab_panel(tab_docs).classes("px-6 py-4"):
                            _build_documents_tab()
                        with ui.tab_panel(tab_models).classes("px-6 py-4"):
                            _build_models_tab()
                        with ui.tab_panel(tab_cloud).classes("px-6 py-4"):
                            _build_cloud_tab()
                        with ui.tab_panel(tab_tools).classes("px-6 py-4"):
                            _build_tools_tab()
                        with ui.tab_panel(tab_skills).classes("px-6 py-4"):
                            _build_skills_tab()
                        with ui.tab_panel(tab_fs).classes("px-6 py-4"):
                            _build_system_access_tab()
                        with ui.tab_panel(tab_gmail).classes("px-6 py-4"):
                            _build_gmail_tab()
                        with ui.tab_panel(tab_cal).classes("px-6 py-4"):
                            _build_calendar_tab()
                        with ui.tab_panel(tab_utils).classes("px-6 py-4"):
                            _build_utilities_tab()
                        with ui.tab_panel(tab_tracker).classes("px-6 py-4"):
                            _build_tracker_tab()
                        with ui.tab_panel(tab_mem).classes("px-6 py-4"):
                            _build_memory_tab()
                        with ui.tab_panel(tab_voice).classes("px-6 py-4"):
                            _build_voice_tab()
                        with ui.tab_panel(tab_channels).classes("px-6 py-4"):
                            _build_channels_tab()

    p.settings_dlg.open()
