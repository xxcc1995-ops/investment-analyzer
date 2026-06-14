/**
 * 每日资讯 - 工具函数
 */

/** 格式化百分比 */
export function formatPct(value: number | undefined | null, decimals = 2): string {
  if (value == null || isNaN(value)) return '--'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

/** 格式化大数字（亿/万） */
export function formatAmount(value: number | undefined | null): string {
  if (value == null || isNaN(value)) return '--'
  const abs = Math.abs(value)
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}万亿`
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(value / 1e4).toFixed(1)}万`
  return value.toFixed(0)
}

/** 格式化价格 */
export function formatPrice(value: number | undefined | null, decimals = 2): string {
  if (value == null || isNaN(value)) return '--'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/** 格式化大数字为美元（B/M） */
export function formatUSD(value: number | undefined | null): string {
  if (value == null || isNaN(value)) return '--'
  const abs = Math.abs(value)
  if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `$${(value / 1e3).toFixed(0)}K`
  return `$${value.toFixed(0)}`
}

/** 获取涨跌颜色 */
export function getChangeColor(value: number | undefined | null): string {
  if (value == null || isNaN(value) || value === 0) return 'var(--text-secondary)'
  return value > 0 ? 'var(--accent-red)' : 'var(--accent-green)'
}

/** 获取情绪评分颜色 */
export function getSentimentColor(score: number): string {
  if (score >= 75) return '#f85149' // 极度乐观 - 红
  if (score >= 60) return '#d29922' // 偏多 - 橙
  if (score >= 45) return '#8b949e' // 中性 - 灰
  if (score >= 30) return '#3fb950' // 偏空 - 绿
  return '#58a6ff' // 极度悲观 - 蓝
}

/** 获取情绪等级标签 */
export function getSentimentLabel(level: string): string {
  const map: Record<string, string> = {
    '极度乐观': '🔥 极度乐观',
    '偏多': '📈 偏多',
    '中性': '➡️ 中性',
    '偏空': '📉 偏空',
    '极度悲观': '🧊 极度悲观',
    '强势': '💪 强势',
    '弱势': '😰 弱势',
    '震荡': '⚡ 震荡',
  }
  return map[level] || level
}

/** 获取事件级别颜色 */
export function getEventLevelColor(level: string): string {
  switch (level) {
    case 'critical': return '#f85149'
    case 'high': return '#d29922'
    case 'medium': return '#58a6ff'
    default: return '#8b949e'
  }
}

/** 获取事件类型图标 */
export function getEventIcon(type: string): string {
  switch (type) {
    case 'market_shock': return '⚡'
    case 'sector_divergence': return '🔀'
    case 'fund_flow_shock': return '💰'
    case 'macro_alert': return '📊'
    case 'overseas_event': return '🌍'
    default: return '📌'
  }
}

/** 相对时间显示 */
export function relativeTime(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin}分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour}小时前`
    const diffDay = Math.floor(diffHour / 24)
    if (diffDay < 7) return `${diffDay}天前`
    return date.toLocaleDateString('zh-CN')
  } catch {
    return dateStr
  }
}

/** 截断文本 */
export function truncate(text: string, maxLen: number): string {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}
