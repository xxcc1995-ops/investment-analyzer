/**
 * QuantDinger AI分析 API
 */

import api from './client'

export interface AIAnalysisResult {
  symbol: string
  market: string
  decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  summary: string

  scores: {
    technical: number
    fundamental: number
    sentiment: number
    overall: number
  }

  trading_plan: {
    entry_price: number | null
    stop_loss: number | null
    take_profit: number | null
    position_size_pct: number | null
  }

  reasons: string[]
  risks: string[]

  trend_outlook: {
    [key: string]: {
      score: number
      trend: string
      strength: string
    }
  }
  trend_outlook_summary: string

  consensus: {
    consensus_score: number
    consensus_decision: string
    agreement_ratio: number
    market_regime: string
  }

  market_data: {
    current_price: number
    change_24h: number
    support: number
    resistance: number
  }

  detailed_analysis: {
    technical: string
    fundamental: string
    sentiment: string
  }

  model: string
  analysis_time_ms: number
  analyzed_at: string
}

export interface AnalysisHistory {
  id: number
  symbol: string
  market: string
  decision: string
  confidence: number
  summary: string
  created_at: string
  was_correct: boolean | null
  actual_return_pct: number | null
}

export interface PerformanceStats {
  total_analyses: number
  correct_predictions: number
  accuracy_pct: number
  avg_return_pct: number
  by_decision: {
    BUY: { count: number; correct: number; avg_return: number }
    SELL: { count: number; correct: number; avg_return: number }
    HOLD: { count: number; correct: number; avg_return: number }
  }
}

export const quantdingerApi = {
  /**
   * 检查QuantDinger服务是否可用
   */
  checkHealth: () =>
    api.get<{ available: boolean; base_url: string }>('/quantdinger/health'),

  /**
   * 对股票进行AI分析
   */
  analyzeStock: (
    code: string,
    options?: {
      timeframe?: '1H' | '4H' | '1D' | '1W'
      language?: 'zh-CN' | 'en-US'
      model?: string
    }
  ) =>
    api.post<{ code: number; msg: string; data: AIAnalysisResult }>(
      `/quantdinger/analyze/${code}`,
      null,
      {
        params: {
          timeframe: options?.timeframe || '1D',
          language: options?.language || 'zh-CN',
          model: options?.model,
        },
        timeout: 120000, // AI分析可能需要较长时间
      }
    ),

  /**
   * 获取股票的历史AI分析记录
   */
  getHistory: (
    code: string,
    options?: {
      days?: number
      limit?: number
    }
  ) =>
    api.get<{ code: number; msg: string; data: AnalysisHistory[] }>(
      `/quantdinger/history/${code}`,
      {
        params: {
          days: options?.days || 7,
          limit: options?.limit || 10,
        },
      }
    ),

  /**
   * 获取AI分析的绩效统计
   */
  getPerformance: (options?: { code?: string; days?: number }) =>
    api.get<{ code: number; msg: string; data: PerformanceStats }>(
      '/quantdinger/performance',
      {
        params: {
          code: options?.code,
          days: options?.days || 30,
        },
      }
    ),
}
