"""Build deterministic synthetic document fixtures for parsing evaluation."""

from __future__ import annotations

import os
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ASSET_DIR = Path(__file__).resolve().parent / "assets"
BODY_FONT = "SyntheticCJK"


def _font_path(*, bold: bool = False) -> Path:
    configured = os.getenv("EVAL_CJK_FONT")
    candidates = [
        Path(configured) if configured else None,
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise RuntimeError("A CJK font is required; set EVAL_CJK_FONT")


def _pil_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_font_path(bold=bold)), size=size)


def _set_run_font(run, size: int, *, bold: bool = False, color: str = "000000") -> None:
    run.font.name = "Microsoft YaHei"
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def _set_table_geometry(table, widths: list[int]) -> None:
    table.autofit = False
    properties = table._tbl.tblPr
    width = properties.first_child_found_in("w:tblW")
    width.set(qn("w:type"), "dxa")
    width.set(qn("w:w"), str(sum(widths)))
    indent = OxmlElement("w:tblInd")
    indent.set(qn("w:type"), "dxa")
    indent.set(qn("w:w"), "120")
    properties.append(indent)
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for value in widths:
        column = OxmlElement("w:gridCol")
        column.set(qn("w:w"), str(value))
        grid.append(column)
    for row in table.rows:
        for cell, value in zip(row.cells, widths):
            cell.width = Inches(value / 1440)
            cell._tc.tcPr.tcW.set(qn("w:type"), "dxa")
            cell._tc.tcPr.tcW.set(qn("w:w"), str(value))
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def build_native_text_pdf() -> None:
    path = ASSET_DIR / "native_order_requirement.pdf"
    pdfmetrics.registerFont(TTFont(BODY_FONT, str(_font_path())))
    pdf = canvas.Canvas(str(path), pagesize=letter)
    pdf.setTitle("Synthetic Order Requirement")
    pdf.setFont(BODY_FONT, 18)
    pdf.drawString(72, 720, "订单创建需求")
    pdf.setFont(BODY_FONT, 11)
    lines = [
        "用户提交订单时校验可售库存。",
        "库存充足时创建订单并扣减库存。",
        "库存不足时拒绝创建，并提示“库存不足”。",
        "相同 request_id 重复提交时只能创建一张订单。",
    ]
    for index, line in enumerate(lines):
        pdf.drawString(72, 675 - index * 28, line)
    pdf.save()


def build_role_matrix_docx() -> None:
    path = ASSET_DIR / "role_permission_matrix.docx"
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = section.right_margin = Inches(1)
    section.bottom_margin = section.left_margin = Inches(1)

    normal = document.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    heading = document.styles["Heading 1"]
    heading.font.name = "Microsoft YaHei"
    heading._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    heading.font.size = Pt(16)
    heading.font.color.rgb = RGBColor(0x2E, 0x74, 0xB5)
    heading.paragraph_format.space_before = Pt(18)
    heading.paragraph_format.space_after = Pt(10)

    document.add_heading("项目角色权限矩阵", level=1)
    document.add_paragraph("角色变更后，新权限立即生效。")
    rows = [
        ("角色", "查看项目", "修改项目", "管理成员"),
        ("管理员", "允许", "允许", "允许"),
        ("编辑者", "允许", "允许", "拒绝"),
        ("查看者", "允许", "拒绝", "拒绝"),
    ]
    table = document.add_table(rows=len(rows), cols=4)
    table.style = "Table Grid"
    for row_index, values in enumerate(rows):
        for column_index, value in enumerate(values):
            paragraph = table.cell(row_index, column_index).paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_run_font(paragraph.add_run(value), 10, bold=row_index == 0)
    _set_table_geometry(table, [1800, 2520, 2520, 2520])
    document.save(path)


