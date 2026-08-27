# Batch OCR CSV by Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make batch OCR default to recursive CSV-only processing and emit per-directory text and no-text CSV files with the required columns.

**Architecture:** Keep one OCR mission and enhance `OutputCsv` to classify each result, group it by the image's direct parent directory in source mode, and write each group at mission end. Preserve specified-directory aggregation, and pass the unresolved filename format plus formatted user date from `BatchOCR` so every source directory receives its own `%name` substitution.

**Tech Stack:** Python 3.8 standard library (`csv`, `os`, `unittest`, `tempfile`), QML configuration, bundled Umi-OCR runtime.

## Global Constraints

- Main CSV columns are exactly `ocr,name,path`.
- No-text CSV columns are exactly `name,path`.
- A successful result whose joined OCR text is empty or whitespace-only is a no-text result.
- OCR code `101` and every OCR failure code are no-text results.
- Each source directory receives only results for images directly inside it; the selected root follows the same rule.
- Do not create an empty main or no-text table.
- CSV encoding is `utf-8-sig`.
- Specified-directory mode remains one aggregated destination.
- The extracted distribution is not a Git repository, so commit steps are unavailable.

---

## File Structure

- Create `tests/test_batch_ocr_csv.py`: real CSV I/O tests for classification, columns, directory grouping, encoding, compatibility mode, and QML defaults.
- Modify `UmiOCR-data/py_src/ocr/output/output_csv.py`: classify, group, name, and write CSV files.
- Modify `UmiOCR-data/py_src/tag_pages/BatchOCR.py`: retain the user-formatted date and pass filename-resolution inputs to outputters.
- Modify `UmiOCR-data/qt_res/qml/TabPages/BatchOCR/BatchOCRConfigs.qml`: set recursive, CSV-only, and screenshot-matching defaults.

### Task 1: CSV result classification and per-directory writer

**Files:**
- Create: `tests/test_batch_ocr_csv.py`
- Modify: `UmiOCR-data/py_src/ocr/output/output_csv.py`

**Interfaces:**
- Consumes: output argument keys `outputDir`, `outputDirType`, `outputFileName`, `outputFileNameFormat`, `outputDatetimeUser`, and `ignoreBlank`; OCR result keys `code`, `data`, `fileName`, `path`, and `dir`.
- Produces: `OutputCsv.print(res) -> None` and `OutputCsv.onEnd() -> None`; source-mode files named `<resolved prefix>.csv` and `<resolved prefix>_无文字.csv`.

- [ ] **Step 1: Write failing tests for columns, classification, encoding, and omission of empty tables**

Create the test bootstrap and first test class:

```python
import csv
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "UmiOCR-data"
sys.path[:0] = [
    str(DATA_ROOT),
    str(DATA_ROOT / "site-packages"),
    str(DATA_ROOT / "py_src" / "imports"),
]

from py_src.ocr.output.output_csv import OutputCsv


def output_args(output_dir, dir_type="source"):
    return {
        "outputDir": str(output_dir),
        "outputDirType": dir_type,
        "outputFileName": "[OCR]_selected_20260827_1200",
        "outputFileNameFormat": "[OCR]_%name_%date",
        "outputDatetimeUser": "20260827_1200",
        "ignoreBlank": False,
    }


def result(path, code=100, text="中文内容"):
    path = Path(path)
    data = [{"text": text, "end": ""}] if code == 100 else "failure"
    return {
        "code": code,
        "data": data,
        "fileName": path.name,
        "path": path.as_posix(),
        "dir": path.parent.as_posix(),
    }


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


class OutputCsvTests(unittest.TestCase):
    def test_splits_text_and_no_text_with_required_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "中文目录"
            folder.mkdir()
            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "有字.png", text="识别中文"))
            writer.print(result(folder / "空白.png", code=101))
            writer.print(result(folder / "纯空格.png", text="  \n"))
            writer.print(result(folder / "失败.png", code=500))
            writer.onEnd()

            main_path = folder / "[OCR]_中文目录_20260827_1200.csv"
            blank_path = folder / "[OCR]_中文目录_20260827_1200_无文字.csv"
            self.assertEqual(
                read_csv(main_path),
                [["ocr", "name", "path"], ["识别中文", "有字.png", (folder / "有字.png").as_posix()]],
            )
            self.assertEqual(
                read_csv(blank_path),
                [
                    ["name", "path"],
                    ["空白.png", (folder / "空白.png").as_posix()],
                    ["纯空格.png", (folder / "纯空格.png").as_posix()],
                    ["失败.png", (folder / "失败.png").as_posix()],
                ],
            )
            self.assertEqual(main_path.read_bytes()[:3], b"\xef\xbb\xbf")

    def test_does_not_create_an_empty_category_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "only_text"
            folder.mkdir()
            writer = OutputCsv(output_args(folder))
            writer.print(result(folder / "有字.png"))
            writer.onEnd()

            self.assertTrue((folder / "[OCR]_only_text_20260827_1200.csv").exists())
            self.assertFalse((folder / "[OCR]_only_text_20260827_1200_无文字.csv").exists())
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run from the project root:

```powershell
& '.\UmiOCR-data\runtime\python.exe' '.\tests\test_batch_ocr_csv.py' OutputCsvTests -v
```

Expected: FAIL because current output writes `Name,OCR,Path`, ignores grouped filenames, and does not create the no-text table.

- [ ] **Step 3: Add failing tests for direct-parent grouping and specified-directory aggregation**

Append these methods to `OutputCsvTests`:

```python
    def test_groups_each_image_by_its_direct_parent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            child = root / "第一层"
            grandchild = child / "第二层"
            grandchild.mkdir(parents=True)
            writer = OutputCsv(output_args(root))
            writer.print(result(root / "root.png", text="根"))
            writer.print(result(child / "child.png", text="一层"))
            writer.print(result(grandchild / "blank.png", code=101))
            writer.onEnd()

            self.assertEqual(len(read_csv(root / "[OCR]_root_20260827_1200.csv")), 2)
            self.assertEqual(len(read_csv(child / "[OCR]_第一层_20260827_1200.csv")), 2)
            self.assertEqual(
                read_csv(grandchild / "[OCR]_第二层_20260827_1200_无文字.csv")[1][0],
                "blank.png",
            )

    def test_specified_directory_aggregates_all_source_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            selected = base / "selected"
            selected.mkdir()
            writer = OutputCsv(output_args(selected, dir_type="specify"))
            writer.print(result(base / "a" / "one.png", text="一"))
            writer.print(result(base / "b" / "two.png", text="二"))
            writer.onEnd()

            rows = read_csv(selected / "[OCR]_selected_20260827_1200.csv")
            self.assertEqual([row[1] for row in rows[1:]], ["one.png", "two.png"])
            self.assertFalse((base / "a" / "[OCR]_a_20260827_1200.csv").exists())
