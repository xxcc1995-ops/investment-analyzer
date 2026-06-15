/**
 * 微信公众号日报
 * 通过微信读书 API 获取已关注公众号文章，生成 AI 摘要
 */
import { useState, useEffect, useCallback } from 'react'
import { PageSection, TabBar, LoadingSpinner, EmptyState } from '../components/ui'
import { wechatDigestApi } from '../services/api'

interface Account { mpId: string; name: string; cover?: string; articleCount: number; lastSync: string }
interface Article { title: string; url: string; publishedAt: number; mpName: string; summary: string; readNum?: number; likeNum?: number }
interface DigestGroup { mpName: string; mpId: string; count: number; items: Article[] }
interface Digest { title: string; date: string; groups: DigestGroup[]; totalArticles: number; totalAccounts: number }

const TABS = [
  { key: 'digest', label: '每日日报', icon: '📰' },
  { key: 'sync', label: '同步文章', icon: '🔄' },
  { key: 'accounts', label: '公众号', icon: '📋' },
  { key: 'articles', label: '文章列表', icon: '📖' },
  { key: 'settings', label: '设置', icon: '⚙️' },
]

function relTime(ts?: number) {
  if (!ts) return ''
  const d = Date.now() - ts * 1000
  if (d < 60000) return '刚刚'
  if (d < 3600000) return `${Math.floor(d / 60000)}分钟前`
  if (d < 86400000) return `${Math.floor(d / 3600000)}小时前`
  return `${Math.floor(d / 86400000)}天前`
}

export default function WechatDigest() {
  const [tab, setTab] = useState('digest')
  const [status, setStatus] = useState<{ logged_in: boolean; valid?: boolean; expired?: boolean } | null>(null)

  const checkStatus = useCallback(async () => {
    try { const r = await wechatDigestApi.getLoginStatus(); setStatus(r.data) }
    catch { setStatus({ logged_in: false }) }
  }, [])

  useEffect(() => { checkStatus() }, [checkStatus])

  if (!status) return <PageSection title="📰 微信公众号日报"><LoadingSpinner text="加载中..." /></PageSection>

  if (!status.logged_in) return <PageSection title="📰 微信公众号日报"><LoginPanel onSuccess={checkStatus} /></PageSection>

  if (status.expired) return <PageSection title="📰 微信公众号日报"><CookieExpired onRefresh={checkStatus} /></PageSection>

  return (
    <PageSection title="📰 微信公众号日报" extra={<button onClick={async () => { await wechatDigestApi.logout(); checkStatus() }} style={btnS}>退出</button>}>
      <TabBar tabs={TABS} activeKey={tab} onChange={setTab} style={{ marginBottom: 16 }} />
      {tab === 'digest' && <DigestTab />}
      {tab === 'sync' && <SyncTab />}
      {tab === 'accounts' && <AccountsTab />}
      {tab === 'articles' && <ArticlesTab />}
      {tab === 'settings' && <SettingsTab />}
    </PageSection>
  )
}

// ==================== 登录面板 ====================

