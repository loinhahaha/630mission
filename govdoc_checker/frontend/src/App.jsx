import React, { useMemo, useState } from 'react'
import './app.css'

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

async function requestWithFallback(path, options) {
  const requestUrls = [
    path,
    `http://localhost:8000${path}`,
    `http://127.0.0.1:8000${path}`,
  ]

  if (window.location.hostname && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    requestUrls.push(`${window.location.protocol}//${window.location.hostname}:8000${path}`)
  }

  const attemptLogs = []
  let res
  let lastError
  for (const url of requestUrls) {
    try {
      res = await fetch(url, options)
      attemptLogs.push(`✅ ${url} -> HTTP ${res.status}`)
      // Vite proxy may return 404 for unconfigured relative API paths.
      // If that happens on the first relative path, continue fallback to direct backend URLs.
      if (url === path && res.status === 404) {
        attemptLogs.push(`↪️ ${url} 返回 404，继续尝试直连后端地址`) 
        continue
      }
      break
    } catch (error) {
      lastError = error
      attemptLogs.push(`❌ ${url} -> ${error?.message || 'Failed to fetch'}`)
    }
  }

  if (!res) {
    const err = new Error('无法连接后端服务，请确认服务已启动。')
    err.debugInfo = [
      `尝试地址：${requestUrls.join(' / ')}`,
      ...attemptLogs,
      `最终错误：${lastError?.message || 'Failed to fetch'}`,
      '排查建议：检查后端 8000 端口与 /health 接口。',
    ].join('\n')
    throw err
  }

  return { res, attemptLogs }
}

