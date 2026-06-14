import { type CSSProperties, type ReactNode } from 'react'

export interface Column<T = any> {
  key: string
  title: string
  dataIndex?: string
  render?: (value: any, record: T, index: number) => ReactNode
  align?: 'left' | 'center' | 'right'
  width?: number | string
  sortable?: boolean
  /** 值为正时绿色，负时红时 */
  colorize?: boolean
}

interface DataTableProps<T = any> {
  columns: Column<T>[]
  data: T[]
  rowKey?: string | ((record: T, index: number) => string)
  loading?: boolean
  emptyText?: string
  style?: CSSProperties
  className?: string
  compact?: boolean
  striped?: boolean
  onRowClick?: (record: T) => void
}

/**
 * 通用数据表格 - 替代各页面中重复的原生 <table> 模式
 * 轻量封装，不依赖antd Table（保持灵活性）
 */
export default function DataTable<T extends Record<string, any>>({
  columns, data, rowKey = 'id', loading, emptyText = '暂无数据',
  style, className, compact, striped, onRowClick
}: DataTableProps<T>) {
  if (loading) {
    return <div className="ui-table__loading">加载中...</div>
  }

  if (!data || data.length === 0) {
    return <div className="ui-table__empty">{emptyText}</div>
  }

  const getRowKey = (record: T, index: number): string => {
    if (typeof rowKey === 'function') return rowKey(record, index)
    return record[rowKey] ?? String(index)
  }

  const getValue = (record: T, dataIndex?: string): any => {
    if (!dataIndex) return undefined
    return dataIndex.split('.').reduce((obj, key) => obj?.[key], record as any)
  }

  const getAlign = (align?: string): CSSProperties['textAlign'] => {
    if (align === 'right') return 'right'
    if (align === 'center') return 'center'
    return 'left'
  }

  const getColor = (column: Column<T>, value: any): string | undefined => {
    if (!column.colorize) return undefined
    const num = typeof value === 'number' ? value : parseFloat(value)
    if (isNaN(num)) return undefined
    if (num > 0) return 'var(--accent-green)'
    if (num < 0) return 'var(--accent-red)'
    return undefined
  }

  return (
    <div
      className={`ui-table-container ${compact ? 'ui-table-container--compact' : ''} ${className || ''}`}
      style={style}
    >
      <table className={`ui-table ${striped ? 'ui-table--striped' : ''}`}>
        <thead>
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                style={{ textAlign: getAlign(col.align), width: col.width }}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((record, index) => (
            <tr
              key={getRowKey(record, index)}
              onClick={onRowClick ? () => onRowClick(record) : undefined}
              style={onRowClick ? { cursor: 'pointer' } : undefined}
            >
              {columns.map(col => {
                const value = getValue(record, col.dataIndex)
                const rendered = col.render ? col.render(value, record, index) : value
                const color = col.render ? undefined : getColor(col, value)
                return (
                  <td
                    key={col.key}
                    style={{ textAlign: getAlign(col.align), color }}
                  >
                    {rendered ?? '-'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
