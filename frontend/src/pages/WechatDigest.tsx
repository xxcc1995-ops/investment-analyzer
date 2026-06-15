/**
 * 微信公众号日报
 *
 * 四个标签页：
 * 1. 每日日报 - AI 摘要日报
 * 2. 公众号管理 - 已关注公众号列表
 * 3. 文章列表 - 全部文章卡片
 * 4. 设置 - 配置管理
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { PageSection, TabBar, LoadingSpinner, EmptyState } from '../components/ui'
import { wechatDigestApi } from '../services/api'

// ==================== 类型 ====================

interface DigestArticle {
  title: string
  url: string
  publishedAt: number
  publishedDate: string
  summary: string
  keyPoints: string[]
  mpName: string
}

interface DigestGroup {
  mpName: string
  mpId: string
  count: number
  items: DigestArticle[]
}

interface DailyDigest {
  title: string
  date: string
  groups: DigestGroup[]
  totalArticles: number
  totalAccounts: number
  update_time: string
}

interface Account {
  mpId: string
  name: string
  lastSync: string
  articleCount: number
}

interface Article {
  title: string
  url: string
  publishedAt: number
  fetchedAt: number
  content: string
  mpId: string
  mpName: string
  summary: string
}

interface LoginStatus {
  logged_in: boolean
  uuid?: string
}

// ==================== 标签页配置 ====================

const TABS = [
  { key: 'digest', label: '每日日报', icon: '📰' },
  { key: 'accounts', label: '公众号管理', icon: '📋' },
  { key: 'articles', label: '文章列表', icon: '📖' },
  { key: 'settings', label: '设置', icon: '⚙️' },
]

// ==================== 工具函数 ====================

function formatDate(ts: number | undefined): string {
  if (!ts) return ''
  try {
    return new Date(ts * 1000).toLocaleDateString('zh-CN')
  } catch {
    return ''
  }
}

function relativeTime(ts: number | undefined): string {
  if (!ts) return ''
  try {
    const now = Date.now()
    const diff = now - ts * 1000
    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
    const days = Math.floor(diff / 86400000)
    if (days < 7) return `${days}天前`
    return formatDate(ts)
  } catch {
    return ''
  }
}

// ==================== 主组件 ====================

export default function WechatDigest() {
  const [tab, setTab] = useState('digest')
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null)

  // 检查登录状态
  useEffect(() => {
    wechatDigestApi.getLoginStatus()
      .then(res => setLoggedIn(res.data.logged_in))
      .catch(() => setLoggedIn(false))
  }, [])

  const handleLoginSuccess = useCallback(() => {
    setLoggedIn(true)
  }, [])

  const handleLogout = useCallback(async () => {
    try {
      await wechatDigestApi.logout()
      setLoggedIn(false)
    } catch {}
  }, [])

  // 加载中
  if (loggedIn === null) {
    return (
      <PageSection title="📰 微信公众号日报">
        <LoadingSpinner text="检查登录状态..." />
      </PageSection>
    )
  }

  // 未登录 → 登录面板
  if (!loggedIn) {
    return (
      <PageSection title="📰 微信公众号日报">
        <LoginPanel onSuccess={handleLoginSuccess} />
      </PageSection>
    )
  }

  return (
    <PageSection
      title="📰 微信公众号日报"
      extra={
        <button onClick={handleLogout} style={btnStyleSmall}>
          退出登录
        </button>
      }
    >
      <TabBar tabs={TABS} activeKey={tab} onChange={setTab} style={{ marginBottom: 16 }} />
      {tab === 'digest' && <DigestTab />}
      {tab === 'accounts' && <AccountsTab />}
      {tab === 'articles' && <ArticlesTab />}
      {tab === 'settings' && <SettingsTab />}
    </PageSection>
  )
}

// ==================== 登录面板 ====================

function LoginPanel({ onSuccess }: { onSuccess: () => void }) {
  const [step, setStep] = useState<'init' | 'qr'>('init')
  const [qrUrl, setQrUrl] = useState('')
  const [error, setError] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const pollRef = useRef<number | null>(null)
  const timerRef = useRef<number | null>(null)

  const handleLogin = useCallback(async () => {
    setError('')
    setElapsed(0)
    try {
      const res = await wechatDigestApi.loginStart()
      const { uuid, qr_url } = res.data
      setQrUrl(qr_url)
      setStep('qr')

      // 开始轮询
      let count = 0
      pollRef.current = window.setInterval(async () => {
        count++
        setElapsed(count * 2)
        if (count > 90) {
          if (pollRef.current) clearInterval(pollRef.current)
          setError('登录超时，请重新尝试')
          setStep('init')
          return
        }
        try {
          const checkRes = await wechatDigestApi.loginCheck(uuid)
          if (checkRes.data.status === 'ok') {
            if (pollRef.current) clearInterval(pollRef.current)
            onSuccess()
          }
        } catch {}
      }, 2000)
    } catch (e: any) {
      setError(e.message || '登录发起失败')
    }
  }, [onSuccess])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  return (
    <div style={{ textAlign: 'center', padding: '40px 0' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>📱</div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>登录微信读书</h3>
      <p style={{ color: 'var(--text-muted)', marginBottom: 24, fontSize: 13 }}>
        通过微信读书 API 抓取你关注的公众号文章
      </p>

      {error && (
        <div style={{ color: '#f85149', marginBottom: 16, fontSize: 13 }}>{error}</div>
      )}

      {step === 'init' && (
        <button onClick={handleLogin} style={btnStylePrimary}>
          🔐 扫码登录
        </button>
      )}

      {step === 'qr' && (
        <div>
          <div style={{
            background: '#fff', borderRadius: 12, padding: 16,
            display: 'inline-block', marginBottom: 16,
          }}>
            {qrUrl && <QRCodeSVG value={qrUrl} size={240} level="M" />}
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            请用微信扫描二维码登录微信读书
          </p>
          <LoadingSpinner text={`等待扫码中... ${elapsed}s`} size="small" />
        </div>
      )}
    </div>
  )
}

// ==================== 每日日报 Tab ====================

function DigestTab() {
  const [digest, setDigest] = useState<DailyDigest | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const loadDigest = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await wechatDigestApi.getDigest()
      setDigest(res.data)
    } catch (e: any) {
      setError(e.message || '获取日报失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadDigest() }, [loadDigest])

  const toggleExpand = useCallback((key: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  if (loading) return <LoadingSpinner text="正在生成日报..." />
  if (error) return (
    <div style={{ textAlign: 'center', padding: 40 }}>
      <div style={{ color: '#f85149', marginBottom: 12 }}>{error}</div>
      <button onClick={loadDigest} style={btnStyle}>重试</button>
    </div>
  )
  if (!digest || !digest.groups || digest.groups.length === 0) {
    return (
      <EmptyState
        icon="📭"
        title="暂无文章"
        description="请先同步公众号文章"
        action={
          <button onClick={async () => {
            setLoading(true)
            try {
              await wechatDigestApi.syncArticles()
              await loadDigest()
            } catch { setLoading(false) }
          }} style={btnStyle}>立即同步</button>
        }
      />
    )
  }

  return (
    <div>
      {/* 统计栏 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <StatChip label="公众号" value={digest.totalAccounts} />
        <StatChip label="文章数" value={digest.totalArticles} />
        <StatChip label="日期" value={digest.date} />
        <button onClick={async () => {
          setLoading(true)
          try {
            await wechatDigestApi.syncArticles()
            await loadDigest()
          } catch { setLoading(false) }
        }} style={{ ...btnStyle, fontSize: 12 }}>🔄 同步并刷新</button>
      </div>

      {/* 日报内容 */}
      {digest.groups.map(group => (
        <div key={group.mpId || group.mpName} style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-md)', marginBottom: 12, overflow: 'hidden',
        }}>
          <div
            onClick={() => toggleExpand(group.mpId || group.mpName)}
            style={{
              padding: '12px 16px', cursor: 'pointer',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              borderBottom: expanded.has(group.mpId || group.mpName) ? '1px solid var(--border-primary)' : 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 18 }}>📰</span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{group.mpName}</span>
              <span style={{
                background: 'var(--accent-blue)', color: '#fff',
                borderRadius: 10, padding: '1px 8px', fontSize: 11,
              }}>{group.count}篇</span>
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
              {expanded.has(group.mpId || group.mpName) ? '收起 ▲' : '展开 ▼'}
            </span>
          </div>

          {expanded.has(group.mpId || group.mpName) && (
            <div style={{ padding: '8px 16px 12px' }}>
              {group.items.map((item, idx) => (
                <div key={idx} style={{
                  padding: '10px 0',
                  borderBottom: idx < group.items.length - 1 ? '1px solid var(--border-primary)' : 'none',
                }}>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: 'var(--accent-blue)', textDecoration: 'none', fontWeight: 500, fontSize: 14 }}
                  >
                    {item.title}
                  </a>
                  <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2 }}>
                    {item.publishedDate}
                  </div>
                  {item.summary && (
                    <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 6, lineHeight: 1.6 }}>
                      📝 {item.summary}
                    </div>
                  )}
                  {item.keyPoints && item.keyPoints.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                      {item.keyPoints.map((kp, ki) => (
                        <div key={ki} style={{
                          color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.5,
                          paddingLeft: 12, position: 'relative', marginTop: 2,
                        }}>
                          <span style={{ position: 'absolute', left: 0, color: 'var(--accent-blue)' }}>•</span>
                          {kp}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ==================== 公众号管理 Tab ====================

function AccountsTab() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const loadAccounts = useCallback(async () => {
    setLoading(true)
    try {
      const res = await wechatDigestApi.getAccounts()
      setAccounts(res.data)
    } catch {} finally { setLoading(false) }
  }, [])

  useEffect(() => { loadAccounts() }, [loadAccounts])

  const handleSync = useCallback(async () => {
    setSyncing(true)
    try {
      await wechatDigestApi.syncAccounts()
      await loadAccounts()
    } catch {} finally { setSyncing(false) }
  }, [loadAccounts])

  if (loading) return <LoadingSpinner text="加载公众号列表..." />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          共 {accounts.length} 个公众号
        </span>
        <button onClick={handleSync} disabled={syncing} style={btnStyle}>
          {syncing ? '同步中...' : '🔄 重新同步'}
        </button>
      </div>

      {accounts.length === 0 ? (
        <EmptyState icon="📋" title="暂无公众号" description="点击上方按钮同步已关注的公众号" />
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {accounts.map(acc => (
            <div key={acc.mpId} style={{
              background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-md)', padding: '12px 16px',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div>
                <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{acc.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {acc.articleCount} 篇文章
                  {acc.lastSync && ` · 最后同步: ${relativeTime(acc.lastSync)}`}
                </div>
              </div>
              <button
                onClick={async () => {
                  setSyncing(true)
                  try {
                    await wechatDigestApi.syncArticles({ mp_id: acc.mpId })
                    await loadAccounts()
                  } catch {} finally { setSyncing(false) }
                }}
                style={{ ...btnStyle, fontSize: 12 }}
              >
                同步
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ==================== 文章列表 Tab ====================

function ArticlesTab() {
  const [articles, setArticles] = useState<Article[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  const loadArticles = useCallback(async () => {
    setLoading(true)
    try {
      const res = await wechatDigestApi.getArticles()
      setArticles(res.data)
    } catch {} finally { setLoading(false) }
  }, [])

  useEffect(() => { loadArticles() }, [loadArticles])

  const filtered = filter
    ? articles.filter(a => a.mpName === filter)
    : articles

  const mpNames = [...new Set(articles.map(a => a.mpName))].filter(Boolean)

  if (loading) return <LoadingSpinner text="加载文章列表..." />

  return (
    <div>
      {/* 过滤栏 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>筛选:</span>
        <button
          onClick={() => setFilter('')}
          style={{ ...chipStyle, ...(filter === '' ? chipActiveStyle : {}) }}
        >
          全部 ({articles.length})
        </button>
        {mpNames.map(name => (
          <button
            key={name}
            onClick={() => setFilter(name)}
            style={{ ...chipStyle, ...(filter === name ? chipActiveStyle : {}) }}
          >
            {name}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon="📖" title="暂无文章" description="请先同步文章" />
      ) : (
        <div style={{ display: 'grid', gap: 8 }}>
          {filtered.map((article, idx) => (
            <div key={idx} style={{
              background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-md)', padding: '12px 16px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: 'var(--accent-blue)', textDecoration: 'none', fontWeight: 500, fontSize: 14 }}
                  >
                    {article.title}
                  </a>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    <span>{article.mpName}</span>
                    <span style={{ margin: '0 6px' }}>·</span>
                    <span>{relativeTime(article.publishedAt)}</span>
                  </div>
                </div>
              </div>
              {article.summary && (
                <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 8, lineHeight: 1.6 }}>
                  📝 {article.summary}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ==================== 设置 Tab ====================

function SettingsTab() {
  const [config, setConfig] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    wechatDigestApi.getConfig()
      .then(res => setConfig(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setMessage('')
    try {
      const res = await wechatDigestApi.updateConfig(config)
      setConfig(res.data)
      setMessage('✅ 保存成功')
    } catch {
      setMessage('❌ 保存失败')
    } finally {
      setSaving(false)
    }
  }, [config])

  if (loading) return <LoadingSpinner text="加载配置..." />

  return (
    <div>
      <div style={{
        background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-md)', padding: 20,
      }}>
        <h3 style={{ color: 'var(--text-primary)', marginBottom: 16, fontSize: 15 }}>⚙️ 配置项</h3>

        <ConfigItem label="同步天数" desc="每次同步最近几天的文章">
          <input
            type="number"
            value={config.syncDays || 2}
            onChange={e => setConfig({ ...config, syncDays: parseInt(e.target.value) || 2 })}
            style={inputStyle}
            min={1}
            max={30}
          />
        </ConfigItem>

        <ConfigItem label="每号最大文章数" desc="每个公众号保留的最大文章数">
          <input
            type="number"
            value={config.maxArticlesPerAccount || 20}
            onChange={e => setConfig({ ...config, maxArticlesPerAccount: parseInt(e.target.value) || 20 })}
            style={inputStyle}
            min={5}
            max={100}
          />
        </ConfigItem>

        <ConfigItem label="重试次数" desc="API 请求失败时的重试次数">
          <input
            type="number"
            value={config.retryMaxAttempts || 5}
            onChange={e => setConfig({ ...config, retryMaxAttempts: parseInt(e.target.value) || 5 })}
            style={inputStyle}
            min={1}
            max={10}
          />
        </ConfigItem>

        <ConfigItem label="重试间隔 (ms)" desc="每次重试之间的等待时间">
          <input
            type="number"
            value={config.retryDelayMs || 400}
            onChange={e => setConfig({ ...config, retryDelayMs: parseInt(e.target.value) || 400 })}
            style={inputStyle}
            min={100}
            max={5000}
          />
        </ConfigItem>

        <ConfigItem label="API 地址" desc="微信读书 API 代理地址">
          <input
            type="text"
            value={config.wereadApiBase || ''}
            onChange={e => setConfig({ ...config, wereadApiBase: e.target.value })}
            style={inputStyle}
            placeholder="https://weread.111965.xyz"
          />
        </ConfigItem>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 20 }}>
          <button onClick={handleSave} disabled={saving} style={btnStylePrimary}>
            {saving ? '保存中...' : '💾 保存配置'}
          </button>
          {message && <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{message}</span>}
        </div>
      </div>
    </div>
  )
}

// ==================== 子组件 ====================

function ConfigItem({ label, desc, children }: { label: string; desc: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <label style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 500 }}>{label}</label>
        {children}
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{desc}</div>
    </div>
  )
}

function StatChip({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-sm)', padding: '6px 12px',
    }}>
      <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</span>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>{label}</span>
    </div>
  )
}

// ==================== 样式常量 ====================

const btnStyle: React.CSSProperties = {
  padding: '6px 14px', borderRadius: 6, fontSize: 13,
  border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
  color: 'var(--text-secondary)', cursor: 'pointer',
}

const btnStyleSmall: React.CSSProperties = {
  ...btnStyle, padding: '4px 10px', fontSize: 11,
}

const btnStylePrimary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, fontSize: 14, fontWeight: 500,
  border: 'none', background: 'var(--accent-blue)', color: '#fff', cursor: 'pointer',
}

const chipStyle: React.CSSProperties = {
  padding: '3px 10px', borderRadius: 12, fontSize: 11,
  border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
  color: 'var(--text-muted)', cursor: 'pointer',
}

const chipActiveStyle: React.CSSProperties = {
  background: 'rgba(88,166,255,0.15)', color: 'var(--accent-blue)',
  borderColor: 'var(--accent-blue)',
}

const inputStyle: React.CSSProperties = {
  padding: '4px 8px', borderRadius: 4, fontSize: 13, width: 140,
  border: '1px solid var(--border-primary)', background: 'var(--bg-primary)',
  color: 'var(--text-primary)',
}
