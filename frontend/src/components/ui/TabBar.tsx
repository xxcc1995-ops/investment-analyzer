import { type CSSProperties, type ReactNode } from 'react'

interface Tab {
  key: string
  label: string
  icon?: ReactNode
  badge?: number | string
}

interface TabBarProps {
  tabs: Tab[]
  activeKey: string
  onChange: (key: string) => void
  style?: CSSProperties
  className?: string
  /** 尺寸 */
  size?: 'small' | 'medium'
}

/**
 * 标签栏 - 替代各页面中重复的自定义 tab 按钮组
 */
export default function TabBar({ tabs, activeKey, onChange, style, className, size = 'medium' }: TabBarProps) {
  return (
    <div
      className={`ui-tab-bar ${size === 'small' ? 'ui-tab-bar--sm' : ''} ${className || ''}`}
      style={style}
    >
      {tabs.map(tab => (
        <button
          key={tab.key}
          className={`ui-tab-bar__item ${tab.key === activeKey ? 'ui-tab-bar__item--active' : ''}`}
          onClick={() => onChange(tab.key)}
        >
          {tab.icon && <span className="ui-tab-bar__icon">{tab.icon}</span>}
          {tab.label}
          {tab.badge !== undefined && (
            <span className="ui-tab-bar__badge">{tab.badge}</span>
          )}
        </button>
      ))}
    </div>
  )
}
