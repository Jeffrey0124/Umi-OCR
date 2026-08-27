import csv
import importlib
import re
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "UmiOCR-data"
sys.path[:0] = [
    str(DATA_ROOT),
    str(DATA_ROOT / "site-packages"),
    str(DATA_ROOT / "py_src" / "imports"),
]

from py_src.ocr.output.output_csv import OutputCsv

warnings.filterwarnings(
    "ignore",
    message=r"builtin type swigvarlink has no __module__ attribute",
    category=DeprecationWarning,
)


def output_args(output_dir, dir_type="source"):
    return {
        "outputDir": str(output_dir),
        "outputDirType": dir_type,
        "outputFileName": "[OCR]_selected_20260827_1200",
        "outputFileNameFormat": "[OCR]_%name_%date",
        "outputDatetimeUser": "20260827_1200",
        "ignoreBlank": False,
        "batchOcrCsvMode": True,
    }


def legacy_output_args(output_dir, dir_type="source", ignore_blank=False):
    return {
        "outputDir": str(output_dir),
        "outputDirType": dir_type,
        "outputFileName": "legacy",
        "ignoreBlank": ignore_blank,
    }


def result(path, code=100, text="\u4e2d\u6587\u5185\u5bb9"):
    path = Path(path)
    data = [{"text": text, "end": ""}] if code == 100 else "failure"
    return {
        "code": code,
        "data": data,
        "fileName": path.name,
        "path": path.as_posix(),
        "dir": path.parent.as_posix(),
    }


def document_result(code=100, text="document text"):
    data = [{"text": text, "end": ""}] if code == 100 else "failure"
    return {
        "code": code,
        "data": data,
        "page": 1,
        "fileName": "1",
        "path": "document.pdf",
    }


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


