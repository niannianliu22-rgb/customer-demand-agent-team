#!/usr/bin/env python3
"""Generate six deterministic, synthetic Excel delivery fixtures."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input"

MANAGED = ["日期", "国家", "学校", "学历", "专业/课程", "DDL", "作业形式", "客户来源", "订单编号", "订单金额/澳刀", "跟进反馈", "进度"]
MANAGED_RMB = ["日期", "国家", "学校", "学历", "专业/课程", "DDL", "作业形式", "客户来源", "订单编号", "订单金额/人民币", "跟进反馈", "进度"]
MANAGED_2025 = ["日期", "国家", "学校", "学历", "专业/课程", "DDL", "作业形式", "客户类型", "订单编号", "金额", "跟进反馈", "进度"]
ADVISOR = ["日期", "客服", "国家", "院校", "专业", "学历", "咨询内容", "DDL", "客户类型", "进度", "客户备注", "成交金额"]
ADVISOR_2024 = ["日期", "客服", "国家", "院校", "专业", "学历", "作业类型", "DDL", "客户类型", "进度", "客户备注", "成交金额", "未成交原因"]
ADVISOR_2025 = ["日期", "客服", "国家", "院校", "专业", "学历", "作业类型", "DDL", "客户类型", "进度", "订单编号", "成交金额", "未成交原因"]

def managed_row(year: int, index: int, headers: list[str]) -> list[object]:
    values = {"日期": date(year, 8, 1) + timedelta(days=index), "国家": "示例国", "学校": "示例大学-北校区", "学历": "本科", "专业/课程": "合成研究导论", "DDL": date(year, 8, 12) + timedelta(days=index), "作业形式": "Synthetic Essay", "客户来源": "Synthetic Channel", "客户类型": "Synthetic Type", "订单编号": f"DEMO-{year}-M-{index:03d}", "订单金额/澳刀": 1000 + index, "订单金额/人民币": 5000 + index, "金额": 800 + index, "跟进反馈": "Synthetic follow-up", "进度": "Synthetic complete"}
    return [values.get(header, "") for header in headers]

def advisor_row(year: int, index: int, headers: list[str]) -> list[object]:
    values = {"日期": date(year, 8, 1) + timedelta(days=index), "客服": "Synthetic Advisor", "国家": "示例国", "院校": "示例大学-南校区", "专业": "合成课程设计", "学历": "硕士", "咨询内容": "Synthetic inquiry", "作业类型": "Synthetic Report", "DDL": date(year, 8, 14) + timedelta(days=index), "客户类型": "Synthetic Type", "进度": "Synthetic pending", "客户备注": "Synthetic note", "订单编号": f"DEMO-{year}-A-{index:03d}", "成交金额": 1200 + index, "未成交原因": "Synthetic reason"}
    return [values.get(header, "") for header in headers]

def write(name: str, headers: list[str], row_factory, year: int) -> None:
    book = Workbook(); sheet = book.active; sheet.title = "工作表1"; sheet.append(headers)
    for index in range(1, 13): sheet.append(row_factory(year, index, headers))
    book.save(INPUT / name)

def main() -> None:
    INPUT.mkdir(parents=True, exist_ok=True)
    write("2023年8月学管部咨询数据.xlsx", MANAGED, managed_row, 2023)
    write("2024年8月学管部咨询数据.xlsx", MANAGED_RMB, managed_row, 2024)
    write("2025年8月学管部咨询数据.xlsx", MANAGED_2025, managed_row, 2025)
    write("2023年8月顾问部咨询数据.xlsx", ADVISOR, advisor_row, 2023)
    write("2024年8月顾问部咨询数据.xlsx", ADVISOR_2024, advisor_row, 2024)
    write("2025年8月顾问部咨询数据.xlsx", ADVISOR_2025, advisor_row, 2025)

if __name__ == "__main__": main()
