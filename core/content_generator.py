# ui/content_screen.py
# VoidSend - Content generator TUI screen

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer, Input,
    Label, Static, Select, TextArea
)
from typing import Optional, Callable
from core.content_generator import (
    ContentFields, render_content, save_to_library,
    LAYOUT_CHOICES, GeneratedContent
)


class ContentScreen(Screen):

    BINDINGS = [
        Binding("escape",  "cancel",       "Cancel"),
        Binding("ctrl+p",  "preview",      "Preview"),
        Binding("ctrl+s",  "save_library", "Save to Library"),
    ]

    def __init__(
        self,
        on_complete: Optional[Callable[[ContentFields, GeneratedContent], None]] = None,
        prefill: Optional[ContentFields] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.on_complete = on_complete
        self.prefill = prefill or ContentFields()

    def compose(self) -> ComposeResult:
        layout_options = [(label, key) for key, label, _ in LAYOUT_CHOICES]

        yield Header()
        yield Container(
            Static("✏  Build Email Content", id="content_title"),
            ScrollableContainer(
                Static("── Layout ─────────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Layout Style"),
                        Select(
                            options=layout_options,
                            id="layout_select",
                            value=self.prefill.layout,
                        ),
                    ),
                    Vertical(
                        Label(""),
                        Static("", id="layout_desc"),
                    ),
                    id="layout_row",
                ),
                Static("── Branding ───────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Brand / Sender Name"),
                        Input(
                            placeholder="e.g. Acme Newsletter",
                            id="brand_name",
                            value=self.prefill.brand_name,
                        ),
                    ),
                    Vertical(
                        Label("Brand Color (hex)"),
                        Input(
                            placeholder="#2563eb",
                            id="brand_color",
                            value=self.prefill.brand_color or "#2563eb",
                        ),
                    ),
                    id="brand_row",
                ),
                Horizontal(
                    Vertical(
                        Label("Tagline (Newsletter layout)"),
                        Input(
                            placeholder="Your weekly dose of updates",
                            id="tagline",
                            value=self.prefill.tagline,
                        ),
                    ),
                    Vertical(
                        Label("Logo URL (optional)"),
                        Input(
                            placeholder="https://yourdomain.com/logo.png",
                            id="logo_url",
                            value=self.prefill.logo_url,
                        ),
                    ),
                    id="brand_row2",
                ),
                Static("── Content ────────────────────────────────", classes="section_sep"),
                Label("Email Subject Line"),
                Input(
                    placeholder="e.g. Hello {{name}}, here's your August update!",
                    id="subject",
                    value=self.prefill.subject,
                ),
                Label("Headline"),
                Input(
                    placeholder="e.g. Big news this month",
                    id="headline",
                    value=self.prefill.headline,
                ),
                Label("Intro / Subheadline"),
                Input(
                    placeholder="e.g. Here's what we've been working on...",
                    id="intro",
                    value=self.prefill.intro,
                ),
                Label("Body Text"),
                TextArea(
                    text=self.prefill.body_text,
                    id="body_text",
                ),
                Static("── Promotional (optional) ─────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Offer Text"),
                        Input(
                            placeholder="e.g. 30% OFF all plans",
                            id="offer_text",
                            value=self.prefill.offer_text,
                        ),
                    ),
                    Vertical(
                        Label("Urgency Text"),
                        Input(
                            placeholder="e.g. Offer ends Friday",
                            id="urgency_text",
                            value=self.prefill.urgency_text,
                        ),
                    ),
                    id="promo_row",
                ),
                Static("── Call to Action ──────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Button Label"),
                        Input(
                            placeholder="e.g. Read More",
                            id="cta_label",
                            value=self.prefill.cta_label,
                        ),
                    ),
                    Vertical(
                        Label("Button URL"),
                        Input(
                            placeholder="https://yourdomain.com/article",
                            id="cta_url",
                            value=self.prefill.cta_url,
                        ),
                    ),
                    id="cta_row",
                ),
                Static("── Footer ──────────────────────────────────", classes="section_sep"),
                Label("Footer Note"),
                Input(
                    placeholder="e.g. © 2026 Acme Inc. All rights reserved.",
                    id="footer_note",
                    value=self.prefill.footer_note,
                ),
                Static("── Library ─────────────────────────────────", classes="section_sep"),
                Label("Template Name (required to save to library)"),
                Input(
                    placeholder="e.g. August Newsletter Base",
                    id="template_name",
                    value=self.prefill.template_name,
                ),
                Static("", id="status_msg"),
                id="form_scroll",
            ),
            Horizontal(
                Button("Preview [Ctrl+P]",     id="btn_preview", variant="default"),
                Button("Save to Library [^S]", id="btn_library", variant="default"),
                Button("✓ Use This Content",   id="btn_use",     variant="success"),
                Button("Cancel [ESC]",         id="btn_cancel",  variant="error"),
                id="content_actions",
            ),
            id="content_container",
        )
        yield Footer()

    def on_mount(self):
        self._update_layout_desc(self.prefill.layout)

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "layout_select":
            self._update_layout_desc(str(event.value))

    def _update_layout_desc(self, key: str):
        desc = next((d for k, _, d in LAYOUT_CHOICES if k == key), "")
        self.query_one("#layout_desc", Static).update(f"[dim]{desc}[/dim]")

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#status_msg", Static).update(f"[{color}]{msg}[/{color}]")

    def _collect_fields(self) -> ContentFields:
        def val(id_: str) -> str:
            try:
                w = self.query_one(f"#{id_}")
                if hasattr(w, "text"):
                    return w.text.strip()
                return w.value.strip()
            except Exception:
                return ""

        return ContentFields(
            layout        = str(self.query_one("#layout_select", Select).value),
            subject       = val("subject"),
            headline      = val("headline"),
            intro         = val("intro"),
            body_text     = val("body_text"),
            brand_name    = val("brand_name"),
            brand_color   = val("brand_color") or "#2563eb",
            tagline       = val("tagline"),
            logo_url      = val("logo_url"),
            cta_label     = val("cta_label"),
            cta_url       = val("cta_url"),
            offer_text    = val("offer_text"),
            urgency_text  = val("urgency_text"),
            footer_note   = val("footer_note"),
            template_name = val("template_name"),
        )

    def _validate(self, fields: ContentFields) -> list[str]:
        errors = []
        if not fields.headline:
            errors.append("Headline is required")
        if not fields.subject:
            errors.append("Subject line is required")
        if fields.brand_color and not fields.brand_color.startswith("#"):
            errors.append("Brand color must be hex e.g. #2563eb")
        return errors

    def action_preview(self):
        self._do_preview()

    def action_save_library(self):
        self._do_save_library()

    def _do_preview(self):
        fields = self._collect_fields()
        errors = self._validate(fields)
        if errors:
            self._set_status("✗ " + " | ".join(errors), "red")
            return
        try:
            generated    = render_content(fields)
            preview_path = Path.home() / ".voidsend" / "preview.html"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(generated.html, encoding="utf-8")
            self._set_status(
                f"✓ Preview saved → {preview_path}  (open in browser)",
                "green"
            )
        except Exception as e:
            self._set_status(f"✗ Preview error: {e}", "red")

    def _do_save_library(self):
        fields = self._collect_fields()
        if not fields.template_name:
            self._set_status("✗ Enter a Template Name to save", "yellow")
            return
        errors = self._validate(fields)
        if errors:
            self._set_status("✗ " + " | ".join(errors), "red")
            return
        try:
            save_to_library(fields)
            self._set_status(f"✓ Saved: {fields.template_name}", "green")
        except Exception as e:
            self._set_status(f"✗ Save error: {e}", "red")

    def _do_use(self):
        fields = self._collect_fields()
        errors = self._validate(fields)
        if errors:
            self._set_status("✗ " + " | ".join(errors), "red")
            return
        try:
            generated = render_content(fields)
            if self.on_complete:
                self.on_complete(fields, generated)
            self.app.pop_screen()
        except Exception as e:
            self._set_status(f"✗ Render error: {e}", "red")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_preview":
            self._do_preview()
        elif event.button.id == "btn_library":
            self._do_save_library()
        elif event.button.id == "btn_use":
            self._do_use()
        elif event.button.id == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
