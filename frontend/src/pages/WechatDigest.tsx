/**
 * 微信公众号日报
 * 四个标签页：每日日报 / 公众号管理 / 文章列表 / 添加文章
 */
import { useState, useEffect, useCallback } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { PageSection, TabBar, LoadingSpinner, EmptyState } from '../components/ui'
import { wechatDigestApi } from '../services/api'

// ==================== 类型 ====================

interface DigestArticle {
  title: string; url: string; publishedAt: number; publishedDate: string
  summary: string; keyPoints: string[]; mpName: string
}
interface DigestGroup {
  mpName: string; mpId: string; count: number; items: DigestArticle[]
}
interface DailyDigest {
  title: string; date: string; groups: DigestGroup[]
  totalArticles: number; totalAccounts: number; update_time: string
}
interface Account { mpId: string; name: string; lastSync: string; articleCount: number }
interface Article {
  title: string; url: string; publishedAt: number; fetchedAt: number
  content: string; mpId: string; mpName: string; summary: string
}

const TABS = [
  { key: 'digest', label: '每日日报', icon: '📰' },
  { key: 'add', label: '添加文章', icon: '➕' },
  { key: 'accounts', label: '公众号管理', icon: '📋' },
  { key: 'articles', label: '文章列表', icon: '📖' },
  { key: 'settings', label: '设置', icon: '⚙️' },
]

function fmt(ts?: number): string {
  if (!ts) return ''
  try { return new Date(ts * 1000).toLocaleDateString('zh-CN') } catch { return '' }
}
function relTime(ts?: number): string {
  if (!ts) return ''
  try {
    const d = Date.now() - ts * 1000
    if (d < 60000) return '刚刚'
    if (d < 3600000) return `${Math.floor(d / 60000)}分钟前`
    if (d < 86400000) return `${Math.floor(d / 3600000)}小时前`
    return `${Math.floor(d / 86400000)}天前`
  } catch { return '' }
}

// ==================== 主组件 ====================

export default function WechatDigest() {
  const [tab, setTab] = useState('digest')
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null)

  useEffect(() => {
    wechatDigestApi.getLoginStatus()
      .then(res => setLoggedIn(res.data.logged_in))
      .catch(() => setLoggedIn(false))
  }, [])

  if (loggedIn === null) return <PageSection title="📰 微信公众号日报"><LoadingSpinner text="加载中..." /></PageSection>
  if (!loggedIn) return <PageSection title="📰 微信公众号日报"><LoginPanel onSuccess={() => setLoggedIn(true)} /></PageSection>

  return (
    <PageSection title="📰 微信公众号日报" extra={<button onClick={async () => { await wechatDigestApi.logout(); setLoggedIn(false) }} style={btnS}>退出</button>}>
      <TabBar tabs={TABS} activeKey={tab} onChange={setTab} style={{ marginBottom: 16 }} />
      {tab === 'digest' && <DigestTab />}
      {tab === 'add' && <AddArticleTab />}
      {tab === 'accounts' && <AccountsTab />}
      {tab === 'articles' && <ArticlesTab />}
      {tab === 'settings' && <SettingsTab />}
    </PageSection>
  )
}

// ==================== 登录 ====================

