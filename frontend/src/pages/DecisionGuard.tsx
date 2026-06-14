import React, { useState, useCallback } from 'react';
import axios from 'axios';
import ThinkingFramework from '../components/ThinkingFramework';
import PrefrontalWarmup from '../components/PrefrontalWarmup';
import CalibrationTraining from '../components/CalibrationTraining';
import BaseRatePanel from '../components/BaseRatePanel';
import { PageSection, LoadingSpinner, EmptyState, ProgressBar } from '../components/ui';

const API_BASE = '/api';

// ============================================================
// 类型定义
// ============================================================

interface Detection {
  type: string;
  name: string;
  icon: string;
  desc: string;
  matched_keywords: string[];
  module: string;
}

interface CausalChain {
  issues: string[];
  strengths: string[];
  has_causal: boolean;
  has_data: boolean;
  has_timeframe: boolean;
}

interface NoiseSignal {
  signal: string;
  detail: string;
  mitigation: string;
}

interface NoiseCheck {
  noise_count: number;
  signals: NoiseSignal[];
  consistency_prompt: string;
}

interface ReverseArg {
  thesis: string;
  points: string[];
  challenge: string;
}

interface FailureMode {
  mode: string;
  question: string;
}

interface PreMortem {
  scenario: string;
  failure_modes: FailureMode[];
  instruction: string;
}

interface DimensionScore {
  score: number;
  max: number;
  name: string;
  desc: string;
}

interface Matrix {
  total: number;
  dimensions: Record<string, DimensionScore>;
}

interface Question {
  id: number;
  question: string;
  module: string;
  module_name: string;
  tag: string;
  answer: string;
}

interface Warning {
  icon: string;
  title: string;
  detail: string;
  module: string;
}

interface Diagnosis {
  score: number;
  level: string;
  level_text: string;
  summary: string;
  warnings: Warning[];
  suggestions: string[];
  dimensions: Record<string, DimensionScore>;
}

interface RiskFactor {
  factor: string;
  severity: string;
  detail: string;
  mitigation: string;
}

interface RiskAssessment {
  risk_score: number;
  risk_level: string;
  risk_text: string;
  risk_advice: string;
  risk_factors: RiskFactor[];
  dimensions: Record<string, { score: number; max: number; name: string }>;
}

interface SentimentResult {
  score: number;
  level: string;
  level_text: string;
  advice: string;
  signals: { signal: string; detail: string; score_penalty: number; type: string }[];
}

interface PositionRecommendation {
  suggested_max_pct: number;
  label: string;
  advice: string;
  emotion_adjustment: string;
  risk_score_used: number;
  sentiment_score_used: number;
}

interface DecisionRecord {
  id: string;
  timestamp: string;
  decision_type: string;
  target: string;
  reason: string;
  trigger: string;
  position_pct: string;
  time_horizon: string;
  system1_traps: Detection[];
  logical_fallacies: Detection[];
  causal_chain: CausalChain;
  noise_check: NoiseCheck;
  reverse_arg: ReverseArg;
  pre_mortem: PreMortem;
  matrix: Matrix;
  sentiment?: SentimentResult;
  risk_assessment?: RiskAssessment;
  position_recommendation?: PositionRecommendation;
  questions: Question[];
  diagnosis: Diagnosis | null;
  outcome: { result: string; profit_pct: number | null; lesson: string; recorded_at: string } | null;
}

type Step = 1 | 2 | 3 | 4 | 5;

const DECISION_TYPE_LABELS: Record<string, string> = {
  buy: '买入',
  sell: '卖出',
  hold: '持有/观望',
};

const DIMENSION_COLORS: Record<string, string> = {
  emotion: '#f97316',
  logic: '#3b82f6',
  reverse: '#8b5cf6',
  info: '#10b981',
  noise: '#ec4899',
};

const MODULE_LABELS: Record<string, { icon: string; color: string; name: string }> = {
  system1: { icon: '⚡', color: '#f97316', name: '快思维检测' },
  logic: { icon: '📐', color: '#3b82f6', name: '逻辑验证' },
  reverse: { icon: '🔄', color: '#8b5cf6', name: '反向论证' },
  noise: { icon: '📡', color: '#ec4899', name: '噪声检测' },
  pre_mortem: { icon: '💀', color: '#ef4444', name: '前事分析' },
  causal: { icon: '🔗', color: '#10b981', name: '因果分析' },
};

