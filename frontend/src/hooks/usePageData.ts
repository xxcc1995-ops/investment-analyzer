import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface UsePageDataOptions<T> {
  /** API端点路径（相对于 /api） */
  endpoint: string
  /** 初始数据 */
  initialData: T
  /** 请求参数 */
  params?: Record<string, any>
  /** 是否自动加载（默认true） */
  autoLoad?: boolean
  /** 请求超时时间（毫秒） */
  timeout?: number
  /** 数据转换函数 */
  transform?: (data: any) => T
  /** 错误回调 */
  onError?: (error: any) => void
}

interface UsePageDataResult<T> {
  /** 数据 */
  data: T
  /** 加载状态 */
  loading: boolean
  /** 错误信息 */
  error: string | null
  /** 刷新数据 */
  refresh: () => Promise<void>
  /** 手动设置数据 */
  setData: (data: T | ((prev: T) => T)) => void
  /** 更新参数并重新加载 */
  updateParams: (params: Record<string, any>) => void
}

/**
 * 通用页面数据加载Hook
 *
 * 用于替代各页面重复的 loading/error/data 模式
 * 内置竞态条件保护：快速连续调用只会应用最后一次请求的结果
 *
 * @example
 * ```tsx
 * const { data, loading, error, refresh } = usePageData({
 *   endpoint: 'index-valuation/data',
 *   initialData: { indices: [], update_time: '' },
 *   transform: (res) => ({ indices: res.indices || [], update_time: res.update_time || '' }),
 * })
 * ```
 */
export function usePageData<T>({
  endpoint,
  initialData,
  params,
  autoLoad = true,
  timeout = 30000,
  transform,
  onError,
}: UsePageDataOptions<T>): UsePageDataResult<T> {
  const [data, setData] = useState<T>(initialData)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentParams, setCurrentParams] = useState(params)

  // 用ref存储回调和参数，避免依赖不稳定导致不必要的重新创建refresh
  const transformRef = useRef(transform)
  transformRef.current = transform
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError
  const paramsRef = useRef(currentParams)
  paramsRef.current = currentParams

  // 竞态条件保护：请求计数器
  const requestCounter = useRef(0)

  const refresh = useCallback(async () => {
    const requestId = ++requestCounter.current
    setLoading(true)
    setError(null)
    try {
      const res = await axios.get(`${API_BASE}/${endpoint}`, {
        params: paramsRef.current,
        timeout,
      })
      // 只有当这次请求仍然是最新的才更新状态
      if (requestId === requestCounter.current) {
        const result = transformRef.current ? transformRef.current(res.data) : res.data
        setData(result)
      }
    } catch (e: any) {
      if (requestId === requestCounter.current) {
        const msg = e.response?.data?.detail || e.message || '数据加载失败'
        setError(msg)
        onErrorRef.current?.(e)
      }
    } finally {
      if (requestId === requestCounter.current) {
        setLoading(false)
      }
    }
  }, [endpoint, timeout])

  useEffect(() => {
    if (autoLoad) {
      refresh()
    }
  }, [autoLoad, refresh])

  const updateParams = useCallback((newParams: Record<string, any>) => {
    setCurrentParams(prev => {
      const merged = { ...prev, ...newParams }
      paramsRef.current = merged
      return merged
    })
  }, [])

  return { data, loading, error, refresh, setData, updateParams }
}

/**
 * 通用页面数据加载Hook（简化版）
 *
 * 用于只需要 loading/data/refresh 的简单场景
 *
 * @example
 * ```tsx
 * const { data, loading, refresh } = useSimplePageData(
 *   'index-valuation/data',
 *   { indices: [] }
 * )
 * ```
 */
export function useSimplePageData<T>(
  endpoint: string,
  initialData: T,
  params?: Record<string, any>
) {
  return usePageData({
    endpoint,
    initialData,
    params,
  })
}

/**
 * 多数据源页面Hook
 *
 * 用于同时加载多个API端点的场景
 * 内置竞态条件保护
 *
 * @example
 * ```tsx
 * const sources = useMemo(() => [
 *   { key: 'overview' as const, endpoint: 'macro/overview' },
 *   { key: 'china' as const, endpoint: 'macro/china' },
 * ], [])
 * const initialData = useMemo(() => ({ overview: {}, china: {} }), [])
 * const { data, loading, refresh } = useMultiPageData(sources, initialData)
 * ```
 */
export function useMultiPageData<T extends Record<string, any>>(
  sources: Array<{ key: keyof T; endpoint: string; params?: Record<string, any> }>,
  initialData: T,
  options?: { autoLoad?: boolean; timeout?: number }
) {
  const [data, setData] = useState<T>(initialData)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 用ref存储，避免依赖不稳定
  const sourcesRef = useRef(sources)
  sourcesRef.current = sources
  const initialDataRef = useRef(initialData)
  initialDataRef.current = initialData

  // 竞态条件保护
  const requestCounter = useRef(0)

  // 序列化sources用于依赖比较
  const sourcesKey = useMemo(() =>
    sources.map(s => `${String(s.key)}:${s.endpoint}`).join(','),
    [sources]
  )

  const refresh = useCallback(async () => {
    const requestId = ++requestCounter.current
    setLoading(true)
    setError(null)
    try {
      const currentSources = sourcesRef.current
      const results = await Promise.all(
        currentSources.map(s =>
          axios.get(`${API_BASE}/${s.endpoint}`, {
            params: s.params,
            timeout: options?.timeout || 30000,
          }).then(res => ({ key: s.key, data: res.data }))
        )
      )
      if (requestId === requestCounter.current) {
        const newData = { ...initialDataRef.current }
        results.forEach(r => {
          (newData as any)[r.key] = r.data
        })
        setData(newData)
      }
    } catch (e: any) {
      if (requestId === requestCounter.current) {
        const msg = e.response?.data?.detail || e.message || '数据加载失败'
        setError(msg)
      }
    } finally {
      if (requestId === requestCounter.current) {
        setLoading(false)
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourcesKey, options?.timeout])

  useEffect(() => {
    if (options?.autoLoad !== false) {
      refresh()
    }
  }, [options?.autoLoad, refresh])

  return { data, loading, error, refresh, setData }
}
