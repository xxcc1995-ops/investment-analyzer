import { type CSSProperties, type ReactNode } from 'react'

type BadgeStatus = 'success' | 'warning' | 'error' | 'info' | 'default'

interface StatusBadgeProps {
  status?: BadgeStatus
  color?: string
  text?: ReactNode
  dot?: boolean
  style?: CSSProperties
  className?: string
}

/**
 * 状态徽章 - 用于展示状态标记
 */
export default function StatusBadge({ status = 'default', color, text, dot = true, style, className }: StatusBadgeProps) {
  const statusColors: Record<BadgeStatus, string> = {
    success: 'var(--accent-green)',
    warning: 'var(--accent-orange)',
    error: 'var(--accent-red)',
    info: 'var(--accent-blue)',
    default: 'var(--text-muted)',
  }

  const dotColor = color || statusColors[status]

  return (
    <span className={`ui-badge ${className || ''}`} style={style}>
      {dot && <span className="ui-badge__dot" style={{ backgroundColor: dotColor }} />}
      {text && <span className="ui-badge__text">{text}</span>}
    </span>
  )
}

interface TagProps {
  color?: string
  children: ReactNode
  style?: CSSProperties
  className?: string
}

/** 标签 - 用于分类标记 */
export function Tag({ color = 'var(--accent-blue)', children, style, className }: TagProps) {
  return (
    <span
      className={`ui-tag ${className || ''}`}
      style={{ '--tag-color': color, ...style } as CSSProperties}
    >
      {children}
    </span>
  )
}
