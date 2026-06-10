import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'

const API_BASE = '/api/cards'

// ============== Types ==============

interface Card {
  id: string
  issuer: string
  name: string
  local_name: string
  country: string
  currency: string
  card_type: string
  card_network: string
  annual_fee: number
  annual_fee_waiver: string
  signup_bonus: string
  signup_bonus_requirement: string
  signup_bonus_value: number
  rewards_rate: Record<string, number>
  rewards_type: string
  key_perks: string[]
  income_requirement: string
  credit_score_requirement: string
  foreign_transaction_fee: number
  best_for: string
  notes: string
  rating: number
  tags: string[]
}

interface CardStats {
  total_cards: number
  countries: number
  avg_annual_fee: number
  highest_bonus: number
}

type SortField = 'rating' | 'annual_fee' | 'signup_bonus_value'
type TabKey = 'browse' | 'compare' | 'recommend'

// ============== Reusable UI primitives ==============

const badgeStyle = (bg: string, color: string): React.CSSProperties => ({
  fontSize: '11px',
  padding: '2px 8px',
  borderRadius: '4px',
  background: bg,
  color,
})

const selectInputStyle: React.CSSProperties = {
  padding: '6px 12px',
  border: '1px solid var(--border-primary)',
  borderRadius: '4px',
  background: 'var(--bg-primary)',
  color: 'var(--text-primary)',
}

function Badge({ bg, color, children }: { bg: string; color: string; children: React.ReactNode }) {
  return <span style={badgeStyle(bg, color)}>{children}</span>
}

function Label({ text }: { text: string }) {
  return (
    <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
      {text}
    </label>
  )
}

function LoadingSpinner() {
  return <div className="loading"><div className="spinner" />加载中...</div>
}

function EmptyState({ message }: { message: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
      {message}
    </div>
  )
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div style={{
      margin: '16px 20px',
      padding: '12px 16px',
      background: 'rgba(248, 81, 73, 0.1)',
      border: '1px solid rgba(248, 81, 73, 0.3)',
      borderRadius: '8px',
      color: '#f85149',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      fontSize: '13px',
    }}>
      <span>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: '4px 12px',
            background: 'transparent',
            border: '1px solid #f85149',
            borderRadius: '4px',
            color: '#f85149',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          重试
        </button>
      )}
    </div>
  )
}

// ============== Helpers ==============

function getRatingColor(rating: number): string {
  if (rating >= 4.5) return '#3fb950'
  if (rating >= 3.5) return '#58a6ff'
  if (rating >= 2.5) return '#d29922'
  return '#f85149'
}

function getFeeColor(fee: number): string {
  if (fee === 0) return '#3fb950'
  if (fee <= 100) return '#d29922'
  return '#f85149'
}

// ============== Debounced search hook ==============

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

// ============== Card list item component ==============