function LoginPanel({ onSuccess }: { onSuccess: () => void }) {
  const [mode, setMode] = useState<'choose' | 'manual' | 'auto'>('choose')
  const [cookie, setCookie] = useState('')
  const [vid, setVid] = useState('')
  const [skey, setSkey] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCookie = async () => {
    if (!cookie.trim()) return
    setLoading(true); setError('')
    try {
      await wechatDigestApi.setCookie(cookie.trim())
      onSuccess()
    } catch (e: any) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }

  const handleDirect = async () => {
    if (!vid.trim() || !skey.trim()) return
    setLoading(true); setError('')
    try {
      await wechatDigestApi.setCookieDirect(vid.trim(), skey.trim())
      onSuccess()
    } catch (e: any) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }

  const handleAutoExtract = async () => {
    setLoading(true); setError('')
    try {
      const r = await wechatDigestApi.extractCookie()
      if (r.data.ok) onSuccess()
      else setError(r.data.error || '提取失败')
    } catch (e: any) { setError(e.response?.data?.detail || e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '40px 20px' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>📰</div>
        <h2 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>微信公众号日报</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>通过微信读书获取你关注的公众号文章，AI 生成每日摘要</p>
      </div>

      {error && <div style={{ color: '#f85149', marginBottom: 16, padding: '8px 12px', background: 'rgba(248,81,73,0.1)', borderRadius: 6, fontSize: 13 }}>{error}</div>}

      {mode === 'choose' && (
        <div>
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: 20, marginBottom: 16 }}>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12, fontSize: 15 }}>🔐 登录微信读书</div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 2 }}>
              <div>1. 用浏览器打开 <a href="https://weread.qq.com" target="_blank" rel="noopener" style={{ color: 'var(--accent-blue)', fontWeight: 500 }}>weread.qq.com</a> 并扫码登录</div>
              <div>2. 登录成功后，按 <kbd style={{ background: 'var(--bg-primary)', padding: '2px 6px', borderRadius: 3, fontSize: 12 }}>F12</kbd> 打开开发者工具</div>
              <div>3. 点击 <b>Application</b> → <b>Cookies</b> → <b>weread.qq.com</b></div>
              <div>4. 找到 <code style={{ background: 'var(--bg-primary)', padding: '1px 4px', borderRadius: 3 }}>wr_vid</code> 和 <code style={{ background: 'var(--bg-primary)', padding: '1px 4px', borderRadius: 3 }}>wr_skey</code>，复制它们的值</div>
            </div>
          </div>
          <button onClick={() => setMode('manual')} style={{ ...btnP, width: '100%', padding: '12px 20px', fontSize: 15 }}>
            📋 粘贴 Cookie 登录
          </button>
        </div>
      )}

      {mode === 'manual' && (
        <div>
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 16, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>📖 获取步骤：</div>
            <div>1. 用 Chrome 打开 <a href="https://weread.qq.com" target="_blank" rel="noopener" style={{ color: 'var(--accent-blue)' }}>weread.qq.com</a> 并扫码登录</div>
            <div>2. 按 F12 打开开发者工具 → Application → Cookies → weread.qq.com</div>
            <div>3. 复制 <code style={{ background: 'var(--bg-primary)', padding: '1px 4px', borderRadius: 3 }}>wr_vid</code> 和 <code style={{ background: 'var(--bg-primary)', padding: '1px 4px', borderRadius: 3 }}>wr_skey</code> 的值</div>
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>wr_vid</label>
              <input value={vid} onChange={e => setVid(e.target.value)} placeholder="如 65829848" style={inputS} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>wr_skey</label>
              <input value={skey} onChange={e => setSkey(e.target.value)} placeholder="如 onb3Mjtjxs..." style={inputS} />
            </div>
          </div>
          <button onClick={handleDirect} disabled={loading || !vid || !skey} style={btnP}>{loading ? '验证中...' : '登录'}</button>

          <div style={{ margin: '16px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>或粘贴完整 cookie 字符串</div>
          <textarea value={cookie} onChange={e => setCookie(e.target.value)} placeholder="wr_vid=xxx; wr_skey=xxx; ..." style={{ ...inputS, width: '100%', minHeight: 60, fontFamily: 'monospace', fontSize: 12 }} />
          <button onClick={handleCookie} disabled={loading || !cookie} style={{ ...btnP, marginTop: 8 }}>{loading ? '验证中...' : '用完整 cookie 登录'}</button>

          <div style={{ marginTop: 12 }}>
            <button onClick={() => setMode('choose')} style={{ ...btnS, fontSize: 12 }}>← 返回</button>
          </div>
        </div>
      )}
    </div>
  )
}

