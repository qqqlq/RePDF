import json

import pymupdf
import pytest

from repdf.cli import load_boxes, main, parse_page_ranges
from repdf.providers import tesseract_available


class TestParsePageRanges:
    def test_single_pages(self):
        assert parse_page_ranges("1,3,5") == {0, 2, 4}

    def test_range(self):
        assert parse_page_ranges("5-7") == {4, 5, 6}

    def test_mixed(self):
        assert parse_page_ranges("3,5-7") == {2, 4, 5, 6}

    def test_empty_string(self):
        assert parse_page_ranges("") == set()

    def test_whitespace_is_trimmed(self):
        assert parse_page_ranges(" 3, 5-7 ") == {2, 4, 5, 6}

    def test_invalid_range_start_greater_than_end_raises(self):
        with pytest.raises(ValueError):
            parse_page_ranges("7-5")

    def test_page_zero_raises(self):
        with pytest.raises(ValueError):
            parse_page_ranges("0")


class TestLoadBoxes:
    def test_loads_and_converts_to_zero_indexed(self, tmp_path):
        path = tmp_path / "boxes.json"
        path.write_text(
            json.dumps({"1": [[0.0, 0.0, 0.5, 0.5]], "3": [[0.1, 0.1, 0.2, 0.2]]}),
            encoding="utf-8",
        )
        boxes = load_boxes(str(path))
        assert boxes == {0: [(0.0, 0.0, 0.5, 0.5)], 2: [(0.1, 0.1, 0.2, 0.2)]}

    def test_page_zero_raises(self, tmp_path):
        path = tmp_path / "boxes.json"
        path.write_text(json.dumps({"0": [[0.0, 0.0, 0.5, 0.5]]}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_boxes(str(path))


class TestMain:
    @pytest.fixture
    def input_pdf(self, tmp_path):
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "Page1 Visible", fontsize=14, render_mode=0)
        doc.new_page().insert_text((72, 72), "Page2 Visible", fontsize=14, render_mode=0)
        path = tmp_path / "input.pdf"
        doc.save(path)
        doc.close()
        return path

    def test_generates_output_pdf(self, input_pdf, tmp_path, capsys):
        output = tmp_path / "output.pdf"
        rc = main(["--dpi", "100", str(input_pdf), "-o", str(output)])
        assert rc == 0
        assert output.exists()
        out_doc = pymupdf.open(output)
        assert len(out_doc) == 2
        out_doc.close()

    def test_remove_option_removes_page(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        rc = main(["--dpi", "100", "--remove", "1", str(input_pdf), "-o", str(output)])
        assert rc == 0
        out_doc = pymupdf.open(output)
        assert len(out_doc) == 1
        assert "Page2 Visible" in out_doc[0].get_text()
        out_doc.close()

    def test_markdown_option_writes_sidecar(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        markdown = tmp_path / "output.md"
        rc = main(
            ["--dpi", "100", "--markdown", str(markdown), str(input_pdf), "-o", str(output)]
        )
        assert rc == 0
        assert markdown.exists()

    def test_nonexistent_input_returns_error_code(self, tmp_path):
        output = tmp_path / "output.pdf"
        rc = main(["--dpi", "100", str(tmp_path / "missing.pdf"), "-o", str(output)])
        assert rc == 1

    def test_invalid_remove_spec_returns_error_code(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        rc = main(["--remove", "0", str(input_pdf), "-o", str(output)])
        assert rc == 1

    def test_audit_with_wrong_text_layer_returns_error_code(self, input_pdf, tmp_path):
        output = tmp_path / "output.pdf"
        audit = tmp_path / "audit.json"
        rc = main(
            [
                "--dpi",
                "100",
                "--text-layer",
                "none",
                "--audit",
                str(audit),
                str(input_pdf),
                "-o",
                str(output),
            ]
        )
        assert rc == 1

    @pytest.mark.skipif(not tesseract_available(), reason="tesseract がインストールされていない")
    def test_audit_option_writes_report_and_prints_count(self, input_pdf, tmp_path, capsys):
        output = tmp_path / "output.pdf"
        audit = tmp_path / "audit.json"
        rc = main(
            ["--dpi", "150", "--audit", str(audit), str(input_pdf), "-o", str(output)]
        )
        assert rc == 0
        assert audit.exists()
        report = json.loads(audit.read_text(encoding="utf-8"))
        assert "suspicious_items" in report
        captured = capsys.readouterr()
        assert "監査レポート" in captured.out
