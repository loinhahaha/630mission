from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional

from models import Issue
from docx_utils import (
    load_input_as_docx,
    extract_docx_text,
    build_final_docx_from_text,
    build_annotated_original_docx,
)
from rules.format_rules import check_format_rules
from rules.punct_rules import check_punctuation_rules

from text_slicer import slice_text
from agent_client import call_agent_and_normalize


def analyze(
    *,
    mode: str,
    text: str = "",
    file_path: Optional[str] = None,
    do_format_check: bool = True,
    do_punct_check: bool = True,
    do_polish: bool = False,
    max_chunk_chars: int = 1200,
) -> Dict[str, Any]:
    """
    返回：
      - annotated_bytes: bytes（兼容旧调用方）
      - download_bytes: bytes（建议下载内容）
      - download_filename: str
      - report: dict
      - issues: List[Issue]
      - files: dict[str, bytes]
    """
    with tempfile.TemporaryDirectory() as td:
        if mode == "file":
            if not file_path:
                raise ValueError("mode=file 时必须提供 file_path")
            docx_path = load_input_as_docx(file_path, td)
        else:
            docx_path = build_final_docx_from_text(text, os.path.join(td, "input_from_text.docx"), as_input=True)

        paragraphs = extract_docx_text(docx_path)
        full_text = "\n".join(paragraphs).strip()

        issues: List[Issue] = []
        if do_format_check:
            issues.extend(check_format_rules(docx_path, paragraphs))
        if do_punct_check:
            issues.extend(check_punctuation_rules(paragraphs))

        revised_text = full_text
        agent_notes: List[dict] = []
        if do_polish and full_text:
            revised_text, agent_notes = polish_text(full_text, max_chunk_chars=max_chunk_chars)

        annotated_docx_path = os.path.join(td, "标记后文档.docx")
        build_annotated_original_docx(docx_path, issues, annotated_docx_path)
        with open(annotated_docx_path, "rb") as f:
            annotated_bytes = f.read()

        files: Dict[str, bytes] = {"标记后文档.docx": annotated_bytes}
        download_filename = "标记后文档.docx"
        download_bytes = annotated_bytes

        if do_polish and revised_text and revised_text != full_text:
            polished_docx_path = os.path.join(td, "润色后文档.docx")
            build_final_docx_from_text(revised_text, polished_docx_path, as_input=True)
            with open(polished_docx_path, "rb") as f:
                polished_bytes = f.read()
            files["润色后文档.docx"] = polished_bytes
            download_filename = "润色后文档.docx"
            download_bytes = polished_bytes

        report = {
            "issues": [i.model_dump() for i in issues],
            "agent_notes": agent_notes,
        }

        return {
            "annotated_bytes": annotated_bytes,
            "download_bytes": download_bytes,
            "download_filename": download_filename,
            "report": report,
            "issues": issues,
            "files": files,
            "revised_text": revised_text,
        }


def polish_text(text: str, *, max_chunk_chars: int = 1200) -> tuple[str, List[dict]]:
    """Polish plain text chunk-by-chunk and return revised text with model notes."""
    source_text = (text or "").strip()
    if not source_text:
        return "", []

    chunks = slice_text(source_text, max_chars=max_chunk_chars)
    revised_chunks: List[str] = []
    agent_notes: List[dict] = []
    for idx, chunk in enumerate(chunks):
        res = call_agent_and_normalize(chunk)
        revised_chunks.append(res["revised_text"])
        if res.get("notes"):
            agent_notes.append({"chunk_index": idx, "notes": res["notes"]})

    revised_text = "\n".join([c.strip() for c in revised_chunks if c.strip()]).strip() or source_text
    return revised_text, agent_notes
