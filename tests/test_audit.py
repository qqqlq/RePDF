from repdf.audit import find_suspicious_items
from repdf.models import TextItem


def make_item(text, bbox):
    return TextItem(text=text, bbox=bbox, confidence=None)


def test_extract_item_with_matching_ocr_is_not_suspicious():
    extract_items = [make_item("Hello", (10, 10, 50, 20))]
    ocr_items = [make_item("Hello", (10, 10, 50, 20))]
    assert find_suspicious_items(extract_items, ocr_items) == []


def test_extract_item_with_no_ocr_overlap_is_suspicious():
    extract_items = [make_item("Secret", (10, 10, 50, 20))]
    ocr_items = [make_item("Other", (100, 100, 150, 110))]
    result = find_suspicious_items(extract_items, ocr_items)
    assert len(result) == 1
    assert result[0].text == "Secret"
    assert result[0].reason == "not_detected_by_ocr"


def test_partial_overlap_counts_as_matched():
    extract_items = [make_item("Line", (10, 10, 100, 20))]
    ocr_items = [make_item("Li", (10, 10, 40, 20)), make_item("ne", (40, 10, 100, 20))]
    assert find_suspicious_items(extract_items, ocr_items) == []


def test_empty_extract_items_returns_empty():
    ocr_items = [make_item("Hello", (10, 10, 50, 20))]
    assert find_suspicious_items([], ocr_items) == []


def test_empty_ocr_items_flags_all_extract_items():
    extract_items = [
        make_item("A", (10, 10, 20, 20)),
        make_item("B", (30, 30, 40, 40)),
    ]
    result = find_suspicious_items(extract_items, [])
    assert {item.text for item in result} == {"A", "B"}
