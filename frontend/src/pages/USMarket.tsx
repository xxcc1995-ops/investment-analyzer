import { useState, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface QuoteData {
  symbol: string
  price: number
  change: number
  change_pct: number
  volume: number
  market_cap: number | null
  pe_ratio: number | null
  fifty_two_week_high: number | null
  fifty_two_week_low: number | null
}

interface PriceData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export default function USMarket() {
  const [activeTab, setActiveTab] = useState<'equity' | 'crypto'>('equity')
  const [symbol, setSymbol] = useState('')
  const [quote, setQuote] = useState<QuoteData | null>(null)
  const [prices, setPrices] = useState<PriceData[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchQuote = useCallback(async (sym: string) => {
    setLoading(true)
    setError('')
    try {
      const quoteEndpoint = activeTab === 'equity'
        ? `${API_BASE}/openbb/equity/quote/${sym}`
        : `${API_BASE}/openbb/crypto/quote/${sym}`
      const quoteRes = await axios.get(quoteEndpoint)
      setQuote(quoteRes.data)

      const priceEndpoint = activeTab === 'equity'
        ? `${API_BASE}/openbb/equity/price/${sym}`
        : `${API_BASE}/openbb/crypto/price/${sym}`
      const priceRes = await axios.get(priceEndpoint)
      setPrices(priceRes.data.data || [])
    } catch (e: any) {
      setError(e.response?.data?.detail || '获取数据失败')
      setQuote(null)
      setPrices([])
    } finally {
      setLoading(false)
    }
  }, [activeTab])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (symbol.trim()) {
      fetchQuote(symbol.trim().toUpperCase())
    }
  }

  const hotSymbols = activeTab === 'equity'
    ? ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK-B']
    : ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'DOT']

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>美股/加密货币</h2>
            <span className="stock-code">
              基于 OpenBB 数据平台
              {loading && <span style={{ color: 'var(--accent-blue)', marginLeft: '8px' }}>加载中...</span>}
            </span>
          </div>
        </div>
      </div>

      {/* Tab切换 */}
      <div style={{
        display: 'flex', gap: '8px', padding: '12px 20px',
        borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)',
      }}>
        {(['equity', 'crypto'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setQuote(null); setPrices([]); setSymbol(''); setError(''); }}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
          >
            {tab === 'equity' ? '美股' : '加密货币'}
          </button>
        ))}
      </div>

      {/* 搜索框 */}
      <div style={{ padding: '16px 20px' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder={activeTab === 'equity' ? '输入美股代码 (如 AAPL)' : '输入加密货币代码 (如 BTC)'}
            style={{
              flex: 1, padding: '10px 14px', borderRadius: '6px',
              border: '1px solid var(--border-primary)', fontSize: '14px',
              background: 'var(--bg-input)', color: 'var(--text-primary)',
            }}
          />
          <button
            type="submit"
            className="btn-add"
            style={{ padding: '10px 20px', fontSize: '14px' }}
          >
            查询
          </button>
        </form>

        {/* 热门标的 */}
        <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '12px', lineHeight: '28px' }}>热门：</span>
          {hotSymbols.map(sym => (
            <button
              key={sym}
              onClick={() => { setSymbol(sym); fetchQuote(sym); }}
              style={{
                padding: '4px 12px', borderRadius: '4px',
                border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
                cursor: 'pointer', fontSize: '12px', color: 'var(--accent-blue)',
              }}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div style={{ padding: '0 20px' }}>
          <div className="alert-error">
            {error}
          </div>
        </div>
      )}

      {/* 报价信息 */}
      {quote && (
        <div style={{ padding: '0 20px 16px' }}>
          <div style={{
            background: 'var(--bg-tertiary)', borderRadius: '8px', padding: '20px',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: '24px', fontWeight: 700 }}>{quote.symbol}</div>
                <div style={{ fontSize: '32px', fontWeight: 700, marginTop: '8px' }}>
                  ${quote.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>
                <div style={{
                  fontSize: '16px', marginTop: '4px',
                  color: quote.change >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
                }}>
                  {quote.change >= 0 ? '+' : ''}{quote.change.toFixed(2)}
                  ({quote.change_pct >= 0 ? '+' : ''}{quote.change_pct.toFixed(2)}%)
                </div>
              </div>
              <div style={{ textAlign: 'right', fontSize: '13px', color: 'var(--text-secondary)' }}>
                {quote.volume > 0 && <div>成交量: {(quote.volume / 1e6).toFixed(1)}M</div>}
                {quote.market_cap && <div>市值: ${(quote.market_cap / 1e9).toFixed(1)}B</div>}
                {quote.pe_ratio && <div>PE: {quote.pe_ratio.toFixed(2)}</div>}
                {quote.fifty_two_week_high && <div>52周高: ${quote.fifty_two_week_high.toFixed(2)}</div>}
                {quote.fifty_two_week_low && <div>52周低: ${quote.fifty_two_week_low.toFixed(2)}</div>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 历史价格表格 */}
      {prices.length > 0 && (
        <div style={{ padding: '0 20px 20px', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>日期</th>
                <th>开盘</th>
                <th>最高</th>
                <th>最低</th>
                <th>收盘</th>
                <th>涨跌幅</th>
                <th>成交量</th>
              </tr>
            </thead>
            <tbody>
              {prices.slice(-30).reverse().map((item, idx) => {
                const changePct = item.open > 0 ? ((item.close - item.open) / item.open * 100) : 0
                return (
                  <tr key={idx}>
                    <td>{item.date}</td>
                    <td>${item.open.toFixed(2)}</td>
                    <td>${item.high.toFixed(2)}</td>
                    <td>${item.low.toFixed(2)}</td>
                    <td style={{ fontWeight: 600 }}>${item.close.toFixed(2)}</td>
                    <td style={{
                      color: changePct >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
                    }}>
                      {changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%
                    </td>
                    <td>
                      {(item.volume / 1e6).toFixed(1)}M
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 说明 */}
      <div style={{ padding: '0 20px 20px' }}>
        <div className="info-box">
          <div className="info-box-title">数据说明</div>
          <div>数据来源：OpenBB Platform (Yahoo Finance)</div>
          <div>支持美股、加密货币的实时行情和历史数据</div>
          <div style={{ marginTop: '8px', color: 'var(--text-muted)' }}>
            提示：输入代码后点击查询或按回车
          </div>
        </div>
      </div>
    </div>
  )
}
