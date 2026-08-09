from repdf.markdown import items_to_markdown, pages_to_markdown
from repdf.models import TextItem


def test_empty_items_returns_empty_string():
    assert items_to_markdown([]) == ""


def test_single_item():
    items = [TextItem(text="Hello", bbox=(10, 10, 50, 20), confidence=None)]
    assert items_to_markdown(items) == "Hello"


def test_words_on_same_line_are_joined_left_to_right():
    items = [
        TextItem(text="World", bbox=(60, 10, 100, 20), confidence=None),
        TextItem(text="Hello", bbox=(10, 10, 50, 20), confidence=None),
    ]
    assert items_to_markdown(items) == "Hello World"


def test_items_on_different_lines_produce_multiple_lines():
    items = [
        TextItem(text="Line2", bbox=(10, 50, 50, 60), confidence=None),
        TextItem(text="Line1", bbox=(10, 10, 50, 20), confidence=None),
    ]
    assert items_to_markdown(items) == "Line1\nLine2"


def test_items_within_y_tolerance_are_same_line():
    items = [
        TextItem(text="A", bbox=(10, 10.0, 20, 20), confidence=None),
        TextItem(text="B", bbox=(30, 11.5, 40, 21.5), confidence=None),  # 1.5pt差、閾値3.0以内
    ]
    assert items_to_markdown(items) == "A B"


def test_items_beyond_y_tolerance_are_different_lines():
    items = [
        TextItem(text="A", bbox=(10, 10.0, 20, 20), confidence=None),
        TextItem(text="B", bbox=(30, 20.0, 40, 30), confidence=None),  # 10pt差
    ]
    assert items_to_markdown(items) == "A\nB"


def test_pages_to_markdown_joins_with_separator():
    page1 = [TextItem(text="Page1", bbox=(10, 10, 50, 20), confidence=None)]
    page2 = [TextItem(text="Page2", bbox=(10, 10, 50, 20), confidence=None)]
    result = pages_to_markdown([page1, page2])
    assert result == "Page1\n\n---\n\nPage2"


def test_pages_to_markdown_handles_empty_page():
    page1 = [TextItem(text="Page1", bbox=(10, 10, 50, 20), confidence=None)]
    result = pages_to_markdown([page1, []])
    assert result == "Page1\n\n---\n\n"