export default function App() {
  const [view, setView] = useState('check')

  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [debugInfo, setDebugInfo] = useState('')
  const [doFormatCheck, setDoFormatCheck] = useState(true)
  const [doPunctCheck, setDoPunctCheck] = useState(true)

  const [polishInput, setPolishInput] = useState('')
  const [polishOutput, setPolishOutput] = useState('')
  const [polishBusy, setPolishBusy] = useState(false)
  const [polishStage, setPolishStage] = useState('')
  const [polishMsg, setPolishMsg] = useState('')
  const [polishDebug, setPolishDebug] = useState('')

  const canSubmit = useMemo(() => {
    if (busy) return false
    if (!doFormatCheck && !doPunctCheck) return false
    if (mode === 'text') return (text || '').trim().length > 0
    return !!file
  }, [busy, mode, text, file, doFormatCheck, doPunctCheck])

  const canPolish = useMemo(() => !polishBusy && (polishInput || '').trim().length > 0, [polishBusy, polishInput])

  async function onSubmit() {
    setBusy(true)
    setMsg('正在处理，请稍候…')
    setDebugInfo('')
    try {
      const fd = new FormData()
      fd.append('mode', mode)
      fd.append('text', mode === 'text' ? text : '')
      if (mode === 'file' && file) fd.append('file', file)
      fd.append('do_format_check', String(doFormatCheck))
      fd.append('do_punct_check', String(doPunctCheck))
      fd.append('do_polish', 'false')

      const { res } = await requestWithFallback('/analyze', { method: 'POST', body: fd })

      if (!res.ok) {
        let detail = ''
        const contentType = res.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          const json = await res.json()
          detail = json?.error || json?.detail || JSON.stringify(json)
        } else {
          detail = await res.text()
        }
        throw new Error(detail || '请求失败')
      }

      const blob = await res.blob()
      const fallback = `${(file?.name || '文本输入').replace(/\.(docx?|txt)$/i, '')}-检查后文档.docx`
      const disposition = res.headers.get('content-disposition') || ''
      const match = disposition.match(/filename\*=UTF-8''([^;]+)/)
      const filename = match ? decodeURIComponent(match[1]) : fallback
      downloadBlob(blob, filename)
      setMsg(`处理完成：已下载 ${filename}`)
    } catch (e) {
      setMsg('处理失败：' + (e?.message || String(e)))
      setDebugInfo(e?.debugInfo || e?.stack || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function onPolish() {
    setPolishBusy(true)
    setPolishMsg('正在启动润色…')
    setPolishDebug('')
    setPolishStage('正在分段处理中，请稍候…')
    try {
      const fd = new FormData()
      fd.append('text', polishInput)
      fd.append('max_chunk_chars', '1200')

      const { res, attemptLogs } = await requestWithFallback('/polish', { method: 'POST', body: fd })
      setPolishStage('模型处理中…')

      if (!res.ok) {
		  let detail = ''
		  let agentNotes = null
		  let revisedText = ''
		  const contentType = res.headers.get('content-type') || ''

		  if (contentType.includes('application/json')) {
			const json = await res.json()
			detail = json?.error || json?.detail || JSON.stringify(json)
			agentNotes = json?.agent_notes || null
			revisedText = json?.revised_text || ''
		  } else {
			detail = await res.text()
		  }

		  const isRouteMissing = res.status === 404
		  const err = new Error(
			isRouteMissing
			  ? '润色接口不存在（/polish）。请重启后端，或确认启动的是最新代码。'
			  : (detail || `润色失败（HTTP ${res.status}）`)
		  )

		  err.debugInfo = [
			`请求路径：/polish`,
			`HTTP 状态：${res.status}`,
			...attemptLogs,
			agentNotes ? '' : '',
			agentNotes ? 'agent_notes:' : '',
			agentNotes ? JSON.stringify(agentNotes, null, 2) : '',
			revisedText ? '' : '',
			revisedText ? 'revised_text:' : '',
			revisedText ? revisedText : '',
			isRouteMissing
			  ? '排查建议：1) 检查 backend/main.py 是否包含 @app.post("/polish")；2) 重启 uvicorn；3) 检查 Vite 代理是否包含 /polish。'
			  : '',
		  ].filter(Boolean).join('\n')

		  throw err
		}

      const json = await res.json()
      const revisedText = json?.revised_text || ''
      const agentNotes = json?.agent_notes || []
      const notesStr = JSON.stringify(agentNotes)
      const hasAgentFailure = notesStr.includes('大模型调用失败') || notesStr.includes('未配置智能体鉴权参数')

      setPolishOutput(revisedText)
      if (hasAgentFailure) {
        setPolishMsg('润色失败：模型接口未成功返回可用结果')
        setPolishStage('')
        setPolishDebug([
          ...attemptLogs,
          '',
          'agent_notes:',
          JSON.stringify(agentNotes, null, 2),
        ].join('\n'))
        return
      }

      setPolishStage('润色完成，可复制或继续修改。')
      setPolishMsg('润色已完成')
      setPolishDebug(attemptLogs.join('\n'))
    } catch (e) {
      setPolishMsg('润色失败：' + (e?.message || String(e)))
      setPolishDebug(e?.debugInfo || e?.stack || String(e))
      setPolishStage('')
    } finally {
      setPolishBusy(false)
    }
  }

  if (view === 'polish') {
    return (
      <div className="page">
        <div className="bg bg-1" />
        <div className="bg bg-2" />
        <div className="bg bg-3" />

        <main className="layout polish-layout">
          <section className="hero card">
            <p className="eyebrow">GovDoc Rewriter</p>
            <h1>公文润色工坊</h1>
            <p className="desc">将原文粘贴到左侧，点击“开始润色”，右侧将显示优化后的版本。适合先润色再返回主页做格式与标点校核。</p>
            <ul className="feature-list">
              <li>仅支持文本输入，长文会自动分段处理</li>
              <li>润色过程含动态状态提示</li>
              <li>结果可直接复制，再用于下一步校核</li>
            </ul>
            <button className="ghost-btn" onClick={() => setView('check')}>← 返回校核主页</button>
          </section>

          <section className="card panel polish-panel">
            <div className="panel-head">
              <h2>AI 润色工作区</h2>
              <span className="badge">文本专用</span>
            </div>

            <div className="split-editor">
              <label className="input-block">
                <span>原文输入</span>
                <textarea
                  value={polishInput}
                  onChange={(e) => setPolishInput(e.target.value)}
                  placeholder="请粘贴待润色的正文..."
                  className="text"
                />
              </label>
              <label className="input-block">
                <span>润色结果</span>
                <textarea
                  value={polishOutput}
                  readOnly
                  placeholder="润色结果将显示在这里"
                  className="text output"
                />
              </label>
            </div>

            <button disabled={!canPolish} onClick={onPolish} className="btn">
              {polishBusy ? <span className="spinner" /> : '开始润色'}
            </button>
            <p className="msg">{polishMsg || '提示：长文将自动分段调用模型，请耐心等待。'}</p>
            {polishStage ? <p className="msg status">{polishStage}</p> : null}
            {polishDebug ? <pre className="msg" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{polishDebug}</pre> : null}
          </section>
        </main>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="bg bg-1" />
      <div className="bg bg-2" />
      <div className="bg bg-3" />

      <main className="layout">
        <section className="hero card">
          <p className="eyebrow">GovDoc Checker</p>
          <h1>公文智能校核工作台</h1>
          <p className="desc">面向公文场景的格式与标点智能校核系统，支持文本/Word 输入，生成高亮标注文档，便于快速复核与定稿。</p>

          <ul className="feature-list">
            <li>格式检查：标题、段落缩进、版面等规则校核</li>
            <li>标点检查：重复标点、引号搭配与全半角问题</li>
            <li>结果输出：自动下载“检查后文档”用于逐条复核</li>
          </ul>

          <div className="guide-box">
            <h3>使用方法</h3>
            <ol>
              <li>选择“粘贴文本”或“上传 Word”。</li>
              <li>勾选需要执行的检查项。</li>
              <li>点击“开始审核并下载结果”。</li>
              <li>如需文字优化，进入右下角“公文润色工坊”。</li>
            </ol>
          </div>

          <button className="ghost-btn" onClick={() => setView('polish')}>进入公文润色工坊 →</button>
        </section>

        <section className="card panel">
          <div className="panel-head">
            <h2>发起审核</h2>
            <span className="badge">实时校核</span>
          </div>

          <div className="mode-switch">
            <button className={`mode-btn ${mode === 'text' ? 'active' : ''}`} onClick={() => setMode('text')}>粘贴文本</button>
            <button className={`mode-btn ${mode === 'file' ? 'active' : ''}`} onClick={() => setMode('file')}>上传 Word</button>
          </div>

          {mode === 'text' ? (
            <label className="input-block">
              <span>公文正文</span>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="请粘贴待审核的公文正文..."
                className="text"
              />
            </label>
          ) : (
            <label className="upload" htmlFor="file-input">
              <input
                id="file-input"
                type="file"
                accept=".doc,.docx"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <strong>{file ? file.name : '点击上传 .doc / .docx'}</strong>
              <p>建议优先上传 .docx；.doc 需环境安装 LibreOffice。</p>
            </label>
          )}

          <div className="checks">
            <label className="check-item">
              <input type="checkbox" checked={doFormatCheck} onChange={(e) => setDoFormatCheck(e.target.checked)} />
              <span>格式检查（版面、标题、缩进、行距、页边距等）</span>
            </label>
            <label className="check-item">
              <input type="checkbox" checked={doPunctCheck} onChange={(e) => setDoPunctCheck(e.target.checked)} />
              <span>标点检查（重复标点、引号规则、全半角等）</span>
            </label>
          </div>

          <button disabled={!canSubmit} onClick={onSubmit} className="btn">
            {busy ? <span className="spinner" /> : '开始审核并下载结果'}
          </button>

          <p className="msg">{msg || '系统将返回标注后文档（高亮 + 批注），便于快速复核。'}</p>
          {debugInfo ? <pre className="msg" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{debugInfo}</pre> : null}
        </section>
      </main>
    </div>
  )
}