function LoginPanel({ onSuccess }: { onSuccess: () => void }) {
  const [step, setStep] = useState<'init' | 'qr'>('init')
  const [qrUrl, setQrUrl] = useState('')
  const [error, setError] = useState('')
  const [sec, setSec] = useState(0)
  const pollRef = { current: 0 as any }

  const handleLogin = useCallback(async () => {
    setError(''); setSec(0)
    try {
      const res = await wechatDigestApi.loginStart()
      setQrUrl(res.data.qr_url)
      setStep('qr')
      let count = 0
      pollRef.current = setInterval(async () => {
        count++; setSec(count * 2)
        if (count > 90) { clearInterval(pollRef.current); setError('超时'); setStep('init'); return }
        try {
          const r = await wechatDigestApi.loginCheck(res.data.uuid)
          if (r.data.status === 'ok') { clearInterval(pollRef.current); onSuccess() }
        } catch {}
      }, 2000)
    } catch (e: any) { setError(e.message || '登录失败') }
  }, [onSuccess])

  useEffect(() => () => clearInterval(pollRef.current), [])

  return (
    <div style={{ textAlign: 'center', padding: '40px 0' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>📱</div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>登录微信读书</h3>
      <p style={{ color: 'var(--text-muted)', marginBottom: 24, fontSize: 13 }}>通过微信读书 API 获取公众号文章</p>
      {error && <div style={{ color: '#f85149', marginBottom: 16, fontSize: 13 }}>{error}</div>}
      {step === 'init' && <button onClick={handleLogin} style={btnP}>🔐 扫码登录</button>}
      {step === 'qr' && (
        <div>
          <div style={{ background: '#fff', borderRadius: 12, padding: 16, display: 'inline-block', marginBottom: 16 }}>
            {qrUrl && <QRCodeSVG value={qrUrl} size={240} level="M" />}
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>请用微信扫描二维码</p>
          <LoadingSpinner text={`等待扫码... ${sec}s`} size="small" />
        </div>
      )}
    </div>
  )
}

// ==================== 添加文章 ====================

function AddArticleTab() {
  const [url, setUrl] = useState('')
  const [mpName, setMpName] = useState('')
  const [mpId, setMpId] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [accounts, setAccounts] = useState<Account[]>([])

  useEffect(() => { wechatDigestApi.getAccounts().then(r => setAccounts(r.data)).catch(() => {}) }, [])

  const handleAdd = useCallback(async () => {
    if (!url.trim()) return
    setLoading(true); setResult('')
    try {
      const res = await wechatDigestApi.addArticle({ url: url.trim(), mpName, mpId })
      if (res.data.duplicate) { setResult('⚠️ 文章已存在') }
      else { setResult(`✅ 已添加: ${res.data.title || '成功'}`); setUrl('') }
    } catch (e: any) { setResult(`❌ ${e.response?.data?.detail || e.message}`) }
    finally { setLoading(false) }
  }, [url, mpName, mpId])

  const handleBatch = useCallback(async () => {
    const urls = url.split('\n').map(u => u.trim()).filter(Boolean)
    if (urls.length === 0) return
    setLoading(true); setResult('')
    try {
      const res = await wechatDigestApi.addArticlesBatch({ urls, mpName, mpId })
      const ok = res.data.results.filter((r: any) => r.ok).length
      const fail = res.data.results.filter((r: any) => !r.ok).length
      setResult(`✅ 成功 ${ok} 篇${fail > 0 ? `，失败 ${fail} 篇` : ''}`)
      setUrl('')
    } catch (e: any) { setResult(`❌ ${e.response?.data?.detail || e.message}`) }
    finally { setLoading(false) }
  }, [url, mpName, mpId])

  return (
    <div>
      <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: 20 }}>
        <h3 style={{ color: 'var(--text-primary)', marginBottom: 16, fontSize: 15 }}>➕ 添加微信公众号文章</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 16 }}>
          粘贴微信公众号文章链接（mp.weixin.qq.com），支持单条或批量（每行一个链接）
        </p>

        <div style={{ marginBottom: 12 }}>
          <label style={{ color: 'var(--text-secondary)', fontSize: 12, display: 'block', marginBottom: 4 }}>文章链接</label>
          <textarea
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder={"https://mp.weixin.qq.com/s/xxxxx\nhttps://mp.weixin.qq.com/s/yyyyy"}
            style={{ ...inputS, width: '100%', minHeight: 80, resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }}
          />
        </div>

        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <label style={{ color: 'var(--text-secondary)', fontSize: 12, display: 'block', marginBottom: 4 }}>公众号名称（可选）</label>
            <input value={mpName} onChange={e => setMpName(e.target.value)} placeholder="如: 半佛仙人" style={inputS} list="mp-names" />
            <datalist id="mp-names">{accounts.map(a => <option key={a.mpId} value={a.name} />)}</datalist>
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ color: 'var(--text-secondary)', fontSize: 12, display: 'block', marginBottom: 4 }}>公众号ID（可选）</label>
            <input value={mpId} onChange={e => setMpId(e.target.value)} placeholder="如: banfoxx" style={inputS} list="mp-ids" />
            <datalist id="mp-ids">{accounts.map(a => <option key={a.mpId} value={a.mpId} />)}</datalist>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleAdd} disabled={loading || !url.trim()} style={btnP}>
            {loading ? '添加中...' : '添加文章'}
          </button>
          {url.includes('\n') && (
            <button onClick={handleBatch} disabled={loading} style={{ ...btnS, background: 'var(--accent-blue)', color: '#fff', border: 'none' }}>
              批量添加
            </button>
          )}
        </div>

        {result && <div style={{ marginTop: 12, fontSize: 13, color: result.startsWith('✅') ? '#3fb950' : result.startsWith('⚠️') ? '#d29922' : '#f85149' }}>{result}</div>}
      </div>
    </div>
  )
}

