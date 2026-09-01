import { memo } from 'react'
import { Input, Tooltip } from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'

interface SearchItem {
  code: string
  name: string
  market?: string
}

interface BondYield {
  yield?: number
  change?: number
  pe?: number
  stock_bond_ratio?: number
  earnings_yield?: number
  spread?: number
}

interface TopBarProps {
  // 搜索
  searchKeyword: string
  onSearchChange: (value: string) => void
  searchResults: SearchItem[]
  showSearch: boolean
  onShowSearch: (show: boolean) => void
  searchLoading: boolean
  onSelectStock: (code: string) => void
  searchBoxRef: React.RefObject<HTMLDivElement>
  // 国债收益率
  bondYields: { cn: BondYield; us: BondYield } | null
  bondLoading: boolean
  onRefreshBonds: () => void
}

const TopBar = memo(function TopBar({
  searchKeyword,
  onSearchChange,
  searchResults,
  showSearch,
  onShowSearch,
  searchLoading,
  onSelectStock,
  searchBoxRef,
  bondYields,
  bondLoading,
  onRefreshBonds,
}: TopBarProps) {
  return (
    <div style={{
      height: 56,
      background: '#161b22',
      borderBottom: '1px solid #30363d',
      display: 'flex',
      alignItems: 'center',
      padding: '0 20px',
      gap: 24,
      flexShrink: 0,
    }}>
      {/* 左侧：Logo + 标语 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{
          fontSize: 17,
          fontWeight: 700,
          color: '#e6edf3',
          letterSpacing: 0.5,
          whiteSpace: 'nowrap',
        }}>
          <span style={{ color: '#58a6ff' }}>新源</span>Invest
        </div>
        <Tooltip title="不被自媒体带节奏 · 拆解问题 · 补齐证据链 · 用概率表达">
          <div style={{
            fontSize: 11,
            color: '#d29922',
            background: 'rgba(210,153,34,0.1)',
            padding: '2px 8px',
            borderRadius: 4,
            cursor: 'default',
            whiteSpace: 'nowrap',
          }}>
            💡 拆解问题 · 用概率表达
          </div>
        </Tooltip>
      </div>

      {/* 中间：搜索框 */}
      <div ref={searchBoxRef} style={{ position: 'relative', flex: 1, maxWidth: 480 }}>
        <Input
          prefix={<SearchOutlined style={{ color: '#484f58' }} />}
          placeholder="输入股票代码或名称搜索..."
          value={searchKeyword}
          onChange={e => { onSearchChange(e.target.value); onShowSearch(true) }}
          onFocus={() => { if (searchKeyword) onShowSearch(true) }}
          style={{
            background: '#0d1117',
            borderColor: '#30363d',
            color: '#e6edf3',
            borderRadius: 6,
          }}
          allowClear
        />
        {showSearch && searchKeyword && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '0 0 6px 6px',
            maxHeight: 300,
            overflowY: 'auto',
            zIndex: 100,
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          }}>
            {searchLoading ? (
              <div style={{ padding: 12, textAlign: 'center', color: '#484f58', fontSize: 13 }}>搜索中...</div>
            ) : searchResults.length > 0 ? (
              searchResults.map(item => (
                <div
                  key={item.code}
                  onMouseDown={e => { e.preventDefault(); onSelectStock(item.code) }}
                  style={{
                    padding: '10px 12px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    color: '#e6edf3',
                    transition: 'background 0.2s',
                    fontSize: 13,
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#1f2937')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <span style={{ minWidth: 60, color: '#484f58', fontSize: 13 }}>{item.code}</span>
                  {item.market === 'HK' && (
                    <span style={{ fontSize: 11, padding: '1px 5px', borderRadius: 3, background: 'rgba(255,152,0,0.15)', color: '#ff9800' }}>港</span>
                  )}
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                </div>
              ))
            ) : (
              <div style={{ padding: 12, textAlign: 'center', color: '#484f58', fontSize: 13 }}>未找到相关股票</div>
            )}
          </div>
        )}
      </div>

      {/* 右侧：国债收益率 */}
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexShrink: 0 }}>
        <div
          onClick={onRefreshBonds}
          style={{ cursor: 'pointer', color: '#58a6ff', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
        >
          <ReloadOutlined spin={bondLoading} style={{ fontSize: 12 }} />
        </div>

        {/* 中国国债 */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 10, color: '#484f58', lineHeight: 1.2 }}>中国10Y</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#f85149', lineHeight: 1.3 }}>
            {bondYields?.cn?.yield?.toFixed(2) ?? '--'}%
          </div>
          <div style={{
            fontSize: 10,
            color: (bondYields?.cn?.change ?? 0) >= 0 ? '#f85149' : '#3fb950',
            lineHeight: 1.2,
          }}>
            {bondYields?.cn?.change != null
              ? `${bondYields.cn.change >= 0 ? '+' : ''}${bondYields.cn.change.toFixed(3)}`
              : '--'}
          </div>
        </div>

        {/* 分隔线 */}
        <div style={{ width: 1, height: 28, background: '#30363d' }} />

        {/* 美国国债 */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 10, color: '#484f58', lineHeight: 1.2 }}>美国10Y</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#58a6ff', lineHeight: 1.3 }}>
            {bondYields?.us?.yield?.toFixed(2) ?? '--'}%
          </div>
          <div style={{
            fontSize: 10,
            color: (bondYields?.us?.change ?? 0) >= 0 ? '#f85149' : '#3fb950',
            lineHeight: 1.2,
          }}>
            {bondYields?.us?.change != null
              ? `${bondYields.us.change >= 0 ? '+' : ''}${bondYields.us.change.toFixed(3)}`
              : '--'}
          </div>
        </div>

        {/* 分隔线 */}
        <div style={{ width: 1, height: 28, background: '#30363d' }} />

        {/* 股债比 */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 10, color: '#484f58', lineHeight: 1.2 }}>股债比</div>
          <div style={{ display: 'flex', gap: 10, marginTop: 2 }}>
            <div>
              <span style={{ fontSize: 10, color: '#8b949e' }}>CN </span>
              <span style={{
                fontSize: 13,
                fontWeight: 600,
                color: (bondYields?.cn?.stock_bond_ratio ?? 0) > 1 ? '#3fb950' : '#f85149',
              }}>
                {bondYields?.cn?.stock_bond_ratio?.toFixed(2) ?? '--'}
              </span>
            </div>
            <div>
              <span style={{ fontSize: 10, color: '#8b949e' }}>US </span>
              <span style={{
                fontSize: 13,
                fontWeight: 600,
                color: (bondYields?.us?.stock_bond_ratio ?? 0) > 1 ? '#3fb950' : '#f85149',
              }}>
                {bondYields?.us?.stock_bond_ratio?.toFixed(2) ?? '--'}
              </span>
            </div>
          </div>
        </div>

        {/* 分隔线 */}
        <div style={{ width: 1, height: 28, background: '#30363d' }} />

        {/* 美债10Y − 盈利收益率 差值 */}
        <Tooltip
          title={
            <div style={{ fontSize: 12, lineHeight: 1.7, maxWidth: 280 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>差值 = 美债10Y收益率 − 标普500盈利收益率</div>
              <div><span style={{ color: '#3fb950' }}>缩窄</span>（长债降得快）→ 股权风险溢价↑ → 股市涨</div>
              <div><span style={{ color: '#f85149' }}>走阔</span>（盈利跌更快）→ 高开低走 / 债涨股跌背离</div>
            </div>
          }
        >
          <div style={{ textAlign: 'right', cursor: 'default' }}>
            <div style={{ fontSize: 10, color: '#484f58', lineHeight: 1.2 }}>美债-盈利收益差</div>
            <div style={{
              fontSize: 14,
              fontWeight: 600,
              lineHeight: 1.3,
              color: bondYields?.us?.spread == null
                ? '#8b949e'
                : (bondYields.us.spread < 0 ? '#3fb950' : '#f85149'),
            }}>
              {bondYields?.us?.spread != null
                ? `${bondYields.us.spread >= 0 ? '+' : ''}${bondYields.us.spread.toFixed(2)}%`
                : '--'}
            </div>
            <div style={{ fontSize: 10, color: '#8b949e', lineHeight: 1.2 }}>
              {bondYields?.us?.earnings_yield != null
                ? `盈利收益率 ${bondYields.us.earnings_yield.toFixed(2)}%`
                : '\u00A0'}
            </div>
          </div>
        </Tooltip>
      </div>
    </div>
  )
})

export default TopBar
