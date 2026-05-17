from app.modules.playbook.services.publish_renderer import render_markdown


class TestRenderMarkdown:
    def test_basic_paragraph(self) -> None:
        result = render_markdown("Hello world")
        assert result == "<p>Hello world</p>"

    def test_heading(self) -> None:
        result = render_markdown("## Section Title")
        assert result == "<h2>Section Title</h2>"

    def test_bold(self) -> None:
        result = render_markdown("**bold text**")
        assert "<strong>bold text</strong>" in result

    def test_italic(self) -> None:
        result = render_markdown("*italic text*")
        assert "<em>italic text</em>" in result

    def test_single_newline_produces_break(self) -> None:
        result = render_markdown("line one\nline two")
        assert "<br" in result

    def test_unordered_list(self) -> None:
        result = render_markdown("- item one\n- item two")
        assert "<ul>" in result
        assert "<li>" in result

    def test_link(self) -> None:
        result = render_markdown("[click](https://example.com)")
        assert "href=" in result

    def test_image(self) -> None:
        result = render_markdown("![alt](https://example.com/img.png)")
        assert "<img src=" in result

    def test_code_block(self) -> None:
        result = render_markdown("```\nprint('hi')\n```")
        assert "<code>" in result

    def test_inline_code(self) -> None:
        result = render_markdown("`foo()`")
        assert "<code>foo()</code>" in result

    def test_blockquote(self) -> None:
        result = render_markdown("> wise words")
        assert "<blockquote>" in result

    def test_linkify_bare_url(self) -> None:
        result = render_markdown("Visit https://vizzuality.com today")
        assert 'href="https://vizzuality.com"' in result

    def test_empty_input(self) -> None:
        assert render_markdown("") == ""

    def test_none_input(self) -> None:
        assert render_markdown(None) == ""