class OutputCsvTests(unittest.TestCase):
    def test_legacy_batch_doc_source_writes_one_csv_without_result_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(legacy_output_args(folder, dir_type="source"))
            self.assertTrue((folder / "legacy.csv").exists())

            writer.print(document_result())
            writer.onEnd()

            self.assertEqual(
                read_csv(folder / "legacy.csv"),
                [["Name", "OCR", "Path"], ["1", "document text", "document.pdf"]],
            )
            self.assertFalse((folder / "legacy_\u65e0\u6587\u5b57.csv").exists())

    def test_legacy_document_server_specify_writes_one_csv_without_result_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(legacy_output_args(folder, dir_type="specify"))

            writer.print(document_result())
            writer.onEnd()

            self.assertEqual(
                read_csv(folder / "legacy.csv"),
                [["Name", "OCR", "Path"], ["1", "document text", "document.pdf"]],
            )
            self.assertFalse((folder / "legacy_\u65e0\u6587\u5b57.csv").exists())

    def test_legacy_ignore_blank_true_omits_blank_and_failed_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(legacy_output_args(folder, ignore_blank=True))
            writer.print(document_result())
            writer.print(document_result(code=101))
            writer.print(document_result(code=500))
            writer.onEnd()

            self.assertEqual(
                read_csv(folder / "legacy.csv"),
                [["Name", "OCR", "Path"], ["1", "document text", "document.pdf"]],
            )

    def test_legacy_ignore_blank_false_keeps_blank_and_failed_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(legacy_output_args(folder, ignore_blank=False))
            writer.print(document_result(code=101))
            writer.print(document_result(code=500))
            writer.onEnd()

            rows = read_csv(folder / "legacy.csv")
            self.assertEqual(rows[0], ["Name", "OCR", "Path"])
            self.assertEqual(rows[1], ["1", "", "document.pdf"])
            self.assertIn("[Error] OCR failed. Code: 500", rows[2][1])

    def test_splits_text_and_no_text_with_required_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "\u4e2d\u6587\u76ee\u5f55"
            folder.mkdir()
            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "\u6709\u5b57.png", text="\u8bc6\u522b\u4e2d\u6587"))
            writer.print(result(folder / "\u7a7a\u767d.png", code=101))
            writer.print(result(folder / "\u7eaf\u7a7a\u683c.png", text="  \n"))
            writer.print(result(folder / "\u5931\u8d25.png", code=500))
            writer.onEnd()

            main_path = folder / "[OCR]_\u4e2d\u6587\u76ee\u5f55_20260827_1200.csv"
            blank_path = folder / "[OCR]_\u4e2d\u6587\u76ee\u5f55_20260827_1200_\u65e0\u6587\u5b57.csv"
            self.assertEqual(
                read_csv(main_path),
                [["ocr", "name", "path"], ["\u8bc6\u522b\u4e2d\u6587", "\u6709\u5b57.png", (folder / "\u6709\u5b57.png").as_posix()]],
            )
            self.assertEqual(
                read_csv(blank_path),
                [
                    ["name", "path"],
                    ["\u7a7a\u767d.png", (folder / "\u7a7a\u767d.png").as_posix()],
                    ["\u7eaf\u7a7a\u683c.png", (folder / "\u7eaf\u7a7a\u683c.png").as_posix()],
                    ["\u5931\u8d25.png", (folder / "\u5931\u8d25.png").as_posix()],
                ],
            )
            self.assertEqual(main_path.read_bytes()[:3], b"\xef\xbb\xbf")

    def test_does_not_create_an_empty_category_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "only_text"
            folder.mkdir()
            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "\u6709\u5b57.png"))
            writer.onEnd()

            main_path = folder / "[OCR]_only_text_20260827_1200.csv"
            self.assertTrue(main_path.exists())
            self.assertFalse((folder / "[OCR]_only_text_20260827_1200_\u65e0\u6587\u5b57.csv").exists())
            self.assertEqual(writer.generatedPaths, [str(main_path)])
            self.assertEqual(writer.outputPath, str(main_path))

    def test_batch_ocr_ignore_blank_true_omits_no_text_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "ignore_blank"
            folder.mkdir()
            args = output_args(folder)
            args["ignoreBlank"] = True
            writer = OutputCsv(args)
            writer.print(result(folder / "text.png"))
            writer.print(result(folder / "blank.png", code=101))
            writer.print(result(folder / "whitespace.png", text=" \n"))
            writer.print(result(folder / "failed.png", code=500))
            writer.onEnd()

            self.assertTrue(
                (folder / "[OCR]_ignore_blank_20260827_1200.csv").exists()
            )
            self.assertFalse(
                (folder / "[OCR]_ignore_blank_20260827_1200_\u65e0\u6587\u5b57.csv").exists()
            )

    def test_batch_ocr_ignore_blank_false_keeps_no_text_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "keep_blank"
            folder.mkdir()
            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "blank.png", code=101))
            writer.onEnd()

            self.assertEqual(
                read_csv(folder / "[OCR]_keep_blank_20260827_1200_\u65e0\u6587\u5b57.csv"),
                [
                    ["name", "path"],
                    ["blank.png", (folder / "blank.png").as_posix()],
                ],
            )

    def test_main_only_rerun_removes_exact_stale_no_text_counterpart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "rerun"
            folder.mkdir()
            main_path = folder / "[OCR]_rerun_20260827_1200.csv"
            blank_path = folder / "[OCR]_rerun_20260827_1200_\u65e0\u6587\u5b57.csv"
            other_path = folder / "other_\u65e0\u6587\u5b57.csv"
            main_path.write_text("stale main", encoding="utf-8")
            blank_path.write_text("stale blank", encoding="utf-8")
            other_path.write_text("keep me", encoding="utf-8")

            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "text.png", text="fresh"))
            writer.onEnd()

            self.assertEqual(read_csv(main_path)[1][0], "fresh")
            self.assertFalse(blank_path.exists())
            self.assertEqual(other_path.read_text(encoding="utf-8"), "keep me")

    def test_no_text_only_rerun_removes_exact_stale_main_counterpart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "rerun"
            folder.mkdir()
            main_path = folder / "[OCR]_rerun_20260827_1200.csv"
            blank_path = folder / "[OCR]_rerun_20260827_1200_\u65e0\u6587\u5b57.csv"
            other_path = folder / "other.csv"
            main_path.write_text("stale main", encoding="utf-8")
            blank_path.write_text("stale blank", encoding="utf-8")
            other_path.write_text("keep me", encoding="utf-8")

            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "blank.png", code=101))
            writer.onEnd()

            self.assertFalse(main_path.exists())
            self.assertEqual(read_csv(blank_path)[1][0], "blank.png")
            self.assertEqual(other_path.read_text(encoding="utf-8"), "keep me")

    def test_groups_each_image_by_its_direct_parent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            child = root / "\u7b2c\u4e00\u5c42"
            grandchild = child / "\u7b2c\u4e8c\u5c42"
            grandchild.mkdir(parents=True)
            writer = OutputCsv(output_args(root))
            writer.print(result(root / "root.png", text="\u6839"))
            writer.print(result(child / "child.png", text="\u4e00\u5c42"))
            writer.print(result(grandchild / "blank.png", code=101))
            writer.onEnd()

            self.assertEqual(len(read_csv(root / "[OCR]_root_20260827_1200.csv")), 2)
            self.assertEqual(len(read_csv(child / "[OCR]_\u7b2c\u4e00\u5c42_20260827_1200.csv")), 2)
            self.assertEqual(
                read_csv(grandchild / "[OCR]_\u7b2c\u4e8c\u5c42_20260827_1200_\u65e0\u6587\u5b57.csv")[1][0],
                "blank.png",
            )

    def test_specified_directory_aggregates_all_source_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            selected = base / "selected"
            selected.mkdir()
            writer = OutputCsv(output_args(selected, dir_type="specify"))
            writer.print(result(base / "a" / "one.png", text="\u4e00"))
            writer.print(result(base / "b" / "two.png", text="\u4e8c"))
            writer.onEnd()

            rows = read_csv(selected / "[OCR]_selected_20260827_1200.csv")
            self.assertEqual([row[1] for row in rows[1:]], ["one.png", "two.png"])
            self.assertFalse((base / "a" / "[OCR]_a_20260827_1200.csv").exists())


