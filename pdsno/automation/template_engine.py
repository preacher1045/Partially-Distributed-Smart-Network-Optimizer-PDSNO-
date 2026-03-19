"""
Template Engine

Manages Jinja2 template rendering with proper inheritance support.

Two modes:
    1. Direct render  — render a template file with variables
    2. Extended render — a user template extends a base template using
    3.Jinja2's native {% extends %} / {% block %} system

Directory layout expected:
    templates_dir/
        base_config.j2         ← base templates (define {% block %} regions)
        policy.j2
        ...
    custom_templates_dir/
    user_alex_vlans.j2 ← user templates (use {% extends "base_config.j2" %})
    ...
"""

import yaml
from typing import Dict, Optional, Any
from pathlib import Path
import logging
from jinja2 import (
    Environment,
    FileSystemLoader,
    ChoiceLoader,
    StrictUndefined,
    TemplateNotFound,
    TemplateSyntaxError,
    UndefinedError,
)


class TemplateRenderError(Exception):
    """Raised when a template cannot be rendered."""
    pass


class TemplateEngine:
    """
    Render Jinja2 templates with inheritance support.

    Base templates live in templates_dir and define {% block %} regions.
    User templates live in custom_templates_dir and can use
    {% extends "base_config.j2" %} to inherit and override those regions.

    Both directories are on the Jinja2 search path, so a user template
    can extend any base template by name without specifying a path.
    """

    def __init__(
        self,
        templates_dir: str = "pdsno/automation/core/templates",
        custom_templates_dir: str = "pdsno/automation/custom/templates",
    ):
        self.templates_dir = Path(templates_dir)
        self.custom_templates_dir = Path(custom_templates_dir)
        self.logger = logging.getLogger(__name__)

        # Validate directories exist — warn but don't crash if custom dir is missing
        if not self.templates_dir.exists():
            raise FileNotFoundError(
                f"Core templates directory not found: {self.templates_dir}"
            )
        if not self.custom_templates_dir.exists():
            self.logger.warning(
                f"Custom templates directory not found: {self.custom_templates_dir}. "
                f"User templates will not be available."
            )

        # Build a Jinja2 Environment with both directories on the search path.
        # ChoiceLoader tries loaders in order — custom first so users can
        # shadow a core template by name if they deliberately want to.
        loaders = [FileSystemLoader(str(self.templates_dir))]
        if self.custom_templates_dir.exists():
            loaders = [
                FileSystemLoader(str(self.custom_templates_dir)),
                FileSystemLoader(str(self.templates_dir)),
            ]

        self.env = Environment(
            loader=ChoiceLoader(loaders),
            # StrictUndefined turns a missing variable into an error rather
            # than silently rendering as an empty string. This catches typos
            # in variable names at render time rather than producing silent
            # misconfiguration — critical for network config templates.
            undefined=StrictUndefined,
            # Keep newlines from {% block %} tags clean
            trim_blocks=True,
            lstrip_blocks=True,
            # Don't auto-escape — these are network config files, not HTML
            autoescape=False,
            keep_trailing_newline=True,
        )

        self.logger.info(
            f"TemplateEngine initialised. "
            f"Core: {self.templates_dir}, "
            f"Custom: {self.custom_templates_dir}"
        )

    def render(
        self,
        template_name: str,
        variables: Dict[str, Any],
    ) -> str:
        """
        Render a template by name with the given variables.

        Works for both base templates and user templates. If the template
        contains {% extends %}, Jinja2 handles the inheritance automatically.

        Args:
            template_name: Filename of the template (e.g. "base_config.j2"
            or "user_alex_vlans.j2"). No path prefix needed.
            variables: Dict of variables available inside the template.

        Returns:
            Rendered string ready to be applied to a device.

        Raises:
            TemplateRenderError: If the template is not found, has a syntax
            error, or references an undefined variable.
        """
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            raise TemplateRenderError(
                f"Template not found: '{template_name}'. "
                f"Check core templates in {self.templates_dir} and "
                f"custom templates in {self.custom_templates_dir}."
            )
        except TemplateSyntaxError as e:
            raise TemplateRenderError(
                f"Syntax error in template '{template_name}' "
                f"at line {e.lineno}: {e.message}"
            )

        try:
            return template.render(**variables)
        except UndefinedError as e:
            raise TemplateRenderError(
                f"Undefined variable in template '{template_name}': {e}. "
                f"Check that all required variables are passed to render()."
            )
        except Exception as e:
            raise TemplateRenderError(
                f"Failed to render template '{template_name}': {e}"
            )

    def render_to_playbook_tasks(
        self,
        template_name: str,
        variables: Dict[str, Any],
    ) -> list:
        """
        Render a template and parse the result as YAML task list.

        Use this when the template produces a list of Ansible tasks
        rather than raw device CLI config.

        Returns:
            Parsed list of Ansible task dicts.

        Raises:
            TemplateRenderError: If render fails or result is not valid YAML.
        """
        rendered = self.render(template_name, variables)
        try:
            result = yaml.safe_load(rendered)
        except yaml.YAMLError as e:
            raise TemplateRenderError(
                f"Template '{template_name}' rendered successfully but the "
                f"output is not valid YAML: {e}"
            )
        if not isinstance(result, list):
            raise TemplateRenderError(
                f"Template '{template_name}' must render to a YAML list of "
                f"tasks, got {type(result).__name__}."
            )
        return result

    def list_templates(self, custom_only: bool = False) -> list[str]:
        """
        List available template names.

        Args:
            custom_only: If True, only return templates from custom_templates_dir.
        """
        if custom_only:
            if not self.custom_templates_dir.exists():
                return []
            return sorted(
                p.name for p in self.custom_templates_dir.glob("*.j2")
            )
        # env.list_templates() returns all templates the loader can find
        return sorted(self.env.list_templates())

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists without rendering it."""
        try:
            self.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False

    def validate_template(self, template_name: str) -> tuple[bool, Optional[str]]:
        """
        Parse a template for syntax errors without rendering it.

        Returns:
            (valid, error_message) — error_message is None if valid.
        """
        try:
            self.env.get_template(template_name)
            return True, None
        except TemplateNotFound:
            return False, f"Template not found: '{template_name}'"
        except TemplateSyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.message}"

    # ------------------------------------------------------------------
    # Kept for backwards compatibility — will be removed in Phase 8
    # ------------------------------------------------------------------

    def extend_template(self, base_template: str, custom_content: str) -> str:
        """
        Deprecated. Use render() with {% extends %} in the template instead.

        Previously this concatenated two YAML playbook lists. That approach
        did not support variable passing, block overriding, or any real
        template inheritance. It is retained here so existing callers do not
        break, but it will be removed once callers are migrated.

        Migration path:
            Old: engine.extend_template("base_config", custom_yaml_string)
            New: engine.render("user_alice_custom.j2", variables)
            where user_alice_custom.j2 uses {% extends "base_config.j2" %}
        """
        self.logger.warning(
            "extend_template() is deprecated and will be removed in Phase 8. "
            "Use render() with Jinja2 {% extends %} inheritance instead."
        )
        try:
            base = yaml.safe_load(
                self.env.get_source(self.env, base_template + ".j2")[0]
                if not base_template.endswith(".j2")
                else self.env.get_source(self.env, base_template)[0]
            )
        except Exception:
            # Fall back to old behaviour if the new loader can't find it
            base = yaml.safe_load(
                self._load_raw(base_template)
            )

        custom = yaml.safe_load(custom_content)
        if not isinstance(base, list):
            base = []
        if not isinstance(custom, list):
            custom = []
        merged = base + custom
        return yaml.dump(merged, default_flow_style=False)

    def _load_raw(self, template_name: str) -> str:
        """Load template source as raw string. Used only by deprecated method."""
        for directory in [self.custom_templates_dir, self.templates_dir]:
            candidate = directory / (template_name + ".j2")
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
            candidate = directory / template_name
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        return ""