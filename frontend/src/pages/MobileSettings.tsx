import { useState, useEffect } from 'react'
import { getBackendBaseUrl, setBackendUrl, testBackendConnection, isNativePlatform } from '../services/capacitorConfig'
import { PageSection, LoadingSpinner } from '../components/ui'

export default function MobileSettings() {
  const [backendUrl, setBackendUrlState] = useState('')
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getBackendBaseUrl().then(url => setBackendUrlState(url))
  }, [])

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    const result = await testBackendConnection(backendUrl)
    setTestResult(result)
    setTesting(false)
  }

  const handleSave = async () => {
    await setBackendUrl(backendUrl)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  if (!isNativePlatform()) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: '#8b949e' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>💻</div>
        <div style={{ fontSize: 16, color: '#e6edf3', marginBottom: 8 }}>当前为Web模式</div>
        <div style={{ fontSize: 13 }}>后端地址由Vite代理自动处理，无需手动配置</div>
      </div>
    )
  }

  return (
    <div style={{ padding: 20, maxWidth: 480, margin: '0 auto' }}>
      <h2 style={{ fontSize: 18, color: '#e6edf3', marginBottom: 8 }}>⚙️ 服务器配置</h2>
      <p style={{ fontSize: 13, color: '#8b949e', marginBottom: 24 }}>
        配置后端服务器地址。请确保手机和服务器在同一局域网内，或使用公网地址。
      </p>

      <div style={{ marginBottom: 20 }}>
        <label style={{ display: 'block', fontSize: 13, color: '#8b949e', marginBottom: 8, fontWeight: 600 }}>
          后端服务器地址
        </label>
        <input
          type="text"
          value={backendUrl}
          onChange={e => setBackendUrlState(e.target.value)}
          placeholder="http://192.168.1.100:8002"
          style={{
            width: '100%',
            padding: '12px 14px',
            background: '#0d1117',
            border: '1px solid #30363d',
            borderRadius: 6,
            color: '#e6edf3',
            fontSize: 14,
            boxSizing: 'border-box',
          }}
        />
        <div style={{ fontSize: 11, color: '#484f58', marginTop: 6 }}>
          示例: http://192.168.1.100:8002 或 http://your-server.com:8002
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <button
          onClick={handleTest}
          disabled={testing || !backendUrl}
          style={{
            flex: 1,
            padding: '12px',
            background: testing ? '#30363d' : 'rgba(88,166,255,0.15)',
            border: '1px solid #58a6ff',
            borderRadius: 6,
            color: '#58a6ff',
            fontSize: 14,
            fontWeight: 600,
            cursor: testing ? 'wait' : 'pointer',
          }}
        >
          {testing ? '测试中...' : '🔗 测试连接'}
        </button>
        <button
          onClick={handleSave}
          disabled={!backendUrl}
          style={{
            flex: 1,
            padding: '12px',
            background: saved ? '#16a34a' : 'linear-gradient(135deg, #58a6ff 0%, #1f6feb 100%)',
            border: 'none',
            borderRadius: 6,
            color: '#fff',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {saved ? '✓ 已保存' : '💾 保存配置'}
        </button>
      </div>

      {testResult && (
        <div style={{
          padding: 12,
          background: testResult.success ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)',
          border: `1px solid ${testResult.success ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)'}`,
          borderRadius: 6,
          color: testResult.success ? '#3fb950' : '#f85149',
          fontSize: 13,
          marginBottom: 20,
        }}>
          {testResult.success ? '✅ ' : '❌ '}{testResult.message}
        </div>
      )}

      <div style={{
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: 8,
        padding: 16,
      }}>
        <div style={{ fontSize: 13, color: '#e6edf3', fontWeight: 600, marginBottom: 12 }}>📋 使用说明</div>
        <div style={{ fontSize: 12, color: '#8b949e', lineHeight: 2 }}>
          <div>1. 在电脑上启动后端服务：<code style={{ color: '#58a6ff', background: '#0d1117', padding: '2px 6px', borderRadius: 3 }}>cd backend && python -m uvicorn app.main:app --port 8002 --host 0.0.0.0</code></div>
          <div>2. 注意必须加 <code style={{ color: '#58a6ff', background: '#0d1117', padding: '2px 6px', borderRadius: 3 }}>--host 0.0.0.0</code> 才能从手机访问</div>
          <div>3. 查看电脑IP地址（ipconfig），填入上面的地址框</div>
          <div>4. 确保手机和电脑连接同一个WiFi网络</div>
          <div>5. 点击"测试连接"验证，成功后点击"保存配置"</div>
        </div>
      </div>
    </div>
  )
}
