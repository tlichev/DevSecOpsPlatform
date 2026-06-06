import logging
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

logger = logging.getLogger(__name__)

# Jinja2 environment with strict undefined — any missing variable raises immediately
_jinja_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,  # config text, not HTML
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(template_body: str, variables: dict) -> str:
    try:
        tmpl = _jinja_env.from_string(template_body)
        return tmpl.render(**variables)
    except TemplateSyntaxError as exc:
        raise ValueError(f"Template syntax error at line {exc.lineno}: {exc.message}") from exc
    except UndefinedError as exc:
        raise ValueError(f"Missing variable in template: {exc}") from exc