function CookieExpired({ onRefresh }: { onRefresh: () => void }) {
  const handleRelogin = async () => {
    await wechatDigestApi.logout()
    onRefresh()
  }
  return (
    <div style={{ textAlign: 'center', padding: '40px 20px' }}>
      <div style={{ fontSize: 48, marginBottom: 12 }}>⏰</div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>Cookie 已过期</h3>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>请重新登录微信读书</p>
      <button onClick={handleRelogin} style={btnP}>重新登录</button>
    </div>
  )
}

// ==================== 同步文章 ====================

function SyncTab() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    wechatDigestApi.getAccounts().then(r => setAccounts(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleSync = async (mpId?: string) => {
    setSyncing(true); setResult('')
    try {
      const r = await wechatDigestApi.sync({ mp_id: mpId, limit: 20 })
      const d = r.data
      if (d.error) { setResult(`❌ ${d.error}`) }
      else { setResult(`✅ 同步完成：新增 ${d.synced} 篇`); wechatDigestApi.getAccounts().then(r => setAccounts(r.data)) }
    } catch (e: any) { setResult(`❌ ${e.response?.data?.detail || e.message}`) }
    finally { setSyncing(false) }
  }

  if (loading) return <LoadingSpinner text="加载中..." />

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <button onClick={() => handleSync()} disabled={syncing} style={btnP}>
          {syncing ? '同步中...' : '🔄 同步全部公众号'}
        </button>
        {result && <span style={{ marginLeft: 12, fontSize: 13, color: result.startsWith('✅') ? '#3fb950' : '#f85149' }}>{result}</span>}
      </div>

      {accounts.length === 0 ? (
        <EmptyState icon="📋" title="暂无公众号" description="请先在微信读书 App 中关注公众号" />
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {accounts.map(a => (
            <div key={a.mpId} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{a.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {a.articleCount} 篇{a.lastSync ? ` · ${relTime(a.lastSync)}` : ''}
                </div>
              </div>
              <button onClick={() => handleSync(a.mpId)} disabled={syncing} style={btnS}>同步</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ==================== 公众号列表 ====================

function AccountsTab() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    wechatDigestApi.getAccounts().then(r => setAccounts(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner text="加载中..." />
  if (accounts.length === 0) return <EmptyState icon="📋" title="暂无公众号" description="请先在微信读书 App 中关注公众号，然后点击「同步文章」" />

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {accounts.map(a => (
        <div key={a.mpId} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {a.cover && <img src={a.cover} alt="" style={{ width: 36, height: 36, borderRadius: 18 }} />}
            <div>
              <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{a.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{a.articleCount} 篇文章</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ==================== 文章列表 ====================

function ArticlesTab() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    wechatDigestApi.getArticles().then(r => setArticles(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const filtered = filter ? articles.filter(a => a.mpName === filter) : articles
  const mpNames = [...new Set(articles.map(a => a.mpName))].filter(Boolean)

  if (loading) return <LoadingSpinner text="加载中..." />
  if (articles.length === 0) return <EmptyState icon="📖" title="暂无文章" description="点击「同步文章」获取最新文章" />

  return (
    <div>
      {mpNames.length > 1 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
          <button onClick={() => setFilter('')} style={{ ...chipS, ...(filter === '' ? chipA : {}) }}>全部 ({articles.length})</button>
          {mpNames.map(n => <button key={n} onClick={() => setFilter(n)} style={{ ...chipS, ...(filter === n ? chipA : {}) }}>{n}</button>)}
        </div>
      )}
      <div style={{ display: 'grid', gap: 8 }}>
        {filtered.map((a, i) => (
          <div key={i} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: '12px 16px' }}>
            <a href={a.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'none', fontWeight: 500, fontSize: 14 }}>{a.title}</a>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {a.mpName} · {relTime(a.publishedAt)}
              {a.readNum ? ` · 👁${a.readNum}` : ''}
              {a.likeNum ? ` · 👍${a.likeNum}` : ''}
            </div>
            {a.summary && <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6, lineHeight: 1.6 }}>📝 {a.summary.slice(0, 200)}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

// ==================== 每日日报 ====================

function DigestTab() {
  const [digest, setDigest] = useState<Digest | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => { wechatDigestApi.getDigest().then(r => setDigest(r.data)).catch(() => {}).finally(() => setLoading(false)) }, [])
  const toggle = (k: string) => setExpanded(prev => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n })

  if (loading) return <LoadingSpinner text="生成日报..." />
  if (!digest || digest.groups.length === 0) return <EmptyState icon="📭" title="暂无文章" description="点击「同步文章」获取最新公众号文章" />

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Chip l="公众号" v={digest.totalAccounts} /><Chip l="文章" v={digest.totalArticles} /><Chip l="日期" v={digest.date} />
      </div>
      {digest.groups.map(g => (
        <div key={g.mpId} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', marginBottom: 12, overflow: 'hidden' }}>
          <div onClick={() => toggle(g.mpId)} style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18 }}>📰</span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{g.mpName}</span>
              <span style={{ background: 'var(--accent-blue)', color: '#fff', borderRadius: 10, padding: '1px 8px', fontSize: 11 }}>{g.count}篇</span>
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{expanded.has(g.mpId) ? '收起 ▲' : '展开 ▼'}</span>
          </div>
          {expanded.has(g.mpId) && (
            <div style={{ padding: '8px 16px 12px', borderTop: '1px solid var(--border-primary)' }}>
              {g.items.map((it, idx) => (
                <div key={idx} style={{ padding: '10px 0', borderBottom: idx < g.items.length - 1 ? '1px solid var(--border-primary)' : 'none' }}>
                  <a href={it.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'none', fontWeight: 500, fontSize: 14 }}>{it.title}</a>
                  <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2 }}>{it.publishedDate}</div>
                  {it.summary && <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 6, lineHeight: 1.6 }}>📝 {it.summary.slice(0, 200)}</div>}
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
  const save = async () => { setMsg(''); try { await wechatDigestApi.updateConfig(config); setMsg('✅ 已保存') } catch { setMsg('❌ 失败') } }

  if (loading) return <LoadingSpinner text="加载中..." />

  return (
    <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-md)', padding: 20 }}>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 16, fontSize: 15 }}>⚙️ 配置</h3>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <label style={{ color: 'var(--text-primary)', fontSize: 13 }}>同步天数</label>
        <input type="number" value={config.syncDays || 3} onChange={e => setConfig({ ...config, syncDays: +e.target.value })} style={{ ...inputS, width: 100 }} min={1} max={30} />
      </div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <label style={{ color: 'var(--text-primary)', fontSize: 13 }}>每号最大文章数</label>
        <input type="number" value={config.maxArticlesPerAccount || 30} onChange={e => setConfig({ ...config, maxArticlesPerAccount: +e.target.value })} style={{ ...inputS, width: 100 }} min={5} max={100} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button onClick={save} style={btnP}>💾 保存</button>
        {msg && <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{msg}</span>}
      </div>
    </div>
  )
}

function Chip({ l, v }: { l: string; v: number | string }) {
  return <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', padding: '6px 12px' }}><span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{v}</span><span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>{l}</span></div>
}

const btnS: React.CSSProperties = { padding: '6px 14px', borderRadius: 6, fontSize: 13, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-secondary)', cursor: 'pointer' }
const btnP: React.CSSProperties = { padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 500, border: 'none', background: 'var(--accent-blue)', color: '#fff', cursor: 'pointer' }
const chipS: React.CSSProperties = { padding: '3px 10px', borderRadius: 12, fontSize: 11, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', color: 'var(--text-muted)', cursor: 'pointer' }
const chipA: React.CSSProperties = { background: 'rgba(88,166,255,0.15)', color: 'var(--accent-blue)', borderColor: 'var(--accent-blue)' }
const inputS: React.CSSProperties = { padding: '6px 10px', borderRadius: 4, fontSize: 13, border: '1px solid var(--border-primary)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }
const cardBtn: React.CSSProperties = { padding: 20, borderRadius: 8, border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)', cursor: 'pointer', textAlign: 'center' as const }
