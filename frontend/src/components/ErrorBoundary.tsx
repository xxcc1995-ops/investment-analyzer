import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * 全局错误边界组件
 * 捕获子组件渲染错误，防止整个应用崩溃
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] 捕获到渲染错误:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          minHeight: '40vh', padding: 40, textAlign: 'center',
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>💥</div>
          <h2 style={{ color: '#e6edf3', marginBottom: 8, fontSize: 18 }}>页面渲染出错</h2>
          <p style={{ color: '#8b949e', marginBottom: 24, maxWidth: 480, fontSize: 14 }}>
            {this.state.error?.message || '未知错误'}
          </p>
          <button
            onClick={this.handleReset}
            style={{
              padding: '8px 24px', borderRadius: 6, border: '1px solid #30363d',
              background: '#21262d', color: '#e6edf3', cursor: 'pointer', fontSize: 14,
            }}
          >
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
