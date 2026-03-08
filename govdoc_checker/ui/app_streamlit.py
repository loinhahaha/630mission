# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
from datetime import datetime

import streamlit as st

# 让 Streamlit 能 import backend 模块
import sys
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline import analyze

st.set_page_config(page_title="公文格式审核工具", page_icon="🧾", layout="wide")

st.markdown("""
<style>
:root { color-scheme: light; }
.main-title { font-weight: 800; letter-spacing: .5px; margin-bottom: 4px; }
.subtitle { color:#4b5563; margin-bottom: 16px; }
.card {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 18px 18px 12px 18px;
  background: linear-gradient(180deg,#ffffff 0%,#fcfcfd 100%);
  box-shadow: 0 10px 30px rgba(15,23,42,.06);
}
.hr { height: 1px; background: #f1f1f1; margin: 10px 0 12px 0; }
.issue-list-tip { color:#666; font-size:12px; margin-top:4px; }
</style>
""", unsafe_allow_html=True)

st.title("🧾 公文格式审核工具")
st.caption("支持上传 .doc/.docx 或粘贴文本；输出检查后文档（docx）并在页面展示问题列表。")

left, right = st.columns([1.05, 0.95], gap="large")

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("输入")

    input_mode = st.radio("输入方式", ["📄 上传 Word", "📝 粘贴文本"], horizontal=True)
    uploaded = None
    text = ""
    mode = "file"

    if input_mode.startswith("📄"):
        mode = "file"
        uploaded = st.file_uploader("选择 Word 文件（.docx / .doc）", type=["docx", "doc"])
        st.markdown('<div class="small">上传 .doc 需要安装 LibreOffice（soffice）。</div>', unsafe_allow_html=True)
    else:
        mode = "text"
        text = st.text_area("粘贴公文正文", height=280, placeholder="在此粘贴公文正文……")

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.subheader("检测项")
    do_format = st.checkbox("格式检查（版面、标题、缩进、行距、页边距等）", value=True)
    do_punct = st.checkbox("标点检查（重复标点、引号规则、全半角等）", value=True)

    run = st.button("🚀 开始审核", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("输出")
    st.markdown('<span class="badge">检查后文档（.docx）</span>', unsafe_allow_html=True)
    st.markdown('<div class="small">不再打包 zip；直接下载 docx，问题列表在下方查看。</div>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    if "last_result" not in st.session_state:
        st.session_state["last_result"] = None

    if run:
        if uploaded is None and mode == "file":
            st.warning("请先上传 Word 文件，或切换到“粘贴文本”。")
        elif mode == "text" and (not text.strip()):
            st.warning("请先粘贴文本，或切换到“上传 Word”。")
        else:
            with st.spinner("处理中，请稍候..."):
                try:
                    if uploaded is not None and mode == "file":
                        with tempfile.TemporaryDirectory() as td:
                            fp = os.path.join(td, uploaded.name)
                            with open(fp, "wb") as f:
                                f.write(uploaded.getbuffer())
                            result = analyze(mode="file", file_path=fp, do_format_check=do_format, do_punct_check=do_punct, do_polish=False)
                    else:
                        result = analyze(mode="text", text=text, do_format_check=do_format, do_punct_check=do_punct, do_polish=False)
                    st.session_state["last_result"] = result
                except Exception as e:
                    st.error(f"处理失败：{e}")

    result = st.session_state.get("last_result")
    if result:
        issues = result["report"]["issues"]
        n_err = sum(1 for i in issues if i.get("severity") == "error")
        n_warn = sum(1 for i in issues if i.get("severity") == "warning")
        n_info = sum(1 for i in issues if i.get("severity") == "info")
        st.markdown(f'<div class="issue-stat">❌ 错误 <b>{n_err}</b> &nbsp;&nbsp; ⚠️ 警告 <b>{n_warn}</b> &nbsp;&nbsp; ℹ️ 提示 <b>{n_info}</b></div>', unsafe_allow_html=True)

        st.markdown(f"**问题统计：** ❌错误 {n_err} | ⚠️警告 {n_warn} | ℹ️提示 {n_info}")
        st.markdown('<div class="issue-list-tip">错误=硬性规则不满足；警告=高风险不规范；提示=优化建议。若错误为0，说明未触发硬性规则，但仍可能有警告/提示。</div>', unsafe_allow_html=True)

        with st.expander("查看问题列表（按段落定位）", expanded=True):
            if not issues:
                st.success("未发现明显问题（基于当前规则集）。")
            else:
                with st.container(height=420):
                    for it in issues[:200]:
                        idx = it.get("paragraph_index")
                        loc = f"第 {idx+1} 段" if isinstance(idx, int) else "全局"
                        st.write(f"- **[{it.get('severity')}] {it.get('issue_type')}**（{loc}）：{it.get('message')}")
                        if it.get("evidence"):
                            st.code(it["evidence"], language="text")
                        if it.get("suggestion"):
                            st.caption("建议：" + it["suggestion"])

        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        marked = result["files"]["标记后文档.docx"]
        st.download_button(
            label="⬇️ 下载检查后文档.docx",
            data=marked,
            file_name=f"检查后文档_{now}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    else:
        st.info("还没有生成结果。请在左侧输入并点击“开始审核”。")

    st.markdown('</div>', unsafe_allow_html=True)
