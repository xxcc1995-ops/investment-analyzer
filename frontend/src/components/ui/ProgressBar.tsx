import { type CSSProperties } from 'react'

interface ProgressBarProps {
  value: number
  max?: number
  color?: string
  showLabel?: boolean
  label?: string
  height?: number
  style?: CSSProperties
  className?: string
}

/**
 * 进度条 - 替代各页面中重复的手动 CSS 进度条
 */
export default function ProgressBar({
  value, max = 100, color, showLabel = true, label, height = 6, style, className
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))

  const getAutoColor = (): string => {
    if (color) return color
    if (pct >= 80) return 'var(--accent-green)'
    if (pct >= 50) return 'var(--accent-blue)'
    if (pct >= 30) return 'var(--accent-orange)'
    return 'var(--accent-red)'
  }

  return (
    <div className={`ui-progress ${className || ''}`} style={style}>
      {showLabel && (
        <div className="ui-progress__label">
          <span>{label}</span>
          <span>{pct.toFixed(1)}%</span>
        </div>
      )}
      <div className="ui-progress__track" style={{ height }}>
        <div
          className="ui-progress__fill"
          style={{ width: `${pct}%`, backgroundColor: getAutoColor() }}
        />
      </div>
    </div>
  )
}
