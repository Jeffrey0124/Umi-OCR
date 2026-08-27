# 输出到csv表格文件

import csv
import os
import re

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
        group = self.groups.setdefault(target_dir, [])
        name = os.path.splitext(res["fileName"])[0]
        folder = os.path.basename(os.path.normpath(res["dir"]))
        path = os.path.abspath(res["path"])
        text_out = ""
        if res["code"] == 100:
            text_out = getDataText(res["data"])
            if text_out.strip():
                status = "成功"
            else:
                status = "无文字"
                text_out = ""
        elif res["code"] == 101 and not self._has_error_message(res["data"]):
            status = "无文字"
        else:
            status = "失败"
        group.append([text_out, name, folder, status, path])

    def _has_error_message(self, data):
        if isinstance(data, str):
            return bool(data.strip())
        return bool(data)

    def _natural_path_key(self, path):
        return [
            int(part) if part.isdigit() else os.path.normcase(part)
            for part in re.split(r"(\d+)", path)
        ]

    def _sorted_rows(self, rows):
        status_order = {"成功": 0, "失败": 1, "无文字": 2}
        return sorted(
            rows,
            key=lambda row: (status_order[row[3]], self._natural_path_key(row[4])),
        )

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
        headers = ["OCR", "Name", "文件夹", "识别状态", "路径"]
        if self.outputDirType == "source":
            all_rows = []
            for target_dir, rows in self.groups.items():
                file_name = self._file_name(target_dir)
                output_path = os.path.join(target_dir, f"{file_name}.csv")
                self._remove_old_blank_csv(target_dir, file_name)
                self._write_csv(output_path, headers, self._sorted_rows(rows))
                self.generatedPaths.append(output_path)
                all_rows.extend(rows)

            if all_rows:
                root_dir = os.path.normpath(self.dir)
                summary_name = f"{self._file_name(root_dir)}_总表"
                summary_path = os.path.join(root_dir, f"{summary_name}.csv")
                self._write_csv(summary_path, headers, self._sorted_rows(all_rows))
                self.generatedPaths.append(summary_path)
        else:
            rows = [row for group in self.groups.values() for row in group]
            if rows:
                self._remove_old_blank_csv(self.dir, self.fileName)
                output_path = os.path.join(self.dir, f"{self.fileName}.csv")
                self._write_csv(output_path, headers, self._sorted_rows(rows))
                self.generatedPaths.append(output_path)
        self.outputPath = self.generatedPaths[0] if self.generatedPaths else ""

    def _remove_old_blank_csv(self, target_dir, file_name):
        blank_path = os.path.join(target_dir, f"{file_name}_无文字.csv")
        if os.path.exists(blank_path):
            os.remove(blank_path)

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
