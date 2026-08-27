from .output_txt import OutputTxt
from .output_txt_plain import OutputTxtPlain
from .output_txt_individual import OutputTxtIndividual
from .output_md import OutputMD
from .output_jsonl import OutputJsonl
from .output_csv import OutputCsv
from .output_pdf_layered import OutputPdfLayered
from .output_pdf_one_layer import OutputPdfOneLayer

"""纯文本输出器。初始化传入参数字典：
    outputArgd = {
        "outputDir": "",  # 输出路径
        "outputDirType": "",  # 输出目录类型，"source" 为原文件目录，"specify"为指定目录
        "outputFileName": "",  # 输出文件名（前缀）
        "startDatetime": "",  # 开始日期字符串（标准格式）
        "ignoreBlank": True/False,  # 忽略空白文件
        # 仅 BatchOCR 传入以启用按目录的主表/无文字表：
        "batchOcrCsvMode": True,
        "outputFileNameFormat": "",  # BatchOCR 源目录文件名模板
        "outputDatetimeUser": "",  # BatchOCR %date 替换值
    }

CSV 输出器在 BatchOCR 模式下可生成多个文件，实际路径记录在
``generatedPaths`` 中，``outputPath`` 指向第一个已生成文件。
"""
Output = {
    # 纯文本输出器
    "txt": OutputTxt,
    "txtPlain": OutputTxtPlain,
    "txtIndividual": OutputTxtIndividual,
    "md": OutputMD,
    "jsonl": OutputJsonl,
    "csv": OutputCsv,
    # PDF输出器，需要额外的参数 "originPath" 原始文件路径
    "pdfLayered": OutputPdfLayered,
    "pdfOneLayer": OutputPdfOneLayer,
}
