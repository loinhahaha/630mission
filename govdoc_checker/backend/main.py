from __future__ import annotations

import io
import os
import tempfile
from urllib.parse import quote

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from pipeline import analyze as run_pipeline
from pipeline import polish_text as run_polish_text

# FastAPI 主应用：仅暴露健康检查与分析接口
app = FastAPI(title="govdoc_checker")

# Allow local front-end dev servers to call the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_content_disposition(filename: str) -> str:
    encoded_name = quote(filename)
    return f"attachment; filename=annotated.docx; filename*=UTF-8''{encoded_name}"



def _has_agent_failure(agent_notes: list[dict] | None) -> bool:
    if not agent_notes:
        return False
    hints = ("大模型调用失败", "未配置智能体鉴权参数", "stream_error", "http_error", "sync_no_answer")
    joined = str(agent_notes)
    return any(h in joined for h in hints)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze")
async def analyze(
    mode: str = Form(..., description="text|file"),
    text: str = Form("", description="纯文本输入"),
    file: UploadFile = File(None),
    do_format_check: bool = Form(True),
    do_punct_check: bool = Form(True),
    do_polish: bool = Form(False),
    max_chunk_chars: int = Form(1200),
):
    """返回标记后的文档（docx）"""
    try:
        with tempfile.TemporaryDirectory() as td:
            file_path = None
            if mode == "file":
                if file is None:
                    return JSONResponse({"error": "mode=file 时必须上传文件"}, status_code=400)
                file_path = os.path.join(td, file.filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())

            result = run_pipeline(
                mode=mode,
                text=text,
                file_path=file_path,
                do_format_check=do_format_check,
                do_punct_check=do_punct_check,
                do_polish=do_polish,
                max_chunk_chars=max_chunk_chars,
            )

            doc_buf = io.BytesIO(result.get("download_bytes") or result["annotated_bytes"])
            doc_buf.seek(0)
            return StreamingResponse(
                doc_buf,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": build_content_disposition(result.get("download_filename", "标记后文档.docx"))},
            )
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"服务内部错误：{e}"}, status_code=500)


@app.post("/polish")
async def polish(
    text: str = Form("", description="待润色文本"),
    max_chunk_chars: int = Form(1200),
):
    """Return polished plain text for the dedicated polish workspace."""
    try:
        if not (text or "").strip():
            return JSONResponse({"error": "请先输入需要润色的文本"}, status_code=400)
        revised_text, agent_notes = run_polish_text(text, max_chunk_chars=max_chunk_chars)
        if _has_agent_failure(agent_notes):
            return JSONResponse(
                {
                    "error": "润色模型调用失败",
                    "revised_text": revised_text,
                    "agent_notes": agent_notes,
                },
                status_code=502,
            )
        return JSONResponse(
            {
                "revised_text": revised_text,
                "agent_notes": agent_notes,
            },
            status_code=200,
        )
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"服务内部错误：{e}"}, status_code=500)
