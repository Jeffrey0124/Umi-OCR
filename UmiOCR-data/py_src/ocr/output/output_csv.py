# 输出到csv表格文件

import csv
import os

from umi_log import logger
from .output import Output
from .tools import getDataText


class OutputCsv(Output):
    def __init__(self, argd):
        self.dir = argd["outputDir"]
        self.fileName = argd["outputFileName"]
        self.ignoreBlank = argd["ignoreBlank"]
        self.batchOcrCsvMode = argd.get("batchOcrCsvMode", False)
        self.generatedPaths = []

        if self.batchOcrCsvMode:
            self.outputPath = ""
            self.outputDirType = argd["outputDirType"]
            self.fileNameFormat = argd.get("outputFileNameFormat", self.fileName)
            self.datetimeUser = argd.get("outputDatetimeUser", "")
            self.groups = {}
            return

        self.encodings = [
            "ansi",
            "ascii",
            "gbk",
            "big5",
            "shift_jis",
            "euc-kr",
            "utf-8",
        ]
        self.outputPath = os.path.join(self.dir, f"{self.fileName}.csv")
        self.writeLists = []
        self.writeText = ""
        try:
            with open(self.outputPath, "w", encoding="utf-8"):
                pass
        except Exception as e:
            raise Exception(f"Failed to create csv file. {e}\n创建csv文件失败。")
        self.generatedPaths = [self.outputPath]

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
        if not self.batchOcrCsvMode:
            self._print_legacy(res)
            return

        target_dir = self._target_dir(res)
        group = self.groups.setdefault(target_dir, {"text": [], "blank": []})
        name = res["fileName"]
        path = res["path"]
        if res["code"] == 100:
            text_out = getDataText(res["data"])
            if text_out.strip():
                group["text"].append([text_out, name, path])
                return
        if not self.ignoreBlank:
            group["blank"].append([name, path])

    def _print_legacy(self, res):
        if res["code"] != 100 and self.ignoreBlank:
            return
        name = res["fileName"]
        path = res["path"]
        if res["code"] == 100:
            text_out = getDataText(res["data"])
        elif res["code"] == 101:
            text_out = ""
        else:
            text_out = (
                f'[Error] OCR failed. Code: {res["code"]}, '
                f'Msg: {res["data"]} .\n'
            )
        self.writeLists.append([name, text_out, path])
        self.writeText += text_out

    def _write_csv(self, path, headers, rows, encoding="utf-8-sig"):
        with open(path, "w", encoding=encoding, newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)

    def onEnd(self):
        if not self.batchOcrCsvMode:
            self._on_end_legacy()
            return

        self.generatedPaths = []
        for target_dir, group in self.groups.items():
            file_name = self._file_name(target_dir)
            main_path = os.path.join(target_dir, f"{file_name}.csv")
            blank_path = os.path.join(target_dir, f"{file_name}_无文字.csv")
            if group["text"]:
                self._write_csv(main_path, ["ocr", "name", "path"], group["text"])
                self.generatedPaths.append(main_path)
            elif os.path.exists(main_path):
                os.remove(main_path)
            if group["blank"]:
                self._write_csv(blank_path, ["name", "path"], group["blank"])
                self.generatedPaths.append(blank_path)
            elif os.path.exists(blank_path):
                os.remove(blank_path)
        self.outputPath = self.generatedPaths[0] if self.generatedPaths else ""

    def _on_end_legacy(self):
        encoding = "utf-8"
        for candidate in self.encodings:
            try:
                self.writeText.encode(candidate)
                encoding = candidate
                break
            except Exception:
                pass
        logger.info(f"csv encoding: {encoding}")
        try:
            self._write_csv(
                self.outputPath,
                ["Name", "OCR", "Path"],
                self.writeLists,
                encoding=encoding,
            )
        except Exception as e:
            raise Exception(f"Failed to write csv file. {e}\n写入csv文件失败。")