export default function DecisionGuard() {
  const [step, setStep] = useState<Step>(1);
  const [decisionType, setDecisionType] = useState<string>('buy');
  const [target, setTarget] = useState('');
  const [positionPct, setPositionPct] = useState('');
  const [timeHorizon, setTimeHorizon] = useState('');
  const [reason, setReason] = useState('');
  const [trigger, setTrigger] = useState('');
  const [questions, setQuestions] = useState<Question[]>([]);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [decisionId, setDecisionId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<DecisionRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [decisionStats, setDecisionStats] = useState<any>(null);
  const [outcomeModal, setOutcomeModal] = useState<string | null>(null);
  const [outcomeType, setOutcomeType] = useState('profit');
  const [activeTab, setActiveTab] = useState<'check' | 'warmup' | 'calibration' | 'framework'>('check');
  const [outcomeProfit, setOutcomeProfit] = useState('');
  const [outcomeLesson, setOutcomeLesson] = useState('');
  const [positionRecommendation, setPositionRecommendation] = useState<PositionRecommendation | null>(null);
  const [riskAssessment, setRiskAssessment] = useState<RiskAssessment | null>(null);
  const [sentiment, setSentiment] = useState<SentimentResult | null>(null);

  const handleNext1 = () => {
    if (!target.trim()) { setError('请填写投资标的'); return; }
    setError('');
    setStep(2);
  };

  const handleAnalyze = useCallback(async () => {
    if (!reason.trim()) { setError('请填写决策理由'); return; }
    setError('');
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/decision/analyze`, {
        decision_type: decisionType,
        target: target.trim(),
        reason: reason.trim(),
        trigger: trigger.trim(),
        position_pct: positionPct,
        time_horizon: timeHorizon,
      });
      setAnalysisResult(res.data);
      setQuestions(res.data.questions);
      setDecisionId(res.data.decision_id);
      setSentiment(res.data.sentiment || null);
      setRiskAssessment(res.data.risk_assessment || null);
      setPositionRecommendation(res.data.position_recommendation || null);
      setStep(3);
    } catch (e: any) {
      setError(e.response?.data?.detail || '分析失败，请重试');
    } finally {
      setLoading(false);
    }
  }, [decisionType, target, reason, trigger, positionPct, timeHorizon]);

  const handleDiagnose = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/decision/diagnose`, {
        decision_id: decisionId,
        answers: questions.map((q) => ({ id: q.id, answer: q.answer })),
      });
      setDiagnosis(res.data);
      setStep(5);
    } catch (e: any) {
      setError(e.response?.data?.detail || '诊断失败，请重试');
    } finally {
      setLoading(false);
    }
  }, [decisionId, questions]);

  const handleReset = () => {
    setStep(1);
    setDecisionType('buy');
    setTarget('');
    setPositionPct('');
    setTimeHorizon('');
    setReason('');
    setTrigger('');
    setQuestions([]);
    setAnalysisResult(null);
    setDiagnosis(null);
    setDecisionId('');
    setSentiment(null);
    setRiskAssessment(null);
    setPositionRecommendation(null);
    setError('');
  };

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const [historyRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE}/decision/history`),
        axios.get(`${API_BASE}/decision/stats`).catch(() => ({ data: null })),
      ]);
      setHistory(historyRes.data);
      setDecisionStats(statsRes.data);
      setShowHistory(true);
    } catch {
      setError('加载历史失败');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const handleSubmitOutcome = async () => {
    try {
      await axios.post(`${API_BASE}/decision/outcome`, {
        decision_id: outcomeModal,
        outcome: outcomeType,
        profit_pct: outcomeProfit ? parseFloat(outcomeProfit) : null,
        lesson: outcomeLesson,
      });
      setOutcomeModal(null);
      setOutcomeType('profit');
      setOutcomeProfit('');
      setOutcomeLesson('');
      loadHistory();
    } catch {
      setError('提交结果失败');
    }
  };

  const updateAnswer = (id: number, answer: string) => {
    setQuestions((prev) => prev.map((q) => (q.id === id ? { ...q, answer } : q)));
  };

  // ============================================================
  // 渲染：步骤指示器
  // ============================================================
  const renderSteps = () => (
    <div style={{ display: 'flex', gap: 0, marginBottom: 32 }}>
      {[
        { n: 1 as Step, label: '决策声明' },
        { n: 2 as Step, label: '决策依据' },
        { n: 3 as Step, label: '分析概览' },
        { n: 4 as Step, label: '灵魂质问' },
        { n: 5 as Step, label: '诊断报告' },
      ].map((s, i) => (
        <React.Fragment key={s.n}>
          <div
            onClick={() => { if (s.n < step) setStep(s.n); }}
            style={{
              flex: 1, textAlign: 'center',
              cursor: s.n < step ? 'pointer' : 'default',
              opacity: s.n <= step ? 1 : 0.4,
            }}
          >
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              background: s.n <= step ? '#58a6ff' : 'var(--bg-tertiary)',
              color: s.n <= step ? '#fff' : 'var(--text-muted)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700, fontSize: 16, marginBottom: 6, transition: 'all 0.3s',
            }}>
              {s.n < step ? '✓' : s.n}
            </div>
            <div style={{ fontSize: 12, color: s.n <= step ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              {s.label}
            </div>
          </div>
          {i < 4 && (
            <div style={{
              flex: 0.4, height: 2,
              background: s.n < step ? '#58a6ff' : 'var(--border-primary)',
              alignSelf: 'center', marginTop: -20,
            }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );

  // ============================================================
  // 渲染：Step 1 — 决策声明
  // ============================================================
  const renderStep1 = () => (
    <div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 20 }}>📋 你要做什么？</h3>
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>操作类型</label>
        <div style={{ display: 'flex', gap: 10 }}>
          {[
            { value: 'buy', label: '买入', color: '#f85149' },
            { value: 'sell', label: '卖出', color: '#3fb950' },
            { value: 'hold', label: '观望', color: '#d29922' },
          ].map((opt) => (
            <button key={opt.value} onClick={() => setDecisionType(opt.value)} style={{
              flex: 1, padding: '12px 16px',
              border: `2px solid ${decisionType === opt.value ? opt.color : 'var(--border-primary)'}`,
              borderRadius: 8,
              background: decisionType === opt.value ? `${opt.color}15` : 'var(--bg-secondary)',
              color: decisionType === opt.value ? opt.color : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: 15,
              fontWeight: decisionType === opt.value ? 700 : 400,
              transition: 'all 0.2s',
            }}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>投资标的</label>
        <input value={target} onChange={(e) => setTarget(e.target.value)}
          placeholder="例如：贵州茅台、BTC、沪深300ETF" style={inputStyle} />
      </div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>仓位比例（可选）</label>
          <select value={positionPct} onChange={(e) => setPositionPct(e.target.value)} style={inputStyle}>
            <option value="">请选择</option>
            <option value="light">轻仓（&lt;10%）</option>
            <option value="medium">中等（10-30%）</option>
            <option value="heavy">重仓（30-60%）</option>
            <option value="all">全仓（&gt;60%）</option>
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>持有时间框架（可选）</label>
          <select value={timeHorizon} onChange={(e) => setTimeHorizon(e.target.value)} style={inputStyle}>
            <option value="">请选择</option>
            <option value="short">短线（&lt;1周）</option>
            <option value="swing">波段（1周-3月）</option>
            <option value="medium">中线（3月-1年）</option>
            <option value="long">长线（&gt;1年）</option>
          </select>
        </div>
      </div>
      <button onClick={handleNext1} style={primaryBtnStyle}>下一步：填写决策依据 →</button>
    </div>
  );

  // ============================================================
  // 渲染：Step 2 — 决策依据
  // ============================================================
  const renderStep2 = () => (
    <div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>📝 为什么做这个决策？</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 20 }}>
        请尽量详细、诚实地写下你的理由。越诚实，诊断越准确。
      </p>
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>决策理由 *</label>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="例如：我看好这只股票是因为公司业绩持续增长，ROE稳定在20%以上，当前PE处于历史低位..."
          style={{ ...inputStyle, minHeight: 120, resize: 'vertical' as const }} />
      </div>
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>触发原因（可选）</label>
        <textarea value={trigger} onChange={(e) => setTrigger(e.target.value)}
          placeholder="是什么事情触发了你做这个决定？例如：看到某篇文章、朋友推荐、股价大涨/大跌..."
          style={{ ...inputStyle, minHeight: 80, resize: 'vertical' as const }} />
      </div>
      <div style={{ display: 'flex', gap: 12 }}>
        <button onClick={() => setStep(1)} style={secondaryBtnStyle}>← 返回</button>
        <button onClick={handleAnalyze} style={primaryBtnStyle} disabled={loading}>
          {loading ? '分析中...' : '🧠 开始深度分析'}
        </button>
      </div>
    </div>
  );

  // ============================================================
  // 渲染：Step 3 — 分析概览（新增）
  // ============================================================
  const renderStep3 = () => {
    if (!analysisResult) return null;
    const { system1_traps, logical_fallacies, causal_chain, noise_check, reverse_arg, pre_mortem, matrix } = analysisResult;

    return (
      <div>
        <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>🔍 分析概览</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 24 }}>
          我们从五个维度扫描了你的决策。下面是你需要面对的问题。
        </p>

        {/* 决策矩阵预览 */}
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 16, padding: 24, marginBottom: 24,
          border: '1px solid var(--border-primary)',
        }}>
          <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 16, fontWeight: 600 }}>
            📊 决策矩阵（基础分，回答问题后会调整）
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {Object.entries(matrix.dimensions).map(([key, dim]: [string, any]) => (
              <div key={key} style={{
                flex: '1 1 120px', background: 'var(--bg-tertiary)',
                borderRadius: 12, padding: 16, textAlign: 'center',
                minWidth: 120,
              }}>
                <div style={{
                  fontSize: 28, fontWeight: 900,
                  color: DIMENSION_COLORS[key] || '#58a6ff',
                }}>
                  {dim.score}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  / {dim.max}
                </div>
                <div style={{
                  fontSize: 13, fontWeight: 600, marginTop: 6,
                  color: 'var(--text-primary)',
                }}>
                  {dim.name}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {dim.desc}
                </div>
              </div>
            ))}
          </div>
          <div style={{
            marginTop: 16, textAlign: 'center',
            fontSize: 24, fontWeight: 900,
            color: matrix.total >= 70 ? '#3fb950' : matrix.total >= 50 ? '#d29922' : '#f85149',
          }}>
            基础分：{matrix.total} / 100
          </div>
        </div>

        {/* 仓位建议 & 情绪评分 & 风险评估（三列） */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' as const }}>
          {/* 仓位建议 */}
          {positionRecommendation && (
            <div style={{
              flex: '1 1 200px', background: 'var(--bg-secondary)', borderRadius: 12,
              padding: 20, border: '1px solid var(--border-primary)',
              borderTop: '3px solid #58a6ff',
            }}>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600 }}>
                💰 仓位建议
              </div>
              <div style={{
                fontSize: 32, fontWeight: 900,
                color: positionRecommendation.suggested_max_pct > 10 ? '#3fb950'
                  : positionRecommendation.suggested_max_pct > 0 ? '#d29922' : '#f85149',
              }}>
                {positionRecommendation.suggested_max_pct > 0
                  ? `≤${positionRecommendation.suggested_max_pct}%`
                  : '不建议'}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>
                {positionRecommendation.label}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
                {positionRecommendation.advice}
              </div>
            </div>
          )}

          {/* 情绪评分 */}
          {sentiment && (
            <div style={{
              flex: '1 1 200px', background: 'var(--bg-secondary)', borderRadius: 12,
              padding: 20, border: '1px solid var(--border-primary)',
              borderTop: `3px solid ${sentiment.score >= 70 ? '#3fb950' : sentiment.score >= 50 ? '#d29922' : '#f85149'}`,
            }}>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600 }}>
                🧘 情绪状态
              </div>
              <div style={{
                fontSize: 32, fontWeight: 900,
                color: sentiment.score >= 70 ? '#3fb950' : sentiment.score >= 50 ? '#d29922' : '#f85149',
              }}>
                {sentiment.score}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>
                {sentiment.level_text}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
                {sentiment.advice}
              </div>
              {sentiment.signals.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {sentiment.signals.map((s, i) => (
                    <div key={i} style={{ fontSize: 11, color: '#f97316', marginBottom: 2 }}>
                      ! {s.signal}: {s.detail}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 风险评估 */}
          {riskAssessment && (
            <div style={{
              flex: '1 1 200px', background: 'var(--bg-secondary)', borderRadius: 12,
              padding: 20, border: '1px solid var(--border-primary)',
              borderTop: `3px solid ${riskAssessment.risk_score <= 30 ? '#3fb950'
                : riskAssessment.risk_score <= 60 ? '#d29922' : '#f85149'}`,
            }}>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600 }}>
                ⚠️ 风险等级
              </div>
              <div style={{
                fontSize: 32, fontWeight: 900,
                color: riskAssessment.risk_score <= 30 ? '#3fb950'
                  : riskAssessment.risk_score <= 60 ? '#d29922' : '#f85149',
              }}>
                {riskAssessment.risk_score}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>
                {riskAssessment.risk_text}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5 }}>
                {riskAssessment.risk_advice}
              </div>
              {riskAssessment.risk_factors.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  {riskAssessment.risk_factors.map((f, i) => (
                    <div key={i} style={{
                      fontSize: 11, color: f.severity === 'critical' || f.severity === 'high' ? '#f85149' : '#d29922',
                      marginBottom: 2,
                    }}>
                      ! {f.factor}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* System 1 陷阱 */}
        {system1_traps.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{
              fontSize: 15, fontWeight: 700, color: '#f97316', marginBottom: 12,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              ⚡ 快思维陷阱 ({system1_traps.length})
            </div>
            {system1_traps.map((t: Detection, i: number) => (
              <div key={i} style={{
                background: 'var(--bg-secondary)', borderRadius: 10, padding: 14, marginBottom: 8,
                border: '1px solid var(--border-primary)', borderLeft: '4px solid #f97316',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 18 }}>{t.icon}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.name}</span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>
                  {t.desc}
                </div>
                {t.matched_keywords.length > 0 && (
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                    触发词：{t.matched_keywords.slice(0, 5).join('、')}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 逻辑谬误 */}
        {logical_fallacies.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{
              fontSize: 15, fontWeight: 700, color: '#3b82f6', marginBottom: 12,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              📐 逻辑谬误 ({logical_fallacies.length})
            </div>
            {logical_fallacies.map((f: Detection, i: number) => (
              <div key={i} style={{
                background: 'var(--bg-secondary)', borderRadius: 10, padding: 14, marginBottom: 8,
                border: '1px solid var(--border-primary)', borderLeft: '4px solid #3b82f6',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 18 }}>{f.icon}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{f.name}</span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>
                  {f.desc}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 因果链条分析 */}
        <div style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 15, fontWeight: 700, color: '#10b981', marginBottom: 12,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            🔗 因果链条分析
          </div>
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 10, padding: 16,
            border: '1px solid var(--border-primary)', borderLeft: '4px solid #10b981',
          }}>
            {causal_chain.strengths.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                {causal_chain.strengths.map((s: string, i: number) => (
                  <div key={i} style={{ color: '#3fb950', fontSize: 14, marginBottom: 4 }}>
                    ✓ {s}
                  </div>
                ))}
              </div>
            )}
            {causal_chain.issues.length > 0 && (
              <div>
                {causal_chain.issues.map((issue: string, i: number) => (
                  <div key={i} style={{ color: '#f85149', fontSize: 14, marginBottom: 4 }}>
                    ✗ {issue}
                  </div>
                ))}
              </div>
            )}
            {causal_chain.strengths.length === 0 && causal_chain.issues.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
                未检测到明确的因果推理结构
              </div>
            )}
          </div>
        </div>

        {/* 噪声信号 */}
        {noise_check.signals.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <div style={{
              fontSize: 15, fontWeight: 700, color: '#ec4899', marginBottom: 12,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              📡 噪声信号 ({noise_check.signals.length})
            </div>
            {noise_check.signals.map((s: NoiseSignal, i: number) => (
              <div key={i} style={{
                background: 'var(--bg-secondary)', borderRadius: 10, padding: 14, marginBottom: 8,
                border: '1px solid var(--border-primary)', borderLeft: '4px solid #ec4899',
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                  {s.signal}
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 4 }}>
                  {s.detail}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 13, fontStyle: 'italic' }}>
                  💡 {s.mitigation}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 反向论证框架 */}
        <div style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 15, fontWeight: 700, color: '#8b5cf6', marginBottom: 12,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            🔄 反向论证框架
          </div>
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 10, padding: 16,
            border: '1px solid var(--border-primary)', borderLeft: '4px solid #8b5cf6',
          }}>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
              {reverse_arg.thesis}
            </div>
            {reverse_arg.points.map((p: string, i: number) => (
              <div key={i} style={{
                color: 'var(--text-secondary)', fontSize: 14, marginBottom: 6,
                paddingLeft: 12, borderLeft: '2px solid var(--border-primary)',
              }}>
                {p}
              </div>
            ))}
          </div>
        </div>

        {/* 前事分析 */}
        <div style={{ marginBottom: 24 }}>
          <div style={{
            fontSize: 15, fontWeight: 700, color: '#ef4444', marginBottom: 12,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            💀 前事分析 — 失败预演
          </div>
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 10, padding: 16,
            border: '1px solid var(--border-primary)', borderLeft: '4px solid #ef4444',
          }}>
            <div style={{
              fontWeight: 600, color: '#f85149', marginBottom: 12,
              fontSize: 15, fontStyle: 'italic',
            }}>
              "{pre_mortem.scenario}"
            </div>
            {pre_mortem.failure_modes.map((fm: FailureMode, i: number) => (
              <div key={i} style={{
                color: 'var(--text-secondary)', fontSize: 14, marginBottom: 8,
                paddingLeft: 12, borderLeft: '2px solid var(--border-primary)',
              }}>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{fm.mode}：</span>
                {fm.question}
              </div>
            ))}
          </div>
        </div>

        <button onClick={() => setStep(4)} style={primaryBtnStyle}>
          下一步：回答灵魂质问 →
        </button>
      </div>
    );
  };

  // ============================================================
  // 渲染：Step 4 — 灵魂质问
  // ============================================================
  const renderStep4 = () => (
    <div>
      <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>🧠 灵魂质问</h3>
      <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 24 }}>
        请认真回答以下每个问题。这不是形式——你的回答将直接影响最终评分。
      </p>

      {questions.map((q, idx) => {
        const mod = MODULE_LABELS[q.module] || { icon: '❓', color: '#58a6ff', name: q.module_name };
        return (
          <div key={q.id} style={{
            background: 'var(--bg-secondary)', borderRadius: 12, padding: 20, marginBottom: 16,
            border: '1px solid var(--border-primary)', borderLeft: `4px solid ${mod.color}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{
                background: `${mod.color}20`, color: mod.color,
                padding: '2px 10px', borderRadius: 4, fontSize: 12, fontWeight: 600,
              }}>
                {mod.icon} {mod.name}
              </span>
              <span style={{
                background: 'var(--bg-tertiary)', color: 'var(--text-muted)',
                padding: '2px 8px', borderRadius: 4, fontSize: 11,
              }}>
                {q.tag}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 'auto' }}>
                {idx + 1}/{questions.length}
              </span>
            </div>
            <p style={{
              color: 'var(--text-primary)', fontSize: 16, fontWeight: 600,
              marginBottom: 12, lineHeight: 1.6,
            }}>
              {q.question}
            </p>
            <textarea
              value={q.answer}
              onChange={(e) => updateAnswer(q.id, e.target.value)}
              placeholder="请认真思考后回答..."
              style={{ ...inputStyle, minHeight: 80, resize: 'vertical' as const }}
            />
          </div>
        );
      })}

      <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
        <button onClick={() => setStep(3)} style={secondaryBtnStyle}>← 返回分析</button>
        <button onClick={handleDiagnose} style={primaryBtnStyle} disabled={loading}>
          {loading ? '诊断中...' : '📊 生成诊断报告'}
        </button>
      </div>
    </div>
  );

  // ============================================================
  // 渲染：Step 5 — 诊断报告
  // ============================================================
  const renderStep5 = () => {
    if (!diagnosis) return null;

    const scoreColor = diagnosis.score >= 70 ? '#3fb950' : diagnosis.score >= 50 ? '#d29922' : '#f85149';

    return (
      <div>
        <h3 style={{ color: 'var(--text-primary)', marginBottom: 24 }}>📊 决策诊断报告</h3>

        {/* 评分卡 */}
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 16, padding: 32, marginBottom: 24,
          border: `2px solid ${scoreColor}`, textAlign: 'center',
        }}>
          <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 8 }}>决策质量评分</div>
          <div style={{ fontSize: 72, fontWeight: 900, color: scoreColor, lineHeight: 1 }}>
            {diagnosis.score}
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, color: scoreColor, marginTop: 8 }}>
            {diagnosis.level_text}
          </div>
          <div style={{ color: 'var(--text-secondary)', marginTop: 12, fontSize: 15, lineHeight: 1.6 }}>
            {diagnosis.summary}
          </div>
        </div>

        {/* 五维雷达图（用进度条代替） */}
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 16, padding: 24, marginBottom: 24,
          border: '1px solid var(--border-primary)',
        }}>
          <h4 style={{ color: 'var(--text-primary)', marginBottom: 16 }}>📊 五维评估</h4>
          {diagnosis.dimensions && Object.entries(diagnosis.dimensions).map(([key, dim]: [string, any]) => {
            const pct = (dim.score / dim.max) * 100;
            const color = DIMENSION_COLORS[key] || '#58a6ff';
            return (
              <div key={key} style={{ marginBottom: 14 }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', marginBottom: 4,
                }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {dim.name}
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 700, color }}>
                    {dim.score} / {dim.max}
                  </span>
                </div>
                <div style={{
                  height: 8, borderRadius: 4, background: 'var(--bg-tertiary)', overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%', borderRadius: 4, background: color,
                    width: `${pct}%`, transition: 'width 0.6s ease',
                  }} />
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  {dim.desc}
                </div>
              </div>
            );
          })}
        </div>

        {/* 警告列表 */}
        {diagnosis.warnings.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>
              ⚠️ 检出的风险 ({diagnosis.warnings.length})
            </h4>
            {diagnosis.warnings.map((w, i) => {
              const mod = MODULE_LABELS[w.module] || { icon: '⚠️', color: '#58a6ff', name: w.module };
              return (
                <div key={i} style={{
                  background: 'var(--bg-secondary)', borderRadius: 10, padding: 14, marginBottom: 8,
                  border: '1px solid var(--border-primary)', display: 'flex', alignItems: 'flex-start', gap: 12,
                }}>
                  <span style={{ fontSize: 20 }}>{w.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{w.title}</span>
                      <span style={{
                        background: `${mod.color}20`, color: mod.color,
                        padding: '1px 6px', borderRadius: 3, fontSize: 11,
                      }}>
                        {mod.name}
                      </span>
                    </div>
                    <div style={{ color: 'var(--text-secondary)', fontSize: 14 }}>{w.detail}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 建议 */}
        <div style={{ marginBottom: 24 }}>
          <h4 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>💡 建议</h4>
          {diagnosis.suggestions.map((s, i) => (
            <div key={i} style={{
              background: 'var(--bg-secondary)', borderRadius: 8, padding: 12, marginBottom: 6,
              color: 'var(--text-primary)', fontSize: 14, lineHeight: 1.6,
            }}>
              {s}
            </div>
          ))}
        </div>

        {/* 详细风险因素（来自风险评估） */}
        {riskAssessment && riskAssessment.risk_factors.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>
              🎯 风险因素详情
            </h4>
            {riskAssessment.risk_factors.map((f, i) => (
              <div key={i} style={{
                background: 'var(--bg-secondary)', borderRadius: 10, padding: 14, marginBottom: 8,
                border: '1px solid var(--border-primary)',
                borderLeft: `4px solid ${f.severity === 'critical' ? '#f85149'
                  : f.severity === 'high' ? '#f97316' : '#d29922'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{f.factor}</span>
                  <span style={{
                    background: f.severity === 'critical' ? '#f8514920' : f.severity === 'high' ? '#f9731620' : '#d2992220',
                    color: f.severity === 'critical' ? '#f85149' : f.severity === 'high' ? '#f97316' : '#d29922',
                    padding: '1px 6px', borderRadius: 3, fontSize: 11, fontWeight: 600,
                  }}>
                    {f.severity === 'critical' ? '极高' : f.severity === 'high' ? '高' : '中'}
                  </span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 6 }}>
                  {f.detail}
                </div>
                <div style={{ color: '#58a6ff', fontSize: 13 }}>
                  建议：{f.mitigation}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 仓位建议详情 */}
        {positionRecommendation && (
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 16, padding: 24, marginBottom: 24,
            border: '1px solid var(--border-primary)', borderTop: '3px solid #58a6ff',
          }}>
            <h4 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>💰 仓位建议</h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
              <div style={{
                fontSize: 36, fontWeight: 900,
                color: positionRecommendation.suggested_max_pct > 10 ? '#3fb950'
                  : positionRecommendation.suggested_max_pct > 0 ? '#d29922' : '#f85149',
              }}>
                {positionRecommendation.suggested_max_pct > 0
                  ? `≤${positionRecommendation.suggested_max_pct}%`
                  : '不建议建仓'}
              </div>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {positionRecommendation.label}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
                  {positionRecommendation.emotion_adjustment}
                </div>
              </div>
            </div>
            <div style={{
              color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6,
              padding: '10px 14px', background: 'var(--bg-tertiary)', borderRadius: 8,
            }}>
              {positionRecommendation.advice}
            </div>
          </div>
        )}

        {/* 冷却提示 */}
        {diagnosis.score < 55 && (
          <div style={{
            background: '#f8514915', border: '1px solid #f8514940',
            borderRadius: 12, padding: 20, marginBottom: 24, textAlign: 'center',
          }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>🧊</div>
            <div style={{ color: '#f85149', fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
              建议冷静期：{diagnosis.score < 40 ? '72小时' : '24-48小时'}
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
              {diagnosis.score < 40
                ? '你的决策充满了情绪化因素，请暂停交易，至少冷静72小时后再决定。'
                : '你的决策存在情绪化风险，建议至少冷静24-48小时，等情绪平复后再评估。'}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div style={{ display: 'flex', gap: 12 }}>
          <button onClick={handleReset} style={primaryBtnStyle}>🔄 做新的决策</button>
          <button onClick={loadHistory} style={secondaryBtnStyle} disabled={historyLoading}>
            📋 查看决策日志
          </button>
        </div>
      </div>
    );
  };

  // ============================================================
  // 渲染：历史记录弹窗
  // ============================================================
  const renderHistory = () => {
    if (!showHistory) return null;
    return (
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.7)', zIndex: 1000,
        display: 'flex', justifyContent: 'center', padding: 40, overflow: 'auto',
      }}>
        <div style={{
          background: 'var(--bg-primary)', borderRadius: 16, padding: 32,
          maxWidth: 800, width: '100%', maxHeight: 'calc(100vh - 80px)', overflow: 'auto',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h3 style={{ color: 'var(--text-primary)', margin: 0 }}>📋 决策日志</h3>
            <button onClick={() => setShowHistory(false)} style={{
              background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 24, cursor: 'pointer',
            }}>✕</button>
          </div>
          {/* 统计概览 */}
          {decisionStats && decisionStats.overview && (
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 12, padding: 20, marginBottom: 20,
              border: '1px solid var(--border-primary)',
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
                📊 决策统计概览
              </div>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' as const }}>
                {[
                  { label: '总决策', value: decisionStats.overview.total_decisions, color: '#58a6ff' },
                  { label: '胜率', value: `${decisionStats.overview.win_rate}%`,
                    color: decisionStats.overview.win_rate >= 50 ? '#3fb950' : '#f85149' },
                  { label: '盈亏比', value: decisionStats.overview.profit_loss_ratio,
                    color: decisionStats.overview.profit_loss_ratio >= 1.5 ? '#3fb950' : '#d29922' },
                  { label: 'Sharpe', value: decisionStats.overview.sharpe_ratio,
                    color: decisionStats.overview.sharpe_ratio >= 0.5 ? '#3fb950' : '#d29922' },
                  { label: '期望收益', value: `${decisionStats.overview.expected_value}%`,
                    color: decisionStats.overview.expected_value > 0 ? '#3fb950' : '#f85149' },
                ].map((stat, i) => (
                  <div key={i} style={{
                    flex: '1 1 100px', textAlign: 'center', padding: '8px 4px',
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 900, color: stat.color }}>
                      {stat.value}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      {stat.label}
                    </div>
                  </div>
                ))}
              </div>
              {/* Kelly公式建议 */}
              {decisionStats.base_rates?.kelly_criterion?.half_kelly > 0 && (
                <div style={{
                  marginTop: 12, padding: '8px 12px', background: 'var(--bg-tertiary)',
                  borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)',
                }}>
                  Kelly公式建议单笔仓位：
                  <span style={{ fontWeight: 700, color: '#58a6ff' }}>
                    {decisionStats.base_rates.kelly_criterion.half_kelly}%
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>
                    （半Kelly，更保守）
                  </span>
                </div>
              )}
              {/* 最近30天 */}
              {decisionStats.recent_30d && (
                <div style={{
                  marginTop: 8, padding: '8px 12px', background: 'var(--bg-tertiary)',
                  borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)',
                }}>
                  近30天：{decisionStats.recent_30d.decisions}次决策，
                  胜率{decisionStats.recent_30d.win_rate}%
                  {decisionStats.recent_30d.top_biases?.length > 0 && (
                    <span>，最常见偏误：{decisionStats.recent_30d.top_biases[0][0]}</span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 偏误影响分析 */}
          {decisionStats?.base_rates?.bias_impact?.length > 0 && (
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 12, padding: 20, marginBottom: 20,
              border: '1px solid var(--border-primary)',
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
                🧬 偏误-结果关联
              </div>
              {decisionStats.base_rates.bias_impact.map((b: any, i: number) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '6px 0', borderBottom: i < decisionStats.base_rates.bias_impact.length - 1
                    ? '1px solid var(--border-primary)' : 'none',
                }}>
                  <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                    {b.type}（{b.count}次）
                  </span>
                  <span style={{
                    fontSize: 13, fontWeight: 700,
                    color: b.loss_rate_when_present > 60 ? '#f85149'
                      : b.loss_rate_when_present > 40 ? '#d29922' : '#3fb950',
                  }}>
                    亏损率 {b.loss_rate_when_present}%
                  </span>
                </div>
              ))}
            </div>
          )}

          {history.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>暂无决策记录</div>
          ) : (
            history.map((record) => (
              <div key={record.id} style={{
                background: 'var(--bg-secondary)', borderRadius: 12, padding: 16, marginBottom: 12,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div>
                    <span style={{
                      background: record.decision_type === 'buy' ? '#f8514920'
                        : record.decision_type === 'sell' ? '#3fb95020' : '#d2992220',
                      color: record.decision_type === 'buy' ? '#f85149'
                        : record.decision_type === 'sell' ? '#3fb950' : '#d29922',
                      padding: '2px 8px', borderRadius: 4, fontSize: 13, fontWeight: 600, marginRight: 8,
                    }}>
                      {DECISION_TYPE_LABELS[record.decision_type] || record.decision_type}
                    </span>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 15 }}>
                      {record.target}
                    </span>
                  </div>
                  <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                    {new Date(record.timestamp).toLocaleDateString('zh-CN', {
                      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                    })}
                  </span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 8, lineHeight: 1.5 }}>
                  {record.reason.length > 100 ? record.reason.slice(0, 100) + '...' : record.reason}
                </div>
                {record.diagnosis && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                    <span style={{
                      color: record.diagnosis.score >= 70 ? '#3fb950'
                        : record.diagnosis.score >= 50 ? '#d29922' : '#f85149',
                      fontWeight: 700, fontSize: 18,
                    }}>
                      {record.diagnosis.score}分
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                      {record.diagnosis.level_text}
                    </span>
                    {record.diagnosis.warnings && record.diagnosis.warnings.length > 0 && (
                      <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                        · {record.diagnosis.warnings.length}个风险
                      </span>
                    )}
                    {record.risk_assessment && (
                      <span style={{
                        fontSize: 12, fontWeight: 600, padding: '1px 6px', borderRadius: 3,
                        background: record.risk_assessment.risk_score <= 30 ? '#3fb95020'
                          : record.risk_assessment.risk_score <= 60 ? '#d2992220' : '#f8514920',
                        color: record.risk_assessment.risk_score <= 30 ? '#3fb950'
                          : record.risk_assessment.risk_score <= 60 ? '#d29922' : '#f85149',
                      }}>
                        风险{record.risk_assessment.risk_score}
                      </span>
                    )}
                    {record.position_recommendation && record.position_recommendation.suggested_max_pct > 0 && (
                      <span style={{ fontSize: 12, color: '#58a6ff' }}>
                        建议仓位≤{record.position_recommendation.suggested_max_pct}%
                      </span>
                    )}
                  </div>
                )}
                {record.outcome ? (
                  <div style={{
                    background: record.outcome.result === 'profit' ? '#3fb95015' : '#f8514915',
                    borderRadius: 6, padding: '8px 12px', fontSize: 13,
                  }}>
                    <span style={{
                      color: record.outcome.result === 'profit' ? '#3fb950' : '#f85149', fontWeight: 600,
                    }}>
                      {record.outcome.result === 'profit' ? '盈利' : record.outcome.result === 'loss' ? '亏损' : '持平'}
                      {record.outcome.profit_pct != null && ` ${record.outcome.profit_pct}%`}
                    </span>
                    {record.outcome.lesson && (
                      <span style={{ color: 'var(--text-secondary)', marginLeft: 8 }}>
                        教训：{record.outcome.lesson}
                      </span>
                    )}
                  </div>
                ) : (
                  <button onClick={() => setOutcomeModal(record.id)} style={{
                    background: 'none', border: '1px dashed var(--border-primary)',
                    borderRadius: 6, padding: '6px 12px', color: 'var(--text-muted)',
                    fontSize: 13, cursor: 'pointer',
                  }}>
                    📝 记录结果
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    );
  };

  // ============================================================
  // 渲染：结果补填弹窗
  // ============================================================
  const renderOutcomeModal = () => {
    if (!outcomeModal) return null;
    return (
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        background: 'rgba(0,0,0,0.7)', zIndex: 1100,
        display: 'flex', justifyContent: 'center', alignItems: 'center',
      }}>
        <div style={{
          background: 'var(--bg-primary)', borderRadius: 16, padding: 32,
          maxWidth: 480, width: '100%',
        }}>
          <h3 style={{ color: 'var(--text-primary)', marginBottom: 20 }}>📝 记录决策结果</h3>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>结果</label>
            <div style={{ display: 'flex', gap: 10 }}>
              {[
                { value: 'profit', label: '盈利', color: '#3fb950' },
                { value: 'loss', label: '亏损', color: '#f85149' },
                { value: 'breakeven', label: '持平', color: '#d29922' },
              ].map((opt) => (
                <button key={opt.value} onClick={() => setOutcomeType(opt.value)} style={{
                  flex: 1, padding: '10px',
                  border: `2px solid ${outcomeType === opt.value ? opt.color : 'var(--border-primary)'}`,
                  borderRadius: 8,
                  background: outcomeType === opt.value ? `${opt.color}15` : 'var(--bg-secondary)',
                  color: outcomeType === opt.value ? opt.color : 'var(--text-secondary)',
                  cursor: 'pointer', fontWeight: outcomeType === opt.value ? 700 : 400,
                }}>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>盈亏比例 %（可选）</label>
            <input value={outcomeProfit} onChange={(e) => setOutcomeProfit(e.target.value)}
              placeholder="例如：15.5 或 -8.2" type="number" style={inputStyle} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>经验教训（可选）</label>
            <textarea value={outcomeLesson} onChange={(e) => setOutcomeLesson(e.target.value)}
              placeholder="回头看，这个决策做得怎么样？有什么值得记住的？"
              style={{ ...inputStyle, minHeight: 80, resize: 'vertical' as const }} />
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={() => setOutcomeModal(null)} style={secondaryBtnStyle}>取消</button>
            <button onClick={handleSubmitOutcome} style={primaryBtnStyle}>保存结果</button>
          </div>
        </div>
      </div>
    );
  };

  // ============================================================
  // 主渲染
  // ============================================================
  return (
    <div style={{ maxWidth: 780, margin: '0 auto', padding: '24px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ color: 'var(--text-primary)', margin: 0, fontSize: 24 }}>🛡️ 决策卫士 v2</h2>
          <p style={{ color: 'var(--text-muted)', margin: '6px 0 0', fontSize: 14 }}>
            五层分析框架 — 让 System 2 接管 System 1
          </p>
        </div>
        <button onClick={loadHistory} style={{ ...secondaryBtnStyle, padding: '8px 16px', fontSize: 13 }}
          disabled={historyLoading}>
          📋 决策日志
        </button>
      </div>

      {/* 标签页切换 */}
      <div style={{
        display: 'flex', gap: 0, marginBottom: 24,
        background: 'var(--bg-secondary)', borderRadius: 10, padding: 4,
        border: '1px solid var(--border-primary)',
        flexWrap: 'wrap' as const,
      }}>
        {[
          { key: 'check' as const, label: '🔍 决策检查' },
          { key: 'warmup' as const, label: '🧠 前额叶热身' },
          { key: 'calibration' as const, label: '🎯 校准训练' },
          { key: 'framework' as const, label: '📚 思维框架' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              flex: '1 1 auto', padding: '10px 14px',
              background: activeTab === tab.key ? 'var(--bg-tertiary)' : 'transparent',
              border: activeTab === tab.key ? '1px solid var(--border-primary)' : '1px solid transparent',
              borderRadius: 8, cursor: 'pointer',
              color: activeTab === tab.key ? 'var(--text-primary)' : 'var(--text-muted)',
              fontWeight: activeTab === tab.key ? 600 : 400,
              fontSize: 13,
              transition: 'all 0.2s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 前额叶热身标签页 */}
      {activeTab === 'warmup' && <PrefrontalWarmup />}

      {/* 校准训练标签页 */}
      {activeTab === 'calibration' && <CalibrationTraining />}

      {/* 思维框架标签页 */}
      {activeTab === 'framework' && <ThinkingFramework />}

      {/* 决策检查标签页 */}
      {activeTab === 'check' && (
        <>
          {/* 个人基准率 */}
          <div style={{ marginBottom: 20 }}>
            <BaseRatePanel />
          </div>

          {error && (
            <div style={{
              background: '#f8514915', border: '1px solid #f8514940',
              borderRadius: 8, padding: '10px 16px', color: '#f85149', marginBottom: 20, fontSize: 14,
            }}>
              {error}
            </div>
          )}

          {renderSteps()}

          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4()}
          {step === 5 && renderStep5()}
        </>
      )}

      {renderHistory()}
      {renderOutcomeModal()}
    </div>
  );
}

// ============================================================
// 样式常量
// ============================================================

const labelStyle: React.CSSProperties = {
  display: 'block', color: 'var(--text-secondary)',
  fontSize: 14, fontWeight: 600, marginBottom: 6,
};

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px',
  background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
  borderRadius: 8, color: 'var(--text-primary)', fontSize: 15,
  outline: 'none', boxSizing: 'border-box',
};

const primaryBtnStyle: React.CSSProperties = {
  flex: 1, padding: '12px 24px', background: '#58a6ff', border: 'none',
  borderRadius: 8, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer',
};

const secondaryBtnStyle: React.CSSProperties = {
  padding: '12px 24px', background: 'var(--bg-secondary)',
  border: '1px solid var(--border-primary)', borderRadius: 8,
  color: 'var(--text-secondary)', fontSize: 15, cursor: 'pointer',
};
