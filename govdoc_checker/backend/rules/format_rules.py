from __future__ import annotations

import re
from typing import List, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from models import Issue


def _mm_from_length(length) -> float:
    return float(length) / 914400.0 * 25.4


def _pt_from_line_spacing(value) -> Optional[float]:
    if value is None:
        return None
    try:
        # Length-like value (EMU)
        return float(value.pt)
    except Exception:
        # multiplier like 1.5
        if isinstance(value, (int, float)):
            return float(value) * 16.0
    return None


def _line_has_forbidden_space(t: str) -> bool:
    if t.strip() == "":
        return False
    return bool(re.search(r"[ \u3000\t]", t))


def _is_salutation_exception(t: str) -> bool:
    return bool(re.match(r"^各位[^。！？:：]{1,30}：$", t.strip()))


def _check_font_level(s: str) -> Optional[str]:
    s = s.strip()
    if re.match(r"^[一二三四五六七八九十]+、", s):
        return "level1"
    if re.match(r"^（[一二三四五六七八九十]+）", s):
        return "level2"
    if re.match(r"^\d+\.\s*", s):
        return "level3"
    if re.match(r"^（\d+）", s):
        return "level4"
    return "body"


def check_format_rules(docx_path: str, paragraphs: List[str]) -> List[Issue]:
    # 说明：此函数是“规则检查器”，并非排版修复器。
    # 主要输出 Issue 列表供 UI 展示与文档标注使用。
    issues: List[Issue] = []

    doc = Document(docx_path)
    sec = doc.sections[0]

    # A4 纸张检查
    w_mm = _mm_from_length(sec.page_width)
    h_mm = _mm_from_length(sec.page_height)
    if abs(w_mm - 210) > 1 or abs(h_mm - 297) > 1:
        issues.append(Issue(issue_type="版面", severity="warning", message=f"纸张幅面疑似不是A4（检测到约 {w_mm:.1f}mm×{h_mm:.1f}mm）。", suggestion="设置纸张为A4（210mm×297mm）。"))

    # 页边距检查：上3.7/下3.5/左2.8/右2.6（厘米）
    for label, val, target in [
        ("上边距", _mm_from_length(sec.top_margin), 37),
        ("下边距", _mm_from_length(sec.bottom_margin), 35),
        ("左边距", _mm_from_length(sec.left_margin), 28),
        ("右边距", _mm_from_length(sec.right_margin), 26),
    ]:
        if abs(val - target) > 1.5:
            issues.append(Issue(issue_type="页边距", severity="warning", message=f"{label}建议为{target}±1mm（检测到约 {val:.1f}mm）。", suggestion=f"将{label}设置为{target}mm左右。"))

    # 标题上下空一行检查
    raw = doc.paragraphs
    nonempty_idx = [i for i, p in enumerate(raw) if (p.text or "").strip()]
    if nonempty_idx:
        title_i = nonempty_idx[0]
        title_text = (raw[title_i].text or "").strip()
        if len(title_text) <= 40 and "：" not in title_text:
            before_ok = title_i - 1 >= 0 and (raw[title_i - 1].text or "").strip() == ""
            after_ok = title_i + 1 < len(raw) and (raw[title_i + 1].text or "").strip() == ""
            if not (before_ok and after_ok):
                issues.append(Issue(issue_type="标题", severity="error", paragraph_index=title_i, message="标题上方和下方应各空一行。", evidence=title_text, suggestion="在标题上下各插入一个空段。"))

    _add_structure_and_semantic_checks(paragraphs, issues)

    for idx, p in enumerate(raw):
        t = (p.text or "").strip()
        if not t:
            continue

        # 段末标点
        if not (t.endswith("。") or t.endswith("！") or _is_salutation_exception(t)):
            # 排除常见标题编号段
            if not re.match(r"^([一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\d+\.|（\d+）)", t):
                issues.append(Issue(issue_type="段末标点", severity="error", paragraph_index=idx, message="段落末尾应为“。”或“！”。", evidence=t[:80], suggestion="为该段补全句末标点；称谓行可用“：”。"))

        # 段内空格
        if _line_has_forbidden_space(t):
            issues.append(Issue(issue_type="空格", severity="error", paragraph_index=idx, message="段落内容中不应出现空格。", evidence=t[:80], suggestion="删除段内空格（标题上下空行除外）。"))

        # 半角标点
        if re.search(r"[,.!?;:'\"\(\)\[\]<>]", t):
            issues.append(Issue(issue_type="全半角", severity="error", paragraph_index=idx, message="检测到半角标点，公文建议统一使用全角。", evidence=t[:80], suggestion="将半角符号替换为对应全角符号。"))

        # line spacing 29pt
        pt = _pt_from_line_spacing(p.paragraph_format.line_spacing)
        if pt is None or abs(pt - 29) > 1.5:
            issues.append(Issue(issue_type="行距", severity="info", paragraph_index=idx, message="建议设置固定行距29磅。", evidence=t[:40], suggestion="将段落设置为固定值29磅行距。"))

        # first line indent 2 chars (~32pt for 3号)
        indent = p.paragraph_format.first_line_indent
        if indent is None or abs(float(indent.pt) - 32) > 3:
            if idx > 0 and not re.match(r"^([一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\d+\.|（\d+）)", t):
                issues.append(Issue(issue_type="正文缩进", severity="info", paragraph_index=idx, message="正文首行建议缩进2字符。", evidence=t[:40], suggestion="设置首行缩进2字符。"))

        # title center
        if idx == nonempty_idx[0] if nonempty_idx else False:
            if p.alignment != WD_ALIGN_PARAGRAPH.CENTER:
                issues.append(Issue(issue_type="标题", severity="error", paragraph_index=idx, message="文章标题应居中。", evidence=t, suggestion="将标题段落设置为居中对齐。"))

        # font checks (best effort)
        level = _check_font_level(t)
        expected = {
            "level1": ("方正黑体_GBK", 16),
            "level2": ("方正楷体_GBK", 16),
            "level3": ("方正仿宋_GBK", 16),
            "level4": ("方正仿宋_GBK", 16),
            "body": ("方正仿宋_GBK", 16),
        }[level]
        exp_font, exp_pt = expected
        if idx == (nonempty_idx[0] if nonempty_idx else -1):
            exp_font, exp_pt = "方正小标宋_GBK", 22

        run = p.runs[0] if p.runs else None
        if run is not None:
            rfont = (run.font.name or "")
            east = ""
            try:
                east = run._element.rPr.rFonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia") or ""
            except Exception:
                pass
            fpt = float(run.font.size.pt) if run.font.size else None
            if exp_font not in (rfont + east):
                issues.append(Issue(issue_type="字体", severity="info", paragraph_index=idx, message=f"该段字体建议为{exp_font}。", evidence=t[:40], suggestion="按公文层级调整字体。"))
            if fpt is None or abs(fpt - exp_pt) > 1:
                issues.append(Issue(issue_type="字号", severity="info", paragraph_index=idx, message=f"该段字号建议约{exp_pt}pt。", evidence=t[:40], suggestion="按公文层级调整字号。"))

    # footnote presence check
    xml = doc.part.element.xml
    if "footnoteReference" not in xml:
        issues.append(Issue(issue_type="脚注", severity="info", message="未检测到脚注。", suggestion="如文种要求，请在对应位置添加脚注。"))

    return issues


