import { memo, type CSSProperties, type ReactNode } from 'react'
import { ReloadOutlined } from '@ant-design/icons'

interface PageSectionProps {
  title?: string
  extra?: ReactNode
  onRefresh?: () => void
  refreshing?: boolean
  children: ReactNode
  style?: CSSProperties
  className?: string
  /** 紧凑模式 - 减少内边距 */
  compact?: boolean
}

/**
 * 页面区块容器 - 替代各页面中重复的 section/card 容器模式
 */
const PageSection = memo(function PageSection({
  title, extra, onRefresh, refreshing, children, style, className, compact
}: PageSectionProps) {
  return (
    <div
      className={`ui-section ${compact ? 'ui-section--compact' : ''} ${className || ''}`}
      style={style}
    >
      {(title || extra || onRefresh) && (
        <div className="ui-section__header">
          {title && <h3 className="ui-section__title">{title}</h3>}
          <div className="ui-section__extra">
            {extra}
            {onRefresh && (
              <ReloadOutlined
                className={`ui-section__refresh ${refreshing ? 'spinning' : ''}`}
                onClick={onRefresh}
              />
            )}
          </div>
        </div>
      )}
      <div className="ui-section__body">
        {children}
      </div>
    </div>
  )
})

export default PageSection
