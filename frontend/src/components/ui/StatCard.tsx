import { memo, type CSSProperties, type ReactNode } from 'react'

interface StatCardProps {
  label: string
  value: ReactNode
  suffix?: string
  color?: string
  icon?: ReactNode
  onClick?: () => void
  style?: CSSProperties
  className?: string
}

/**
 * 指标卡片 - 用于展示单个数值指标
 * 替代各页面中重复的 metric-card / stat-card 模式
 */
const StatCard = memo(function StatCard({ label, value, suffix, color, icon, onClick, style, className }: StatCardProps) {
  return (
    <div
      className={`ui-stat-card ${className || ''}`}
      style={{ ...style, cursor: onClick ? 'pointer' : undefined }}
      onClick={onClick}
    >
      {icon && <span className="ui-stat-card__icon">{icon}</span>}
      <div className="ui-stat-card__content">
        <div className="ui-stat-card__label">{label}</div>
        <div className="ui-stat-card__value" style={color ? { color } : undefined}>
          {value}
          {suffix && <span className="ui-stat-card__suffix">{suffix}</span>}
        </div>
      </div>
    </div>
  )
})

export default StatCard

interface StatCardGroupProps {
  children: ReactNode
  columns?: number
  style?: CSSProperties
}

/** 指标卡片组 - 网格布局容器 */
export const StatCardGroup = memo(function StatCardGroup({ children, columns = 4, style }: StatCardGroupProps) {
  return (
    <div
      className="ui-stat-card-group"
      style={{ gridTemplateColumns: `repeat(${columns}, 1fr)`, ...style }}
    >
      {children}
    </div>
  )
})
