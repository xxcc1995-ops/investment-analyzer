import { memo, type CSSProperties } from 'react'
import { LoadingOutlined } from '@ant-design/icons'

interface LoadingSpinnerProps {
  text?: string
  size?: 'small' | 'default' | 'large'
  style?: CSSProperties
  className?: string
}

/**
 * 加载中状态 - 替代各页面中重复的 loading/spinner 模式
 */
const LoadingSpinner = memo(function LoadingSpinner({ text = '加载中...', size = 'default', style, className }: LoadingSpinnerProps) {
  const iconSize = size === 'small' ? 14 : size === 'large' ? 32 : 20

  return (
    <div className={`ui-loading ${className || ''}`} style={style}>
      <LoadingOutlined style={{ fontSize: iconSize }} />
      {text && <span className="ui-loading__text">{text}</span>}
    </div>
  )
})

export default LoadingSpinner
