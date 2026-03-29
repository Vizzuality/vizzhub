from markdown_it import MarkdownIt


def _create_renderer() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"breaks": True, "linkify": True})
    md.enable("linkify")
    return md


_md = _create_renderer()


def render_markdown(source: str | None) -> str:
    if not source:
        return ""
    return _md.render(source).strip()
