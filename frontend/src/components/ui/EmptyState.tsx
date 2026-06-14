import { type CSSProperties, type ReactNode } from 'react'
import { InboxOutlined } from '@ant-design/icons'

interface EmptyStateProps {
  icon?: ReactNode
  title?: string
  description?: string
  action?: ReactNode
  style?: CSSProperties
  className?: string
}

/**
 * 空状态 - 替代各页面中重复的 empty-state 模式
 */
export default function EmptyState({
  icon, title = '暂无数据', description, action, style, className
}: EmptyStateProps) {
  return (
    <div className={`ui-empty ${className || ''}`} style={style}>
      <div className="ui-empty__icon">{icon || <InboxOutlined />}</div>
      <div className="ui-empty__title">{title}</div>
      {description && <div className="ui-empty__desc">{description}</div>}
      {action && <div className="ui-empty__action">{action}</div>}
    </div>
  )
}