// ==================== 公众号管理 ====================

function AccountsTab() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newId, setNewId] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await wechatDigestApi.getAccounts(); setAccounts(r.data) }
    catch {} finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const handleAdd = async () => {
    if (!newName.trim() || !newId.trim()) return
    try {
      await wechatDigestApi.addAccount({ name: newName.trim(), mpId: newId.trim() })
      setNewName(''); setNewId(''); setShowAdd(false); load()
    } catch {}
  }
  const handleRemove = async (mpId: string) => {
    try { await wechatDigestApi.removeAccount(mpId); load() } catch {}
  }

  if (loading) return <LoadingSpinner text="加载中..." />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>共 {accounts.length} 个公众号</span>
        <button onClick={() => setShowAdd(!showAdd)} style={btnS}>{showAdd ? '取消' : '➕ 添加公众号'}</button>
      </div>

      {showAdd && (
        <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 12 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="公众号名称" style={{ ...inputS, flex: 1 }} />
            <input value={newId} onChange={e => setNewId(e.target.value)} placeholder="公众号ID" style={{ ...inputS, flex: 1 }} />
            <button onClick={handleAdd} style={btnP}>添加</button>
          </div>
        </div>
      )}

      {accounts.length === 0 ? (
        <EmptyState icon="📋" title="暂无公众号" description="点击上方按钮添加公众号" />
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {accounts.map(a => (
            <div key={a.mpId} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{a.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {a.articleCount} 篇文章{a.lastSync ? ` · ${relTime(a.lastSync)}` : ''}
                </div>
              </div>
              <button onClick={() => handleRemove(a.mpId)} style={{ ...btnS, color: '#f85149', fontSize: 11 }}>删除</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ==================== 文章列表 ====================

function ArticlesTab() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await wechatDigestApi.getArticles(); setArticles(r.data) }
    catch {} finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const filtered = filter ? articles.filter(a => a.mpName === filter) : articles
  const mpNames = [...new Set(articles.map(a => a.mpName))].filter(Boolean)

  if (loading) return <LoadingSpinner text="加载中..." />

  return (
    <div>
      {mpNames.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
          <button onClick={() => setFilter('')} style={{ ...chipS, ...(filter === '' ? chipActive : {}) }}>全部 ({articles.length})</button>
          {mpNames.map(n => <button key={n} onClick={() => setFilter(n)} style={{ ...chipS, ...(filter === n ? chipActive : {}) }}>{n}</button>)}
        </div>
      )}
      {filtered.length === 0 ? <EmptyState icon="📖" title="暂无文章" description="请先添加文章" /> : (
        <div style={{ display: 'grid', gap: 8 }}>
          {filtered.map((a, i) => (
            <div key={i} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: '12px 16px' }}>
              <a href={a.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'none', fontWeight: 500, fontSize: 14 }}>{a.title}</a>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{a.mpName} · {relTime(a.publishedAt)}</div>
              {a.summary && <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>📝 {a.summary}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ==================== 每日日报 ====================

function DigestTab() {
  const [digest, setDigest] = useState<DailyDigest | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    wechatDigestApi.getDigest().then(r => setDigest(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const toggle = (k: string) => setExpanded(prev => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n })

  if (loading) return <LoadingSpinner text="生成日报..." />
  if (!digest || digest.groups.length === 0) return <EmptyState icon="📭" title="暂无文章" description="请先添加公众号文章" />

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Chip label="公众号" val={digest.totalAccounts} /><Chip label="文章数" val={digest.totalArticles} /><Chip label="日期" val={digest.date} />
      </div>
      {digest.groups.map(g => (
        <div key={g.mpId || g.mpName} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', marginBottom: 12, overflow: 'hidden' }}>
          <div onClick={() => toggle(g.mpId || g.mpName)} style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: expanded.has(g.mpId || g.mpName) ? '1px solid var(--border-primary)' : 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18 }}>📰</span><span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{g.mpName}</span>
              <span style={{ background: 'var(--accent-blue)', color: '#fff', borderRadius: 10, padding: '1px 8px', fontSize: 11 }}>{g.count}篇</span>
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{expanded.has(g.mpId || g.mpName) ? '收起 ▲' : '展开 ▼'}</span>
          </div>
          {expanded.has(g.mpId || g.mpName) && (
            <div style={{ padding: '8px 16px 12px' }}>
              {g.items.map((it, idx) => (
                <div key={idx} style={{ padding: '10px 0', borderBottom: idx < g.items.length - 1 ? '1px solid var(--border-primary)' : 'none' }}>
                  <a href={it.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'none', fontWeight: 500, fontSize: 14 }}>{it.title}</a>
                  <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2 }}>{it.publishedDate}</div>
                  {it.summary && <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 6, lineHeight: 1.6 }}>📝 {it.summary}</div>}
                  {it.keyPoints?.length > 0 && it.keyPoints.map((kp, ki) => (
                    <div key={ki} style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.5, paddingLeft: 12, position: 'relative', marginTop: 2 }}>
                      <span style={{ position: 'absolute', left: 0, color: 'var(--accent-blue)' }}>•</span>{kp}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ==================== 设置 ====================

function SettingsTab() {
  const [config, setConfig] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')

  useEffect(() => { wechatDigestApi.getConfig().then(r => setConfig(r.data)).catch(() => {}).finally(() => setLoading(false)) }, [])
  const save = async () => {
    setMsg('')
    try { const r = await wechatDigestApi.updateConfig(config); setConfig(r.data); setMsg('✅ 已保存') }
    catch { setMsg('❌ 保存失败') }
  }

  if (loading) return <LoadingSpinner text="加载中..." />

  return (
    <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: 20 }}>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 16, fontSize: 15 }}>⚙️ 配置</h3>
      <CfgItem label="同步天数"><input type="number" value={config.syncDays || 7} onChange={e => setConfig({ ...config, syncDays: +e.target.value || 7 })} style={inputS} min={1} max={30} /></CfgItem>
      <CfgItem label="每号最大文章数"><input type="number" value={config.maxArticlesPerAccount || 20} onChange={e => setConfig({ ...config, maxArticlesPerAccount: +e.target.value || 20 })} style={inputS} min={5} max={100} /></CfgItem>
      <CfgItem label="API 地址"><input value={config.wereadApiBase || ''} onChange={e => setConfig({ ...config, wereadApiBase: e.target.value })} style={inputS} /></CfgItem>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 20 }}>
        <button onClick={save} style={btnP}>💾 保存</button>
        {msg && <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{msg}</span>}
      </div>
    </div>
  )
}

function CfgItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <label style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 500 }}>{label}</label>{children}
      </div>
    </div>
  )
}

function Chip({ label, val }: { label: string; val: number | string }) {
  return <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', padding: '6px 12px' }}><span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{val}</span><span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>{label}</span></div>
}

// ==================== 样式 ====================

const btnS: React.CSSProperties = { padding: '6px 14px', borderRadius: 6, fontSize: 13, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', cursor: 'pointer' }
const btnP: React.CSSProperties = { padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 500, border: 'none', background: 'var(--accent-blue)', color: '#fff', cursor: 'pointer' }
const chipS: React.CSSProperties = { padding: '3px 10px', borderRadius: 12, fontSize: 11, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-muted)', cursor: 'pointer' }
const chipActive: React.CSSProperties = { background: 'rgba(88,166,255,0.15)', color: 'var(--accent-blue)', borderColor: 'var(--accent-blue)' }
const inputS: React.CSSProperties = { padding: '6px 10px', borderRadius: 4, fontSize: 13, width: 200, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }
