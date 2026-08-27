import csv
import importlib
import os
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


def result(path, code=100, text="中文内容", data=None):
    path = Path(path)
    if data is None:
        data = [{"text": text, "end": ""}] if code == 100 else ""
    return {
        "code": code,
        "data": data,
        "fileName": path.name,
        "path": str(path.resolve()),
        "dir": str(path.parent.resolve()),
    }


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def document_result(code=100, text="document"):
    data = [{"text": text, "end": ""}] if code == 100 else "failure"
    return {
        "code": code,
        "data": data,
        "fileName": "1",
        "path": "document.pdf",
    }


class OutputCsvTests(unittest.TestCase):
    def test_writes_one_five_column_csv_with_three_statuses(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "中文目录"
            folder.mkdir()
            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "10.png", code=101))
            writer.print(result(folder / "2.png", code=500, data="engine error"))
            writer.print(result(folder / "1.png", text="识别,\n中文"))
            writer.print(result(folder / "11.png", text=" \n"))
            writer.onEnd()

            output = folder / "[OCR]_中文目录_20260827_1200.csv"
            self.assertEqual(
                read_csv(output),
                [
                    ["OCR", "Name", "文件夹", "识别状态", "路径"],
                    ["识别,\n中文", "1", "中文目录", "成功", str((folder / "1.png").resolve())],
                    ["", "2", "中文目录", "失败", str((folder / "2.png").resolve())],
                    ["", "10", "中文目录", "无文字", str((folder / "10.png").resolve())],
                    ["", "11", "中文目录", "无文字", str((folder / "11.png").resolve())],
                ],
            )
            self.assertEqual(output.read_bytes()[:3], b"\xef\xbb\xbf")

    def test_code_101_with_error_message_is_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "error.png", code=101, data="cannot read"))
            writer.onEnd()

            rows = read_csv(folder / f"[OCR]_{folder.name}_20260827_1200.csv")
            self.assertEqual(rows[1][3], "失败")

    def test_writes_an_absolute_path_when_the_result_path_is_relative(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(output_args(folder))
            item = result(folder / "relative.png")
            item["path"] = "relative.png"
            writer.print(item)

            writer.onEnd()

            rows = read_csv(folder / f"[OCR]_{folder.name}_20260827_1200.csv")
            self.assertTrue(os.path.isabs(rows[1][4]))

    def test_source_mode_writes_direct_directory_tables_and_root_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            child = root / "child"
            grandchild = child / "grandchild"
            grandchild.mkdir(parents=True)
            writer = OutputCsv(output_args(root))
            writer.print(result(root / "root.png", text="root"))
            writer.print(result(child / "child.png", code=500, data="error"))
            writer.print(result(grandchild / "grandchild.png", code=101))
            writer.onEnd()

            root_table = root / "[OCR]_root_20260827_1200.csv"
            child_table = child / "[OCR]_child_20260827_1200.csv"
            grandchild_table = grandchild / "[OCR]_grandchild_20260827_1200.csv"
            summary = root / "[OCR]_root_20260827_1200_总表.csv"
            self.assertEqual(len(read_csv(root_table)), 2)
            self.assertEqual(len(read_csv(child_table)), 2)
            self.assertEqual(len(read_csv(grandchild_table)), 2)
            self.assertEqual([row[3] for row in read_csv(summary)[1:]], ["成功", "失败", "无文字"])

    def test_specified_directory_writes_one_aggregated_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            selected = base / "selected"
            selected.mkdir()
            writer = OutputCsv(output_args(selected, dir_type="specify"))
            writer.print(result(base / "a" / "one.png", text="一"))
            writer.print(result(base / "b" / "two.png", code=101))
            writer.onEnd()

            rows = read_csv(selected / "[OCR]_selected_20260827_1200.csv")
            self.assertEqual([row[1] for row in rows[1:]], ["one", "two"])
            self.assertFalse(any(selected.glob("*_总表.csv")))

    def test_always_keeps_no_text_and_only_removes_matching_old_blank_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "rerun"
            folder.mkdir()
            stale = folder / "[OCR]_rerun_20260827_1200_无文字.csv"
            unrelated = folder / "other_无文字.csv"
            stale.write_text("stale", encoding="utf-8")
            unrelated.write_text("keep", encoding="utf-8")
            args = output_args(folder)
            args["ignoreBlank"] = True
            writer = OutputCsv(args)
            writer.print(result(folder / "blank.png", code=101))
            writer.onEnd()

            rows = read_csv(folder / "[OCR]_rerun_20260827_1200.csv")
            self.assertEqual(rows[1][3], "无文字")
            self.assertFalse(stale.exists())
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_legacy_batch_doc_csv_behavior_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(legacy_output_args(folder))
            writer.print(document_result())
            writer.onEnd()

            self.assertEqual(
                read_csv(folder / "legacy.csv"),
                [["Name", "OCR", "Path"], ["1", "document", "document.pdf"]],
            )

    def test_legacy_document_server_and_ignore_blank_behavior_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            writer = OutputCsv(
                legacy_output_args(folder, dir_type="specify", ignore_blank=True)
            )
            writer.print(document_result())
            writer.print(document_result(code=101))
            writer.print(document_result(code=500))
            writer.onEnd()

            self.assertEqual(
                read_csv(folder / "legacy.csv"),
                [["Name", "OCR", "Path"], ["1", "document", "document.pdf"]],
            )

            writer = OutputCsv(legacy_output_args(folder, ignore_blank=False))
            writer.print(document_result(code=101))
            writer.print(document_result(code=500))
            writer.onEnd()
            rows = read_csv(folder / "legacy.csv")
            self.assertEqual(rows[1], ["1", "", "document.pdf"])
            self.assertIn("[Error] OCR failed. Code: 500", rows[2][1])


class BatchOcrConfigurationTests(unittest.TestCase):
    def test_qml_removes_ignore_blank_and_keeps_csv_defaults(self):
        qml = (
            DATA_ROOT / "qt_res" / "qml" / "TabPages" / "BatchOCR" / "BatchOCRConfigs.qml"
        ).read_text(encoding="utf-8")
        self.assertNotRegex(qml, r'"ignoreBlank"\s*:')
        for key, expected in {"recurrence": "true", "txt": "false", "csv": "true"}.items():
            match = re.search(rf'"{key}"\s*:\s*\{{(?P<body>[^{{}}]*)\}}', qml)
            self.assertIsNotNone(match)
            self.assertRegex(match["body"], rf'"default"\s*:\s*{expected}')

    def test_batch_ocr_csv_does_not_depend_on_ignore_blank_config(self):
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
                "mission.fileName": "resolved",
                "mission.fileNameFormat": "[OCR]_%name_%date",
                "startDatetimeUser": "20260827_1200",
                "startDatetime": "2026-08-27 12:00:00",
                "mission.filesType.csv": True,
            }
            self.assertTrue(page._initOutputList(argd))
        finally:
            batch_ocr_module.Output = original_output

        self.assertEqual(len(captured), 1)
        self.assertFalse(captured[0]["ignoreBlank"])
        self.assertTrue(captured[0]["batchOcrCsvMode"])


if __name__ == "__main__":
    unittest.main()