function CardListItem({
  card,
  isComparing,
  onToggleCompare,
}: {
  card: Card
  isComparing: boolean
  onToggleCompare: (id: string) => void
}) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: '8px',
      border: '1px solid var(--border-primary)', padding: '20px',
      transition: 'border-color 0.2s',
    }}>
      {/* Card Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <Badge bg="rgba(88, 166, 255, 0.15)" color="#58a6ff">{card.issuer}</Badge>
            <Badge bg="rgba(210, 153, 34, 0.15)" color="#d29922">{card.card_network}</Badge>
            <Badge bg="rgba(139, 148, 158, 0.15)" color="#8b949e">{card.country}</Badge>
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {card.name}
          </div>
          {card.local_name && card.local_name !== card.name && (
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {card.local_name}
            </div>
          )}
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '22px', fontWeight: 700, color: getRatingColor(card.rating) }}>
            {card.rating.toFixed(1)}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>评分</div>
        </div>
      </div>

      {/* Key Info Row */}
      <div style={{
        display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '12px',
        padding: '12px', background: 'var(--bg-primary)', borderRadius: '6px',
      }}>
        <div style={{ flex: '1 1 120px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>年费</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: getFeeColor(card.annual_fee) }}>
            {card.annual_fee === 0 ? '免年费' : `${card.currency} ${card.annual_fee}`}
          </div>
          {card.annual_fee_waiver && (
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {card.annual_fee_waiver}
            </div>
          )}
        </div>
        <div style={{ flex: '1 1 160px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>开卡奖励</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: '#3fb950' }}>
            {card.signup_bonus || '无'}
          </div>
          {card.signup_bonus_value > 0 && (
            <div style={{ fontSize: '11px', color: '#3fb950', marginTop: '2px' }}>
              价值约 ${card.signup_bonus_value}
            </div>
          )}
          {card.signup_bonus_requirement && (
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {card.signup_bonus_requirement}
            </div>
          )}
        </div>
        <div style={{ flex: '1 1 160px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>返现/积分</div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
            {card.rewards_type || '-'}
          </div>
          {card.rewards_rate && Object.keys(card.rewards_rate).length > 0 && (
            <div style={{ marginTop: '4px' }}>
              {Object.entries(card.rewards_rate).map(([category, rate]) => (
                <span key={category} style={{
                  display: 'inline-block', fontSize: '11px', padding: '1px 6px',
                  margin: '2px 4px 2px 0', borderRadius: '3px',
                  background: 'rgba(88, 166, 255, 0.1)', color: '#58a6ff',
                }}>
                  {category}: {rate}%
                </span>
              ))}
            </div>
          )}
        </div>
        <div style={{ flex: '1 1 120px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>外币手续费</div>
          <div style={{
            fontSize: '16px', fontWeight: 700,
            color: card.foreign_transaction_fee === 0 ? '#3fb950' : '#f85149',
          }}>
            {card.foreign_transaction_fee === 0 ? '免费' : `${card.foreign_transaction_fee}%`}
          </div>
        </div>
      </div>

      {/* Key Perks */}
      {card.key_perks && card.key_perks.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px' }}>核心权益</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {card.key_perks.map((perk, i) => (
              <span key={i} style={{
                fontSize: '12px', padding: '3px 10px', borderRadius: '4px',
                background: 'rgba(63, 185, 80, 0.1)', color: '#3fb950',
                border: '1px solid rgba(63, 185, 80, 0.2)',
              }}>
                {perk}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Footer Row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {card.best_for && (
            <Badge bg="rgba(240, 136, 62, 0.1)" color="#f0883e">
              最适合: {card.best_for}
            </Badge>
          )}
          {card.tags && card.tags.map(tag => (
            <Badge key={tag} bg="rgba(139, 148, 158, 0.1)" color="#8b949e">
              {tag}
            </Badge>
          ))}
        </div>
        <button
          onClick={() => onToggleCompare(card.id)}
          style={{
            padding: '4px 12px', fontSize: '12px', borderRadius: '4px',
            border: isComparing ? '1px solid #3fb950' : '1px solid var(--border-primary)',
            background: isComparing ? 'rgba(63, 185, 80, 0.15)' : 'transparent',
            color: isComparing ? '#3fb950' : 'var(--text-muted)',
            cursor: 'pointer',
          }}
        >
          {isComparing ? '已选对比' : '+ 加入对比'}
        </button>
      </div>
    </div>
  )
}

// ============== Main component ==============

export default function CardBenefitsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('browse')

  // Browse
  const [cards, setCards] = useState<Card[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [country, setCountry] = useState('')
  const [maxAnnualFee, setMaxAnnualFee] = useState('')
  const [noAnnualFee, setNoAnnualFee] = useState(false)
  const [sortBy, setSortBy] = useState<SortField>('rating')
  const [searchInput, setSearchInput] = useState('')
  const search = useDebouncedValue(searchInput, 300)

  // Countries
  const [countries, setCountries] = useState<string[]>([])

  // Stats
  const [stats, setStats] = useState<CardStats | null>(null)

  // Compare
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [compareCards, setCompareCards] = useState<Card[]>([])
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareError, setCompareError] = useState<string | null>(null)

  // Recommend
  const [recommendCards, setRecommendCards] = useState<Card[]>([])
  const [recommendLoading, setRecommendLoading] = useState(false)
  const [recommendError, setRecommendError] = useState<string | null>(null)

  // O(1) lookup for compare membership
  const compareIdSet = useMemo(() => new Set(compareIds), [compareIds])

  // Load countries
  const loadCountries = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/countries`)
      setCountries(res.data.countries || [])
    } catch (e) {
      console.error('获取国家列表失败:', e)
    }
  }, [])

  // Load stats
  const loadStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/stats`)
      setStats(res.data)
    } catch (e) {
      console.error('获取统计失败:', e)
    }
  }, [])

  // Load cards
  const loadCards = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number | boolean> = { sort_by: sortBy }
      if (country) params.country = country
      if (maxAnnualFee) params.max_annual_fee = Number(maxAnnualFee)
      if (noAnnualFee) params.no_annual_fee = true
      if (search) params.search = search
      const res = await axios.get(`${API_BASE}/list`, { params })
      setCards(res.data.cards || [])
      setTotal(res.data.total || 0)
    } catch (e) {
      console.error('获取卡片列表失败:', e)
      setError('获取卡片列表失败，请检查网络后重试')
    } finally {
      setLoading(false)
    }
  }, [country, maxAnnualFee, noAnnualFee, sortBy, search])

  // Load compare
  const loadCompare = useCallback(async () => {
    if (compareIds.length === 0) {
      setCompareCards([])
      return
    }
    setCompareLoading(true)
    setCompareError(null)
    try {
      const res = await axios.get(`${API_BASE}/compare`, { params: { ids: compareIds.join(',') } })
      setCompareCards(res.data.cards || [])
    } catch (e) {
      console.error('获取对比数据失败:', e)
      setCompareError('获取对比数据失败，请重试')
    } finally {
      setCompareLoading(false)
    }
  }, [compareIds])

  // Load recommend
  const loadRecommend = useCallback(async () => {
    setRecommendLoading(true)
    setRecommendError(null)
    try {
      const res = await axios.get(`${API_BASE}/list`, {
        params: { sort_by: 'signup_bonus_value', limit: 50 },
      })
      setRecommendCards(res.data.cards || [])
    } catch (e) {
      console.error('获取推荐失败:', e)
      setRecommendError('获取推荐数据失败，请重试')
    } finally {
      setRecommendLoading(false)
    }
  }, [])

  // Initial load
  useEffect(() => {
    loadCountries()
    loadStats()
  }, [loadCountries, loadStats])

  // Tab-driven data fetching
  useEffect(() => {
    if (activeTab === 'browse') loadCards()
    if (activeTab === 'compare') loadCompare()
    if (activeTab === 'recommend') loadRecommend()
  }, [activeTab, loadCards, loadCompare, loadRecommend])

  // Toggle compare card
  const toggleCompare = useCallback((id: string) => {
    setCompareIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      if (prev.length >= 5) return prev
      return [...prev, id]
    })
  }, [])

  const clearCompare = useCallback(() => {
    setCompareIds([])
    setCompareCards([])
  }, [])

  const tabs: Array<{ key: TabKey; label: string }> = [
    { key: 'browse', label: '卡片浏览' },
    { key: 'compare', label: '卡片对比' },
    { key: 'recommend', label: '开卡奖励推荐' },
  ]

  return (
    <div className="fund-est-page">
      {/* Header */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>信用卡权益对比</h2>
            <span className="stock-code">
              全球支付卡产品信息 · 年费对比 · 权益查询 · 开卡奖励
            </span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, margin: '16px 20px', flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <button
            key={t.key}
            className={`tab-btn ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ============== Tab 1: Browse ============== */}
      {activeTab === 'browse' && (
        <div>
          {/* Filters */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '12px', margin: '16px 20px',
            padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
            border: '1px solid var(--border-primary)', alignItems: 'flex-end',
          }}>
            <div>
              <Label text="国家/地区" />
              <select
                value={country}
                onChange={e => setCountry(e.target.value)}
                style={{ ...selectInputStyle, minWidth: 120 }}
              >
                <option value="">全部</option>
                {countries.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <Label text="最高年费" />
              <select
                value={maxAnnualFee}
                onChange={e => setMaxAnnualFee(e.target.value)}
                style={selectInputStyle}
              >
                <option value="">不限</option>
                <option value="0">免年费</option>
                <option value="100">100以下</option>
                <option value="200">200以下</option>
                <option value="500">500以下</option>
                <option value="1000">1000以下</option>
              </select>
            </div>
            <div>
              <Label text="排序方式" />
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value as SortField)}
                style={selectInputStyle}
              >
                <option value="rating">按评分</option>
                <option value="annual_fee">按年费</option>
                <option value="signup_bonus_value">按开卡奖励</option>
              </select>
            </div>
            <div>
              <Label text="搜索" />
              <input
                type="text"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                placeholder="卡名/发卡行..."
                style={{ ...selectInputStyle, width: 160 }}
              />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-primary)' }}>
              <input
                type="checkbox"
                checked={noAnnualFee}
                onChange={e => setNoAnnualFee(e.target.checked)}
              />
              仅免年费
            </label>
            <button
              onClick={loadCards}
              style={{
                padding: '6px 16px', background: 'var(--accent-blue)', color: '#fff',
                border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
              }}
            >
              刷新
            </button>
          </div>

          {/* Stats */}
          {stats && (
            <div style={{
              display: 'flex', gap: '16px', margin: '0 20px 16px', flexWrap: 'wrap',
            }}>
              {[
                { label: '总卡片数', value: stats.total_cards, color: 'var(--accent-blue)' },
                { label: '覆盖国家', value: `${stats.countries} 个`, color: '#d29922' },
                { label: '平均年费', value: `$${stats.avg_annual_fee.toFixed(0)}`, color: '#8b949e' },
                { label: '最高开卡奖励', value: `$${stats.highest_bonus}`, color: '#3fb950' },
              ].map(s => (
                <div key={s.label} style={{
                  flex: '1 1 160px', padding: '16px', background: 'var(--bg-secondary)',
                  borderRadius: '8px', border: '1px solid var(--border-primary)',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Card List */}
          {loading ? (
            <LoadingSpinner />
          ) : error ? (
            <ErrorBanner message={error} onRetry={loadCards} />
          ) : (
            <div style={{ margin: '0 20px' }}>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                共 {total} 张卡片
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {cards.map(card => (
                  <CardListItem
                    key={card.id}
                    card={card}
                    isComparing={compareIdSet.has(card.id)}
                    onToggleCompare={toggleCompare}
                  />
                ))}
                {cards.length === 0 && <EmptyState message="暂无符合条件的卡片数据" />}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============== Tab 2: Compare ============== */}
      {activeTab === 'compare' && (
        <div style={{ margin: '0 20px' }}>
          {/* Card selector */}
          <div style={{
            padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
            border: '1px solid var(--border-primary)', marginBottom: '16px',
          }}>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
              选择对比卡片（最多5张）
              {compareIds.length > 0 && (
                <span style={{ fontSize: '12px', color: 'var(--accent-blue)', marginLeft: '10px' }}>
                  已选 {compareIds.length} 张
                </span>
              )}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {cards.map(card => {
                const selected = compareIdSet.has(card.id)
                return (
                  <label key={card.id} style={{
                    display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px',
                    borderRadius: '6px', cursor: 'pointer', fontSize: '13px',
                    background: selected ? 'rgba(88, 166, 255, 0.15)' : 'var(--bg-primary)',
                    border: selected ? '1px solid #58a6ff' : '1px solid var(--border-primary)',
                    color: 'var(--text-primary)',
                    opacity: !selected && compareIds.length >= 5 ? 0.4 : 1,
                  }}>
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleCompare(card.id)}
                      disabled={!selected && compareIds.length >= 5}
                    />
                    {card.issuer} - {card.name}
                  </label>
                )
              })}
              {cards.length === 0 && (
                <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                  请先在"卡片浏览"页加载卡片数据
                </span>
              )}
            </div>
            {compareIds.length > 0 && (
              <button
                onClick={clearCompare}
                style={{
                  marginTop: '10px', padding: '4px 12px', fontSize: '12px',
                  background: 'transparent', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', color: 'var(--text-muted)', cursor: 'pointer',
                }}
              >
                清除选择
              </button>
            )}
          </div>

          {/* Compare Table */}
          {compareLoading ? (
            <LoadingSpinner />
          ) : compareError ? (
            <ErrorBanner message={compareError} onRetry={loadCompare} />
          ) : compareCards.length > 0 ? (
            <CompareTable cards={compareCards} />
          ) : (
            <EmptyState message="请从上方选择要对比的卡片" />
          )}
        </div>
      )}

      {/* ============== Tab 3: Recommend ============== */}
      {activeTab === 'recommend' && (
        <div style={{ margin: '0 20px' }}>
          <div style={{
            padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
            border: '1px solid var(--border-primary)', marginBottom: '16px',
            display: 'flex', alignItems: 'center', gap: '12px',
          }}>
            <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
              按开卡奖励价值排序
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              筛选出奖励价值最高的卡片，适合追求开卡奖励的用户
            </span>
          </div>

          {recommendLoading ? (
            <LoadingSpinner />
          ) : recommendError ? (
            <ErrorBanner message={recommendError} onRetry={loadRecommend} />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {recommendCards.map((card, idx) => (
                <RecommendCardItem key={card.id} card={card} rank={idx + 1} />
              ))}
              {recommendCards.length === 0 && <EmptyState message="暂无推荐数据" />}
            </div>
          )}
        </div>
      )}

      {/* Bottom Notes */}
      <div className="arb-notes" style={{ margin: '16px 20px' }}>
        <h3>使用说明</h3>
        <div className="arb-notes-grid">
          <div className="arb-note-item">
            <h4>数据来源</h4>
            <ul>
              <li>卡片信息来源于各金融机构官网公开数据</li>
              <li>年费、权益等信息以发卡行最新公告为准</li>
              <li>开卡奖励价值为估算值，实际价值可能因兑换方式而异</li>
            </ul>
          </div>
          <div className="arb-note-item">
            <h4>评分说明</h4>
            <ul>
              <li>综合评分基于年费、权益、奖励、申请门槛等维度</li>
              <li>评分仅供参考，不同用户需求下最优选择不同</li>
              <li>建议结合自身消费习惯和出行需求选择</li>
            </ul>
          </div>
          <div className="arb-note-item">
            <h4>对比功能</h4>
            <ul>
              <li>最多可同时对比5张卡片</li>
              <li>对比维度包括年费、奖励、权益、申请要求等</li>
              <li>建议重点关注与自身消费场景匹配的核心权益</li>
            </ul>
          </div>
          <div className="arb-note-item">
            <h4>注意事项</h4>
            <ul>
              <li>信用卡申请需满足发卡行的资质要求</li>
              <li>开卡奖励通常有消费门槛和时间限制</li>
              <li>合理用卡，按时还款，避免产生不必要的利息和费用</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

// ============== Compare table sub-component ==============

const COMPARE_ROWS: Array<{ label: string; fn: (c: Card) => string }> = [
  { label: '发卡行', fn: c => c.issuer },
  { label: '卡网络', fn: c => c.card_network },
  { label: '卡类型', fn: c => c.card_type },
  { label: '国家', fn: c => c.country },
  { label: '评分', fn: c => `${c.rating.toFixed(1)} / 5.0` },
  { label: '年费', fn: c => c.annual_fee === 0 ? '免年费' : `${c.currency} ${c.annual_fee}` },
  { label: '年费减免', fn: c => c.annual_fee_waiver || '-' },
  { label: '开卡奖励', fn: c => c.signup_bonus || '无' },
  { label: '奖励价值', fn: c => c.signup_bonus_value > 0 ? `$${c.signup_bonus_value}` : '-' },
  { label: '奖励要求', fn: c => c.signup_bonus_requirement || '-' },
  { label: '返现类型', fn: c => c.rewards_type || '-' },
  { label: '外币手续费', fn: c => c.foreign_transaction_fee === 0 ? '免费' : `${c.foreign_transaction_fee}%` },
  { label: '收入要求', fn: c => c.income_requirement || '-' },
  { label: '信用分要求', fn: c => c.credit_score_requirement || '-' },
  { label: '最适合', fn: c => c.best_for || '-' },
]

function CompareTable({ cards }: { cards: Card[] }) {
  return (
    <div className="table-container">
      <table className="arb-table">
        <thead>
          <tr>
            <th style={{ minWidth: 140 }}>属性</th>
            {cards.map(c => (
              <th key={c.id} style={{ minWidth: 180 }}>{c.issuer} {c.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {COMPARE_ROWS.map(row => (
            <tr key={row.label}>
              <td style={{ fontWeight: 600, color: 'var(--text-muted)', fontSize: '13px' }}>{row.label}</td>
              {cards.map(c => (
                <td key={c.id} style={{ fontSize: '13px' }}>{row.fn(c)}</td>
              ))}
            </tr>
          ))}
          {/* Rewards Rate row */}
          <tr>
            <td style={{ fontWeight: 600, color: 'var(--text-muted)', fontSize: '13px' }}>返现规则</td>
            {cards.map(c => (
              <td key={c.id} style={{ fontSize: '12px' }}>
                {c.rewards_rate && Object.keys(c.rewards_rate).length > 0
                  ? Object.entries(c.rewards_rate).map(([k, v]) => `${k}: ${v}%`).join(', ')
                  : '-'}
              </td>
            ))}
          </tr>
          {/* Key Perks row */}
          <tr>
            <td style={{ fontWeight: 600, color: 'var(--text-muted)', fontSize: '13px' }}>核心权益</td>
            {cards.map(c => (
              <td key={c.id} style={{ fontSize: '12px' }}>
                {c.key_perks && c.key_perks.length > 0 ? c.key_perks.join('、') : '-'}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  )
}

// ============== Recommend card item sub-component ==============

function RecommendCardItem({ card, rank }: { card: Card; rank: number }) {
  return (
    <div style={{
      display: 'flex', gap: '20px', alignItems: 'center',
      background: 'var(--bg-secondary)', borderRadius: '8px',
      border: '1px solid var(--border-primary)', padding: '16px 20px',
    }}>
      {/* Rank */}
      <div style={{
        width: '40px', height: '40px', borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '18px', fontWeight: 700, flexShrink: 0,
        background: rank <= 3 ? 'rgba(248, 81, 73, 0.15)' : 'var(--bg-primary)',
        color: rank <= 3 ? '#f85149' : 'var(--text-muted)',
      }}>
        {rank}
      </div>

      {/* Info */}
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <Badge bg="rgba(88, 166, 255, 0.15)" color="#58a6ff">{card.issuer}</Badge>
          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{card.country}</span>
        </div>
        <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
          {card.name}
        </div>
        {card.signup_bonus && (
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {card.signup_bonus}
            {card.signup_bonus_requirement && (
              <span style={{ fontSize: '12px', color: '#8b949e' }}> | {card.signup_bonus_requirement}</span>
            )}
          </div>
        )}
        {card.key_perks && card.key_perks.length > 0 && (
          <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {card.key_perks.slice(0, 4).map((perk, i) => (
              <span key={i} style={{
                fontSize: '11px', padding: '2px 8px', borderRadius: '3px',
                background: 'rgba(63, 185, 80, 0.1)', color: '#3fb950',
              }}>
                {perk}
              </span>
            ))}
            {card.key_perks.length > 4 && (
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                +{card.key_perks.length - 4}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Right Side Stats */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: '24px', fontWeight: 700, color: '#3fb950' }}>
          ${card.signup_bonus_value}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px' }}>奖励价值</div>
        <div style={{ fontSize: '13px', color: getFeeColor(card.annual_fee), fontWeight: 600 }}>
          {card.annual_fee === 0 ? '免年费' : `年费 ${card.currency} ${card.annual_fee}`}
        </div>
        <div style={{
          fontSize: '14px', fontWeight: 600, color: getRatingColor(card.rating), marginTop: '4px',
        }}>
          {card.rating.toFixed(1)} 评分
        </div>
      </div>
    </div>
  )
}
