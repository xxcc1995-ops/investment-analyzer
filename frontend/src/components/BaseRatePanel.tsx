import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = '/api';

interface BaseRateData {
  status: string;
  total_decisions: number;
  with_outcome: number;
  win_rate: number;
  wins: number;
  losses: number;
  breakeven: number;
  avg_profit: number;
  avg_loss: number;
  profit_loss_ratio: number;
  by_type: Record<string, { total: number; win_rate: number }>;
  top_biases: { type: string; count: number }[];
  trend: { month: string; avg_score: number; count: number }[];
  message?: string;
}

const BIAS_NAMES: Record<string, string> = {
  fomo: 'FOMO',
  panic: '恐慌抛售',
  revenge: '复仇交易',
  herd: '从众心理',
  overconfidence: '过度自信',
  anchoring: '锚定效应',
  sunk_cost: '沉没成本',
  confirmation: '确认偏差',
  no_exit_plan: '无退出计划',
  position_risk: '仓位过重',
  emotional_language: '情绪化表达',
};

const TYPE_LABELS: Record<string, string> = {
  buy: '买入',
  sell: '卖出',
  hold: '观望',
};

export default function BaseRatePanel() {
  const [data, setData] = useState<BaseRateData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/decision/base-rates`);
      setData(res.data);
    } catch {
      console.error('获取基准率失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 12, padding: 20,
        border: '1px solid var(--border-primary)', textAlign: 'center',
        color: 'var(--text-muted)', fontSize: 14,
      }}>
        加载基准率数据...
      </div>
    );
  }

  if (!data || data.status === 'insufficient_data') {
    return (
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 12, padding: 20,
        border: '1px solid var(--border-primary)',
      }}>
        <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14, marginBottom: 8 }}>
          📊 个人基准率
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          {data?.message || '暂无足够数据。完成更多决策并记录结果后，这里会显示你的个人投资基准率。'}
        </div>
      </div>
    );
  }

  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: 12, padding: 20,
      border: '1px solid var(--border-primary)',
    }}>
      <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 15, marginBottom: 16 }}>
        📊 你的投资基准率
      </div>

      {/* 核心指标 */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 16,
      }}>
        {[
          { label: '总决策', value: data.total_decisions, suffix: '次', color: 'var(--text-primary)' },
          { label: '胜率', value: data.win_rate, suffix: '%', color: data.win_rate >= 60 ? '#3fb950' : '#d29922' },
          { label: '平均盈利', value: `+${data.avg_profit}`, suffix: '%', color: '#3fb950' },
          { label: '平均亏损', value: `-${data.avg_loss}`, suffix: '%', color: '#f85149' },
          { label: '盈亏比', value: data.profit_loss_ratio, suffix: '', color: data.profit_loss_ratio >= 1.5 ? '#3fb950' : '#d29922' },
          { label: '有结果', value: data.with_outcome, suffix: '次', color: '#58a6ff' },
        ].map((item, i) => (
          <div key={i} style={{
            background: 'var(--bg-tertiary)', borderRadius: 8, padding: '10px 12px',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>{item.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: item.color }}>
              {item.value}{item.suffix}
            </div>
          </div>
        ))}
      </div>

      {/* 按操作类型 */}
      {Object.keys(data.by_type).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
            按操作类型
          </div>
          {Object.entries(data.by_type).map(([type, stats]) => (
            <div key={type} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '6px 0', borderBottom: '1px solid var(--border-primary)',
            }}>
              <span style={{ color: 'var(--text-primary)', fontSize: 13 }}>
                {TYPE_LABELS[type] || type}
              </span>
              <span style={{
                color: stats.win_rate >= 60 ? '#3fb950' : stats.win_rate >= 40 ? '#d29922' : '#f85149',
                fontWeight: 600, fontSize: 13,
              }}>
                胜率 {stats.win_rate}% ({stats.total}次)
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 最常见偏误 */}
      {data.top_biases.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
            你最常犯的偏误
          </div>
          {data.top_biases.map((bias, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '6px 0', borderBottom: '1px solid var(--border-primary)',
            }}>
              <span style={{ color: 'var(--text-primary)', fontSize: 13 }}>
                {BIAS_NAMES[bias.type] || bias.type}
              </span>
              <span style={{
                background: '#f8514915', color: '#f85149',
                padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 600,
              }}>
                {bias.count}次
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 决策质量趋势 */}
      {data.trend.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
            决策质量趋势
          </div>
          {data.trend.slice(-6).map((t, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
            }}>
              <span style={{ color: 'var(--text-muted)', fontSize: 12, width: 60 }}>
                {t.month}
              </span>
              <div style={{
                flex: 1, height: 6, borderRadius: 3, background: 'var(--bg-tertiary)',
                overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%', borderRadius: 3,
                  background: t.avg_score >= 70 ? '#3fb950' : t.avg_score >= 50 ? '#d29922' : '#f85149',
                  width: `${t.avg_score}%`,
                }} />
              </div>
              <span style={{
                color: 'var(--text-primary)', fontSize: 12, fontWeight: 600, width: 35,
              }}>
                {t.avg_score}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
