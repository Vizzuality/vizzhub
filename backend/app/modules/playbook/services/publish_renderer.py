from markdown_it import MarkdownIt


def _create_renderer() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"breaks": True, "linkify": True})
    md.enable("linkify")
    return md


_md = _create_renderer()


def render_markdown(source: str | None, strip_leading_h1: bool = False) -> str:
    if not source:
        return ""
    html = _md.render(source).strip()
    if strip_leading_h1 and html.startswith("<h1>"):
        end = html.find("</h1>")
        if end != -1:
            html = html[end + 5:].strip()
    return html
