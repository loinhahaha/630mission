from __future__ import annotations

import re
from typing import List, Iterable

from models import Issue

# 连续重复标点（如：。。、！！、——）
REPEAT_PUNCT_RE = re.compile(r"([，。！？；：、\-—《》“”‘’])\1+")
# 中英文标点混用（如：，, 或 ,。）
MIXED_PUNCT_RE = re.compile(r"(?:[，。！？；：、][,.;:!?]|[,.;:!?][，。！？；：、])")
SPACE_AROUND_CN_PUNCT_RE = re.compile(r"(?:\s+[，。！？；：、]|[，。！？；：、]\s+)")
ELLIPSIS_RE = re.compile(r"(?:\.{2,}|…{1,})")
# 并列引号间不应出现任何标点：“内容1”“内容2”才是允许形式
QUOTE_CHAIN_WITH_PUNCT_RE = re.compile(r"“[^”]{1,80}”[，。！？；：、,.!?;:]+“[^”]{1,80}”")

CN_PAREN_OPEN, CN_PAREN_CLOSE = "（", "）"
EN_PAREN_OPEN, EN_PAREN_CLOSE = "(", ")"
CN_QUOTE_OPEN, CN_QUOTE_CLOSE = "“", "”"


def check_punctuation_rules(paragraphs: List[str], *, per_para_cap: int = 20) -> List[Issue]:
    issues: List[Issue] = []
    for idx, t in enumerate(paragraphs):
        if not t:
            continue

        _add_iter_issues(
            issues, idx, t, REPEAT_PUNCT_RE.finditer(t),
            issue_type="标点", severity="error",
            message_tpl="疑似存在连续重复符号：{m0}。",
            suggestion="删除多余的重复符号（通常保留1个）。", cap=per_para_cap,
        )

        _add_iter_issues(
            issues, idx, t, MIXED_PUNCT_RE.finditer(t),
            issue_type="标点", severity="info",
            message_tpl="疑似存在中英文标点混用：{m0}。",
            suggestion="统一使用中文全角标点（或统一英文半角标点），避免混用。", cap=per_para_cap,
        )

        _add_iter_issues(
            issues, idx, t, SPACE_AROUND_CN_PUNCT_RE.finditer(t),
            issue_type="空格", severity="info",
            message_tpl="中文标点前后存在多余空格：{m0!r}。",
            suggestion="删除中文标点前后的多余空格。", cap=per_para_cap,
        )

        _add_iter_issues(
            issues, idx, t, QUOTE_CHAIN_WITH_PUNCT_RE.finditer(t),
            issue_type="引号", severity="error",
            message_tpl="并列引号内容之间不应加标点：{m0}。",
            suggestion="改为“内容1”“内容2”或按句意拆分。", cap=per_para_cap,
        )

        for k, m in enumerate(ELLIPSIS_RE.finditer(t)):
            if k >= per_para_cap:
                issues.append(Issue(issue_type="标点", severity="info", paragraph_index=idx, message=f"该段省略号/点串问题较多，已仅展示前 {per_para_cap} 处。", evidence=t[:120], suggestion="建议按单位规范统一省略号写法（常见为“……”6点）。"))
                break
            s = m.group(0)
            if s in ("……", "......", "...", "...."):
                continue
            issues.append(Issue(issue_type="标点", severity="info", paragraph_index=idx, message="省略号用法可能不规范。", evidence=_clip(t, m.start(), m.end()), suggestion="建议使用中文省略号“……”（6点）或按单位规范统一。"))

        if t.count(CN_PAREN_OPEN) != t.count(CN_PAREN_CLOSE):
            issues.append(Issue(issue_type="括号", severity="warning", paragraph_index=idx, message=f"中文圆括号疑似未配对（“{CN_PAREN_OPEN}”与“{CN_PAREN_CLOSE}”数量不一致）。", evidence=t[:120], suggestion="检查并补全缺失的中文圆括号。"))

        if t.count(EN_PAREN_OPEN) != t.count(EN_PAREN_CLOSE):
            issues.append(Issue(issue_type="括号", severity="warning", paragraph_index=idx, message=f"英文圆括号疑似未配对（“{EN_PAREN_OPEN}”与“{EN_PAREN_CLOSE}”数量不一致）。", evidence=t[:120], suggestion="检查并补全缺失的英文圆括号。"))

        if t.count(CN_QUOTE_OPEN) != t.count(CN_QUOTE_CLOSE):
            issues.append(Issue(issue_type="引号", severity="warning", paragraph_index=idx, message=f"中文引号疑似未配对（“{CN_QUOTE_OPEN}”与“{CN_QUOTE_CLOSE}”数量不一致）。", evidence=t[:120], suggestion="检查并补全缺失的中文引号。"))

    return issues


def _add_iter_issues(
    issues: List[Issue], paragraph_index: int, text: str, it: Iterable[re.Match], *,
    issue_type: str, severity: str, message_tpl: str, suggestion: str, cap: int,
) -> None:
    for k, m in enumerate(it):
        if k >= cap:
            issues.append(Issue(issue_type=issue_type, severity=severity, paragraph_index=paragraph_index, message=f"该段 {issue_type} 问题较多，已仅展示前 {cap} 处。", evidence=text[:120], suggestion=suggestion))
            break
        issues.append(Issue(issue_type=issue_type, severity=severity, paragraph_index=paragraph_index, message=message_tpl.format(m0=m.group(0)), evidence=m.group(0), suggestion=suggestion))


def _clip(text: str, start: int, end: int, window: int = 24) -> str:
    s = max(0, start - window)
    e = min(len(text), end + window)
    return text[s:e]