def build_scanned_pdf() -> None:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.text((110, 130), "退款处理规则", font=_pil_font(46, bold=True), fill="#172033")
    lines = [
        "已支付订单允许多次部分退款。",
        "累计退款金额不得超过订单实付金额。",
        "退款成功后记录退款单号和累计退款金额。",
        "退款处理中不得重复提交同一退款申请。",
    ]
    for index, line in enumerate(lines):
        draw.text((110, 250 + index * 82), line, font=_pil_font(30), fill="#172033")
    image.save(ASSET_DIR / "scanned_refund_requirement.pdf", "PDF", resolution=150)


def _box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], text: str) -> None:
    draw.rounded_rectangle(xy, radius=18, fill="#EFF5FF", outline="#2F6FEB", width=3)
    left, top, right, bottom = xy
    bounds = draw.textbbox((0, 0), text, font=_pil_font(28, bold=True))
    x = left + (right - left - (bounds[2] - bounds[0])) / 2
    y = top + (bottom - top - (bounds[3] - bounds[1])) / 2
    draw.text((x, y), text, font=_pil_font(28, bold=True), fill="#172033")


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    draw.line([start, end], fill="#52606D", width=5)
    x, y = end
    draw.polygon([(x, y), (x - 15, y - 10), (x - 15, y + 10)], fill="#52606D")


def build_flow_diagram() -> None:
    image = Image.new("RGB", (1200, 700), "white")
    draw = ImageDraw.Draw(image)
    _box(draw, (70, 280, 300, 390), "提交订单")
    _box(draw, (430, 280, 700, 390), "校验库存")
    _box(draw, (850, 100, 1130, 210), "创建订单")
    _box(draw, (850, 470, 1130, 580), "提示库存不足")
    _arrow(draw, (300, 335), (430, 335))
    _arrow(draw, (700, 335), (850, 155))
    _arrow(draw, (700, 335), (850, 525))
    draw.text((710, 205), "库存充足", font=_pil_font(24), fill="#137333")
    draw.text((710, 430), "库存不足", font=_pil_font(24), fill="#B3261E")
    image.save(ASSET_DIR / "order_inventory_flow.png")


def build_upload_ui() -> None:
    image = Image.new("RGB", (1200, 760), "#F7F9FC")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((90, 60, 1110, 700), radius=24, fill="white", outline="#D0D7DE", width=2)
    draw.text((140, 105), "发票上传", font=_pil_font(40, bold=True), fill="#172033")
    draw.text((140, 175), "支持 PDF、JPG、PNG，单个文件最大 10MB", font=_pil_font(24), fill="#52606D")
    draw.rounded_rectangle((140, 235, 1060, 410), radius=18, fill="#F7FAFF", outline="#8BA9D6", width=3)
    draw.text((420, 280), "拖拽文件到此处", font=_pil_font(28), fill="#52606D")
    draw.rounded_rectangle((465, 340, 735, 395), radius=12, fill="#2F6FEB")
    draw.text((530, 350), "选择文件", font=_pil_font(24, bold=True), fill="white")
    draw.text((145, 450), "文件名", font=_pil_font(22, bold=True), fill="#172033")
    draw.text((650, 450), "大小", font=_pil_font(22, bold=True), fill="#172033")
    draw.text((870, 450), "处理状态", font=_pil_font(22, bold=True), fill="#172033")
    draw.line((140, 490, 1060, 490), fill="#D0D7DE", width=2)
    draw.text((145, 515), "invoice-001.pdf", font=_pil_font(22), fill="#172033")
    draw.text((650, 515), "2.4MB", font=_pil_font(22), fill="#172033")
    draw.text((870, 515), "上传成功", font=_pil_font(22), fill="#137333")
    draw.text((145, 590), "invoice-002.exe", font=_pil_font(22), fill="#172033")
    draw.text((650, 590), "1.2MB", font=_pil_font(22), fill="#172033")
    draw.text((870, 590), "格式不支持", font=_pil_font(22), fill="#B3261E")
    image.save(ASSET_DIR / "invoice_upload_ui.png")


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    build_native_text_pdf()
    build_role_matrix_docx()
    build_scanned_pdf()
    build_flow_diagram()
    build_upload_ui()
    print(f"generated 5 fixtures in {ASSET_DIR}")


if __name__ == "__main__":
    main()