def _add_structure_and_semantic_checks(paragraphs: List[str], issues: List[Issue]) -> None:
    if not paragraphs:
        issues.append(Issue(issue_type="结构", severity="warning", message="文档内容为空，无法进行结构和语义检查。", suggestion="请补充正文后再进行审核。"))
        return

    first = paragraphs[0].strip()
    title_like = bool(re.match(r"^[\u4e00-\u9fa5A-Za-z0-9（）()《》·\s]{4,40}$", first))
    if not title_like:
        issues.append(Issue(issue_type="标题", severity="info", paragraph_index=0, message="未识别到明显标题行。", evidence=first[:80], suggestion="建议在文首补充明确标题（如“关于×××的通知”）。"))
    elif len(first) > 40 or "。" in first:
        issues.append(Issue(issue_type="标题", severity="info", paragraph_index=0, message="首段疑似不是规范标题（标题通常较短且不含句号）。", evidence=first[:80], suggestion="建议将标题单独成行，控制长度并避免句号结尾。"))

    salutation_re = re.compile(r"^(各[\u4e00-\u9fa5]{1,8}(单位|部门|处室)|你单位|你局|你处|你办)")
    for idx, t in enumerate(paragraphs[:8]):
        line = t.strip()
        if salutation_re.match(line) and not line.endswith("："):
            issues.append(Issue(issue_type="称谓", severity="warning", paragraph_index=idx, message="称谓行建议以全角冒号“：”结尾。", evidence=line[:80], suggestion="在称谓后补全全角冒号，便于与正文语义分界。"))

    body_text = "\n".join(paragraphs)
    has_attach_mention = bool(re.search(r"附件", body_text))
    has_attach_list = any(re.match(r"^附件[:：]", p.strip()) for p in paragraphs)
    if has_attach_mention and not has_attach_list:
        issues.append(Issue(issue_type="附件", severity="warning", message="正文提及“附件”，但未检测到“附件：”条目。", suggestion="补充附件清单（如“附件：1. ×××”）或删除无效引用。"))

    tail = "\n".join(paragraphs[-3:])
    if not re.search(r"\d{4}年\d{1,2}月\d{1,2}日", tail):
        issues.append(Issue(issue_type="落款日期", severity="info", message="末尾未检测到明显成文日期。", suggestion="在文末补充成文日期（如“2026年2月14日”）。"))