class BatchOcrConfigurationTests(unittest.TestCase):
    def test_qml_defaults_match_requested_batch_settings(self):
        qml = (
            DATA_ROOT
            / "qt_res"
            / "qml"
            / "TabPages"
            / "BatchOCR"
            / "BatchOCRConfigs.qml"
        ).read_text(encoding="utf-8")
        expected_defaults = {
            "recurrence": "true",
            "txt": "false",
            "csv": "true",
            "ignoreBlank": "false",
        }
        for key, expected in expected_defaults.items():
            match = re.search(
                rf'"{re.escape(key)}"\s*:\s*\{{(?P<body>[^{{}}]*)\}}', qml
            )
            self.assertIsNotNone(match, f"missing leaf config block: {key}")
            default = re.search(r'"default"\s*:\s*(true|false)', match["body"])
            self.assertIsNotNone(default, f"missing default in config block: {key}")
            self.assertEqual(default.group(1), expected)

    def test_batch_ocr_passes_per_directory_filename_inputs(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            batch_ocr_module = importlib.import_module("py_src.tag_pages.BatchOCR")
        captured = []

        class StubOutput:
            def __init__(self, argd):
                captured.append(argd.copy())

        original_output = batch_ocr_module.Output
        batch_ocr_module.Output = {"csv": StubOutput}
        try:
            page = batch_ocr_module.BatchOCR("test", None)
            argd = {
                "mission.dir": "selected",
                "mission.dirType": "source",
                "mission.fileName": "resolved-first-directory",
                "mission.fileNameFormat": "[OCR]_%name_%date",
                "startDatetimeUser": "20260827_1200",
                "startDatetime": "2026-08-27 12:00:00",
                "mission.ignoreBlank": False,
                "mission.filesType.csv": True,
            }

            self.assertTrue(page._initOutputList(argd))
        finally:
            batch_ocr_module.Output = original_output

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["outputFileName"], "resolved-first-directory")
        self.assertEqual(captured[0]["outputFileNameFormat"], "[OCR]_%name_%date")
        self.assertEqual(captured[0]["outputDatetimeUser"], "20260827_1200")
        self.assertIs(captured[0]["batchOcrCsvMode"], True)


if __name__ == "__main__":
    unittest.main()
