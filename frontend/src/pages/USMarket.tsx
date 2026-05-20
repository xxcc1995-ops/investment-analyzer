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
      // 获取报价
      const quoteEndpoint = activeTab === 'equity'
        ? `${API_BASE}/openbb/equity/quote/${sym}`
        : `${API_BASE}/openbb/crypto/quote/${sym}`
      const quoteRes = await axios.get(quoteEndpoint)
      setQuote(quoteRes.data)

      // 获取历史价格
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

  // 热门标的
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
              {loading && <span style={{ color: '#1890ff', marginLeft: '8px' }}>加载中...</span>}
            </span>
          </div>
        </div>
      </div>

      {/* Tab切换 */}
      <div style={{
        display: 'flex', gap: '8px', padding: '12px 20px',
        borderBottom: '1px solid var(--border)', background: 'var(--bg)',
      }}>
        {(['equity', 'crypto'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setQuote(null); setPrices([]); setSymbol(''); setError(''); }}
            style={{
              padding: '8px 20px', borderRadius: '6px',
              border: '1px solid ' + (activeTab === tab ? '#1e3799' : 'var(--border)'),
              background: activeTab === tab ? '#1e3799' : '#fff',
              color: activeTab === tab ? '#fff' : '#333',
              cursor: 'pointer', fontSize: '13px', fontWeight: activeTab === tab ? 600 : 400,
            }}
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
              border: '1px solid var(--border)', fontSize: '14px',
            }}
          />
          <button
            type="submit"
            style={{
              padding: '10px 20px', background: '#1890ff', color: '#fff',
              border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '14px',
            }}
          >
            查询
          </button>
        </form>

        {/* 热门标的 */}
        <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ color: '#999', fontSize: '12px', lineHeight: '28px' }}>热门：</span>
          {hotSymbols.map(sym => (
            <button
              key={sym}
              onClick={() => { setSymbol(sym); fetchQuote(sym); }}
              style={{
                padding: '4px 12px', borderRadius: '4px',
                border: '1px solid var(--border)', background: '#fff',
                cursor: 'pointer', fontSize: '12px', color: '#1890ff',
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
          <div style={{
            background: '#fff2f0', border: '1px solid #ffccc7',
            borderRadius: '6px', padding: '12px 16px', color: '#cf1322', fontSize: '13px',
          }}>
            {error}
          </div>
        </div>
      )}

      {/* 报价信息 */}
      {quote && (
        <div style={{ padding: '0 20px 16px' }}>
          <div style={{
            background: 'var(--bg)', borderRadius: '8px', padding: '20px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: '24px', fontWeight: 700 }}>{quote.symbol}</div>
                <div style={{ fontSize: '32px', fontWeight: 700, marginTop: '8px' }}>
                  ${quote.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </div>
                <div style={{
                  fontSize: '16px', marginTop: '4px',
                  color: quote.change >= 0 ? '#cf1322' : '#3f8600',
                }}>
                  {quote.change >= 0 ? '+' : ''}{quote.change.toFixed(2)}
                  ({quote.change_pct >= 0 ? '+' : ''}{quote.change_pct.toFixed(2)}%)
                </div>
              </div>
              <div style={{ textAlign: 'right', fontSize: '13px', color: '#666' }}>
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
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: '10px 8px', color: '#666' }}>日期</th>
                <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666' }}>开盘</th>
                <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666' }}>最高</th>
                <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666' }}>最低</th>
                <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666' }}>收盘</th>
                <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666' }}>涨跌幅</th>
                <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666' }}>成交量</th>
              </tr>
            </thead>
            <tbody>
              {prices.slice(-30).reverse().map((item, idx) => {
                const changePct = item.open > 0 ? ((item.close - item.open) / item.open * 100) : 0
                return (
                  <tr key={idx} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '10px 8px' }}>{item.date}</td>
                    <td style={{ textAlign: 'right', padding: '10px 8px' }}>${item.open.toFixed(2)}</td>
                    <td style={{ textAlign: 'right', padding: '10px 8px' }}>${item.high.toFixed(2)}</td>
                    <td style={{ textAlign: 'right', padding: '10px 8px' }}>${item.low.toFixed(2)}</td>
                    <td style={{ textAlign: 'right', padding: '10px 8px', fontWeight: 600 }}>${item.close.toFixed(2)}</td>
                    <td style={{
                      textAlign: 'right', padding: '10px 8px',
                      color: changePct >= 0 ? '#cf1322' : '#3f8600',
                    }}>
                      {changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%
                    </td>
                    <td style={{ textAlign: 'right', padding: '10px 8px' }}>
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
        <div style={{
          background: 'var(--bg)', borderRadius: '8px', padding: '16px',
          fontSize: '12px', color: '#666', lineHeight: '1.8',
        }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: '#333' }}>数据说明</div>
          <div>数据来源：OpenBB Platform (Yahoo Finance)</div>
          <div>支持美股、加密货币的实时行情和历史数据</div>
          <div style={{ marginTop: '8px', color: '#999' }}>
            提示：输入代码后点击查询或按回车
          </div>
        </div>
      </div>
    </div>
  )
}