```

- [ ] **Step 4: Run the focused tests and verify RED**

Run the same `unittest` command. Expected: the new grouping test fails because current `OutputCsv` has only one fixed `outputPath`.

- [ ] **Step 5: Implement the minimal grouped CSV writer**

Replace `output_csv.py` with an implementation organized around these exact methods:

```python
import csv
import os

from .output import Output
from .tools import getDataText


class OutputCsv(Output):
    def __init__(self, argd):
        self.dir = argd["outputDir"]
        self.fileName = argd["outputFileName"]
        self.outputPath = os.path.join(self.dir, f"{self.fileName}.csv")
        self.outputDirType = argd["outputDirType"]
        self.fileNameFormat = argd.get("outputFileNameFormat", self.fileName)
        self.datetimeUser = argd.get("outputDatetimeUser", "")
        self.ignoreBlank = argd["ignoreBlank"]
        self.groups = {}

    def _target_dir(self, res):
        if self.outputDirType == "source":
            return os.path.normpath(res["dir"])
        return os.path.normpath(self.dir)

    def _file_name(self, target_dir):
        if self.outputDirType != "source":
            return self.fileName
        directory_name = os.path.basename(target_dir)
        return self.fileNameFormat.replace("%date", self.datetimeUser).replace(
            "%name", directory_name
        )

    def print(self, res):
        target_dir = self._target_dir(res)
        group = self.groups.setdefault(target_dir, {"text": [], "blank": []})
        name = res["fileName"]
        path = res["path"]
        if res["code"] == 100:
            text_out = getDataText(res["data"])
            if text_out.strip():
                group["text"].append([text_out, name, path])
                return
        group["blank"].append([name, path])

    def _write_csv(self, path, headers, rows):
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)

    def onEnd(self):
        for target_dir, group in self.groups.items():
            file_name = self._file_name(target_dir)
            main_path = os.path.join(target_dir, f"{file_name}.csv")
            blank_path = os.path.join(target_dir, f"{file_name}_无文字.csv")
            if group["text"]:
                self._write_csv(main_path, ["ocr", "name", "path"], group["text"])
            if group["blank"]:
                self._write_csv(blank_path, ["name", "path"], group["blank"])
