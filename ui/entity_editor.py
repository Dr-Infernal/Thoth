"""Thoth UI — in-app entity editor dialog.

Quasar dialog for editing knowledge graph entities: subject, type,
description, aliases, tags, and relations.
"""

from __future__ import annotations

import logging

from nicegui import ui

logger = logging.getLogger(__name__)


def open_entity_editor(
    entity_id: str,
    *,
    on_saved: callable | None = None,
) -> None:
    """Open a modal dialog to edit the entity with *entity_id*.

    Parameters
    ----------
    entity_id : str
        Hex ID of the entity to edit.
    on_saved : callable, optional
        Called (no args) after a successful save so the caller can refresh.
    """
    import knowledge_graph as kg

    entity = kg.get_entity(entity_id)
    if not entity:
        ui.notify(f"Entity {entity_id} not found.", type="warning")
        return

    ENTITY_TYPES = sorted(kg.VALID_ENTITY_TYPES)
    RELATION_TYPES = sorted(kg.VALID_RELATION_TYPES)

    with ui.dialog().props("persistent") as dlg, ui.card().classes("w-full").style(
        "min-width: 620px; max-width: 820px; max-height: 90vh;"
    ):
        ui.label("✏️ Edit Entity").classes("text-h6")

        # ── Core fields ──────────────────────────────────────────
        subject_input = ui.input(
            "Subject",
            value=entity.get("subject", ""),
            validation={"Required": lambda v: bool(v.strip())},
        ).classes("w-full")

        type_select = ui.select(
            label="Entity Type",
            options=ENTITY_TYPES,
            value=entity.get("entity_type", "fact"),
        ).classes("w-full")

        desc_input = ui.textarea(
            "Description",
            value=entity.get("description", ""),
        ).classes("w-full").props('rows="5"')

        aliases_input = ui.input(
            "Aliases (comma-separated)",
            value=entity.get("aliases", ""),
        ).classes("w-full")

        tags_input = ui.input(
            "Tags (comma-separated)",
            value=entity.get("tags", ""),
        ).classes("w-full")

        # ── Relations section ────────────────────────────────────
        ui.separator()
        ui.label("🔗 Relations").classes("text-subtitle2 font-bold")

        rels_container = ui.column().classes("w-full gap-1")

        def _refresh_relations():
            rels_container.clear()
            rels = kg.get_relations(entity_id)
            with rels_container:
                if not rels:
                    ui.label("No relations.").classes("text-grey-6 text-sm")
                else:
                    for rel in rels:
                        arrow = "→" if rel["direction"] == "outgoing" else "←"
                        label_text = (
                            f"{arrow} {rel['relation_type']}  "
                            f"{rel['peer_subject']}"
                        )
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.label(label_text).classes(
                                "text-sm flex-grow"
                            ).style("color: #bbb;")
                            conf = rel.get("confidence", 1.0)
                            if conf < 1.0:
                                ui.label(f"{conf:.0%}").classes(
                                    "text-xs text-grey-6"
                                )

                            def _del_rel(rid=rel["id"]):
                                kg.delete_relation(rid)
                                ui.notify("Relation removed.", type="info")
                                _refresh_relations()

                            ui.button(
                                icon="close", on_click=_del_rel
                            ).props("flat dense round size=xs color=negative")

        _refresh_relations()

        # ── Add relation form ────────────────────────────────────
        with ui.expansion("➕ Add Relation").classes("w-full"):
            all_entities = kg.list_entities(limit=500)
            peer_options = {
                e["id"]: e["subject"]
                for e in all_entities
                if e["id"] != entity_id
            }

            peer_select = ui.select(
                label="Target entity",
                options=peer_options,
                with_input=True,
            ).classes("w-full")

            rel_type_select = ui.select(
                label="Relation type",
                options=RELATION_TYPES,
                with_input=True,
                value="knows",
            ).classes("w-full")

            dir_select = ui.select(
                label="Direction",
                options=["outgoing (this → target)", "incoming (target → this)"],
                value="outgoing (this → target)",
            ).classes("w-full")

            def _add_relation():
                peer_id = peer_select.value
                rtype = rel_type_select.value
                if not peer_id or not rtype:
                    ui.notify("Select a target entity and relation type.", type="warning")
                    return
                if "outgoing" in dir_select.value:
                    src, tgt = entity_id, peer_id
                else:
                    src, tgt = peer_id, entity_id
                result = kg.add_relation(src, tgt, rtype)
                if result:
                    ui.notify(f"Relation added: {rtype}", type="positive")
                    peer_select.value = None
                    _refresh_relations()
                else:
                    ui.notify("Failed to add relation.", type="negative")

            ui.button("Add", icon="add", on_click=_add_relation).props(
                "flat dense color=primary"
            )

        # ── Footer buttons ───────────────────────────────────────
        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=dlg.close).props("flat")

            def _save():
                subj = subject_input.value.strip()
                if not subj:
                    ui.notify("Subject is required.", type="warning")
                    return
                desc = desc_input.value.strip()
                updated = kg.update_entity(
                    entity_id,
                    description=desc,
                    subject=subj,
                    entity_type=type_select.value,
                    aliases=aliases_input.value.strip(),
                    tags=tags_input.value.strip(),
                )
                if updated:
                    ui.notify(
                        f"✅ '{subj}' updated.", type="positive"
                    )
                    dlg.close()
                    if on_saved:
                        on_saved()
                else:
                    ui.notify("Update failed.", type="negative")

            ui.button("Save", icon="save", on_click=_save).props("color=primary")

    dlg.open()
