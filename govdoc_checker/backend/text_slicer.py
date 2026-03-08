\
from __future__ import annotations

from typing import List


def slice_text(text: str, max_chars: int = 1200) -> List[str]:
    """
    按段落切片，保证每片不超过 max_chars（尽量不切断段落）。
    """
    paras = [p.strip() for p in (text or "").splitlines()]
    paras = [p for p in paras if p != ""]
    chunks: List[str] = []
    buf: List[str] = []
    size = 0
    for p in paras:
        if size + len(p) + 1 > max_chars and buf:
            chunks.append("\n".join(buf))
            buf = [p]
            size = len(p) + 1
        else:
            buf.append(p)
            size += len(p) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks
