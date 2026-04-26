# core/template.py
# VoidSend - Email template engine

from pathlib import Path
from typing import Optional
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, Undefined


class SilentUndefined(Undefined):
    """Render missing template variables as empty string instead of erroring."""
    def __str__(self):
        return ""
    def __call__(self, *args, **kwargs):
        return ""


_env = Environment(
    loader=BaseLoader(),
    autoescape=False,
    undefined=SilentUndefined,
)

UNSUBSCRIBE_FOOTER_HTML = """
<br><br>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="font-size:11px;color:#999;text-align:center;">
  You are receiving this email because you subscribed to this newsletter.<br>
  To unsubscribe, reply with "UNSUBSCRIBE" in the subject line.
</p>
"""

UNSUBSCRIBE_FOOTER_TEXT = (
    "\n\n---\n"
    "You are receiving this email because you subscribed to this newsletter.\n"
    "To unsubscribe, reply with 'UNSUBSCRIBE' in the subject line.\n"
)


def render_template(template_str: str, variables: dict) -> str:
    """Render a Jinja2 template string with given variables."""
    try:
        tmpl = _env.from_string(template_str)
        return tmpl.render(**variables)
    except TemplateSyntaxError as e:
        raise ValueError(f"Template syntax error at line {e.lineno}: {e.message}")


def load_template_file(path: str | Path) -> str:
    """Load a template file from disk."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Template file not found: {path}")
    return path.read_text(encoding="utf-8")


def render_email(
    html_template: str,
    subject_template: str,
    variables: dict,
    append_unsubscribe: bool = True,
    plain_text_template: Optional[str] = None,
) -> dict:
    """
    Render a full email — subject, html body, optional plain text.
    Returns dict with keys: subject, html, text
    """
    subject = render_template(subject_template, variables)
    html = render_template(html_template, variables)

    if append_unsubscribe:
        html += UNSUBSCRIBE_FOOTER_HTML

    text = None
    if plain_text_template:
        text = render_template(plain_text_template, variables)
        if append_unsubscribe:
            text += UNSUBSCRIBE_FOOTER_TEXT

    return {"subject": subject, "html": html, "text": text}


def extract_variables(template_str: str) -> list[str]:
    """Return list of variable names used in a template string."""
    from jinja2 import Environment, meta
    env = Environment()
    try:
        ast = env.parse(template_str)
        return sorted(meta.find_undeclared_variables(ast))
    except TemplateSyntaxError:
        return []


def validate_template_vars(
    template_str: str,
    available_vars: set[str],
) -> list[str]:
    """Return variables used in template that are missing from available_vars."""
    used = set(extract_variables(template_str))
    return sorted(used - available_vars)