```

Keep the class free of engine-specific logic; classification uses only the established OCR response contract.

- [ ] **Step 6: Run Task 1 tests and verify GREEN**

Run:

```powershell
& '.\UmiOCR-data\runtime\python.exe' '.\tests\test_batch_ocr_csv.py' OutputCsvTests -v
```

Expected: 4 tests pass with no warnings or tracebacks.

### Task 2: Filename inputs and batch OCR defaults

**Files:**
- Modify: `tests/test_batch_ocr_csv.py`
- Modify: `UmiOCR-data/py_src/tag_pages/BatchOCR.py:66-103`
- Modify: `UmiOCR-data/qt_res/qml/TabPages/BatchOCR/BatchOCRConfigs.qml:39-113`

**Interfaces:**
- Consumes: `mission.fileNameFormat`, `mission.datetimeFormat`, and the existing first image path.
- Produces: `argd["startDatetimeUser"]`; output argument keys `outputFileNameFormat` and `outputDatetimeUser`; QML defaults recurrence `true`, txt `false`, csv `true`, ignoreBlank `false`.

- [ ] **Step 1: Write failing static tests for the four defaults and Python handoff keys**

Append this class to `tests/test_batch_ocr_csv.py`:

```python
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
        patterns = [
            r'"recurrence"\s*:\s*\{.*?"default"\s*:\s*true',
            r'"txt"\s*:\s*\{.*?"default"\s*:\s*false',
            r'"csv"\s*:\s*\{.*?"default"\s*:\s*true',
            r'"ignoreBlank"\s*:\s*\{.*?"default"\s*:\s*false',
        ]
        for pattern in patterns:
            self.assertIsNotNone(re.search(pattern, qml, re.S))

    def test_batch_ocr_passes_per_directory_filename_inputs(self):
        source = (DATA_ROOT / "py_src" / "tag_pages" / "BatchOCR.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('argd["startDatetimeUser"] = startDatetimeUser', source)
        self.assertIn('"outputFileNameFormat": argd["mission.fileNameFormat"]', source)
        self.assertIn('"outputDatetimeUser": argd["startDatetimeUser"]', source)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run configuration tests and verify RED**

Run:

```powershell
& '.\UmiOCR-data\runtime\python.exe' '.\tests\test_batch_ocr_csv.py' BatchOcrConfigurationTests -v
```

Expected: FAIL because the current recurrence/csv defaults are false, txt/ignoreBlank defaults are true, and the filename handoff keys do not exist.

- [ ] **Step 3: Preserve the user-formatted timestamp in `BatchOCR`**

Immediately after calculating `startDatetimeUser`, add:

```python
argd["startDatetimeUser"] = startDatetimeUser
```

This is separate from the existing standardized `startDatetime`, which other outputters still consume.

- [ ] **Step 4: Pass filename format inputs to outputters**

In `outputArgd`, add:

```python
"outputFileNameFormat": argd["mission.fileNameFormat"],
"outputDatetimeUser": argd["startDatetimeUser"],
```

Do not remove `outputFileName`; specified-directory mode and all existing outputters continue to use it.

- [ ] **Step 5: Change only the requested QML defaults**

Set these exact values in `BatchOCRConfigs.qml`:

```qml
"recurrence": {
    // existing title and tooltip
    "default": true,
},
```

```qml
"txt": {
    // existing title and tooltip
    "default": false,
},
```

```qml
"csv": {
    // existing title and tooltip
    "default": true,
},
```

```qml
"ignoreBlank": {
    // existing title and tooltip
    "default": false,
},
```

Leave the options list ordering unchanged so `source` remains the default save destination.

- [ ] **Step 6: Run configuration tests and verify GREEN**

Run the Task 2 test command. Expected: 2 tests pass.

- [ ] **Step 7: Run the full automated suite**

Run:

```powershell
& '.\UmiOCR-data\runtime\python.exe' '.\tests\test_batch_ocr_csv.py' -v
```

Expected: 6 tests pass, zero failures, zero errors.

### Task 3: Packaged-runtime smoke verification

**Files:**
- Verify only; no production changes unless a test exposes a defect.

**Interfaces:**
- Consumes: completed Tasks 1 and 2.
- Produces: fresh evidence that imports, compilation, and realistic directory output work in the bundled runtime.

- [ ] **Step 1: Compile the changed Python files**

Run:

```powershell
& '.\UmiOCR-data\runtime\python.exe' -m py_compile `
  '.\UmiOCR-data\py_src\ocr\output\output_csv.py' `
  '.\UmiOCR-data\py_src\tag_pages\BatchOCR.py' `
  '.\tests\test_batch_ocr_csv.py'
```

Expected: exit code 0 with no output.

- [ ] **Step 2: Re-run the full suite immediately before completion**

Run:

```powershell
& '.\UmiOCR-data\runtime\python.exe' '.\tests\test_batch_ocr_csv.py' -v
```

Expected: all 6 tests pass with no warnings or tracebacks.

- [ ] **Step 3: Inspect the final diff without Git**

Because this directory is not a Git repository, read the three modified production files and the test file directly. Confirm line-by-line that no OCR engine, mission-control, or unrelated output format behavior changed.
