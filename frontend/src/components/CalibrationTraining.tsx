import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';

const API_BASE = '/api';

interface CalibrationQuestion {
  id: string;
  category: string;
  question: string;
  unit: string;
  total_questions: number;
}

interface CalibrationResult {
  accuracy: string;
  accuracy_text: string;
  accuracy_score: number;
  user_answer: number;
  reference_answer: number;
  unit: string;
  error_pct: number;
  confidence: number;
  explanation: string;
}

interface CalibrationStats {
  status: string;
  total_sessions: number;
  overall_accuracy: number;
  avg_confidence: number;
  overconfidence_score: number;
  cal_message: string;
  message?: string;
  calibration_curve: { confidence: number; actual_accuracy: number; sample_size: number; gap: number }[];
}

const CONFIDENCE_LEVELS = [60, 70, 80, 90];

export default function CalibrationTraining() {
  const [question, setQuestion] = useState<CalibrationQuestion | null>(null);
  const [userAnswer, setUserAnswer] = useState('');
  const [confidence, setConfidence] = useState(70);
  const [result, setResult] = useState<CalibrationResult | null>(null);
  const [stats, setStats] = useState<CalibrationStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);

  const fetchQuestion = useCallback(async () => {
    setLoading(true);
    setResult(null);
    setUserAnswer('');
    try {
      const res = await axios.get(`${API_BASE}/decision/calibration-question`);
      setQuestion(res.data);
    } catch {
      console.error('获取题目失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/decision/calibration-stats`);
      setStats(res.data);
    } catch {
      console.error('获取统计失败');
    }
  }, []);

  useEffect(() => {
    fetchQuestion();
    fetchStats();
  }, [fetchQuestion, fetchStats]);

  const handleSubmit = async () => {
    if (!question || !userAnswer.trim()) return;
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/decision/calibration-submit`, {
        question_id: question.id,
        user_answer: parseFloat(userAnswer),
        confidence,
      });
      setResult(res.data);
      setQuestionCount(prev => prev + 1);
      fetchStats();
    } catch {
      console.error('提交失败');
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    fetchQuestion();
  };

  const getAccuracyColor = (accuracy: string) => {
    if (accuracy === 'excellent') return '#3fb950';
    if (accuracy === 'good') return '#58a6ff';
    if (accuracy === 'fair') return '#d29922';
    return '#f85149';
  };

  // 统计面板
  if (showStats && stats) {
    return (
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
          <button onClick={() => setShowStats(false)} style={{
            background: 'none', border: 'none', color: 'var(--text-muted)',
            fontSize: 18, cursor: 'pointer',
          }}>←</button>
          <h3 style={{ color: 'var(--text-primary)', margin: 0, fontSize: 18 }}>
            📊 校准训练统计
          </h3>
        </div>

        {stats.status === 'insufficient_data' ? (
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 12, padding: 24,
            border: '1px solid var(--border-primary)', textAlign: 'center',
          }}>
            <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
              {stats.message}
            </div>
          </div>
        ) : (
          <>
            {/* 核心指标 */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20,
            }}>
              {[
                { label: '总体准确率', value: `${stats.overall_accuracy}%`, color: '#3fb950' },
                { label: '平均置信度', value: `${stats.avg_confidence}%`, color: '#58a6ff' },
                { label: '过度自信', value: `${stats.overconfidence_score > 0 ? '+' : ''}${stats.overconfidence_score}%`,
                  color: stats.overconfidence_score > 10 ? '#f85149' : '#3fb950' },
              ].map((item, i) => (
                <div key={i} style={{
                  background: 'var(--bg-secondary)', borderRadius: 10, padding: 16,
                  border: '1px solid var(--border-primary)', textAlign: 'center',
                }}>
                  <div style={{ fontSize: 24, fontWeight: 900, color: item.color }}>{item.value}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{item.label}</div>
                </div>
              ))}
            </div>

            {/* 校准消息 */}
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 10, padding: 16,
              border: '1px solid var(--border-primary)', marginBottom: 20,
            }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14, marginBottom: 6 }}>
                校准评估
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>
                {stats.cal_message}
              </div>
            </div>

            {/* 校准曲线 */}
            {stats.calibration_curve.length > 0 && (
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 10, padding: 16,
                border: '1px solid var(--border-primary)', marginBottom: 20,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14, marginBottom: 12 }}>
                  校准曲线（置信度 vs 实际准确率）
                </div>
                {stats.calibration_curve.map((point, i) => (
                  <div key={i} style={{ marginBottom: 10 }}>
                    <div style={{
                      display: 'flex', justifyContent: 'space-between', marginBottom: 4,
                    }}>
                      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                        置信度 {point.confidence}%
                      </span>
                      <span style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>
                        实际 {point.actual_accuracy}% ({point.sample_size}题)
                      </span>
                    </div>
                    <div style={{
                      height: 8, borderRadius: 4, background: 'var(--bg-tertiary)',
                      position: 'relative', overflow: 'hidden',
                    }}>
                      {/* 置信度基准线 */}
                      <div style={{
                        position: 'absolute', left: `${point.confidence}%`,
                        top: 0, bottom: 0, width: 2, background: '#58a6ff40',
                      }} />
                      {/* 实际准确率 */}
                      <div style={{
                        height: '100%', borderRadius: 4,
                        background: Math.abs(point.gap) < 10 ? '#3fb950' : Math.abs(point.gap) < 20 ? '#d29922' : '#f85149',
                        width: `${point.actual_accuracy}%`,
                      }} />
                    </div>
                    {Math.abs(point.gap) >= 10 && (
                      <div style={{
                        fontSize: 11, color: point.gap > 0 ? '#f85149' : '#d29922', marginTop: 2,
                      }}>
                        {point.gap > 0 ? `过度自信 ${point.gap}%` : `过度保守 ${Math.abs(point.gap)}%`}
                      </div>
                    )}
                  </div>
                ))}
                <div style={{
                  marginTop: 8, fontSize: 12, color: 'var(--text-muted)',
                  display: 'flex', gap: 16,
                }}>
                  <span>蓝色线 = 置信度</span>
                  <span>彩色条 = 实际准确率</span>
                </div>
              </div>
            )}

            <button onClick={() => setShowStats(false)} style={{
              width: '100%', padding: '12px', background: '#58a6ff', border: 'none',
              borderRadius: 8, color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}>
              继续训练
            </button>
          </>
        )}
      </div>
    );
  }

  // 结果展示
  if (result && question) {
    const accColor = getAccuracyColor(result.accuracy);
    return (
      <div>
        <h3 style={{ color: 'var(--text-primary)', marginBottom: 20, fontSize: 18 }}>
          🎯 校准训练
        </h3>

        {/* 结果卡片 */}
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 16, padding: 24,
          border: `2px solid ${accColor}`, marginBottom: 20,
        }}>
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>
              {result.accuracy === 'excellent' ? '🎯' : result.accuracy === 'good' ? '✅' : result.accuracy === 'fair' ? '⚠️' : '❌'}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: accColor }}>
              {result.accuracy_text}
            </div>
          </div>

          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16,
          }}>
            <div style={{
              background: 'var(--bg-tertiary)', borderRadius: 8, padding: 12, textAlign: 'center',
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>你的答案</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
                {result.user_answer}{result.unit}
              </div>
            </div>
            <div style={{
              background: 'var(--bg-tertiary)', borderRadius: 8, padding: 12, textAlign: 'center',
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>参考答案</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#58a6ff' }}>
                {result.reference_answer}{result.unit}
              </div>
            </div>
          </div>

          <div style={{
            display: 'flex', justifyContent: 'space-between', padding: '8px 0',
            borderTop: '1px solid var(--border-primary)',
          }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>偏差</span>
            <span style={{ color: accColor, fontWeight: 600, fontSize: 13 }}>{result.error_pct}%</span>
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between', padding: '8px 0',
            borderTop: '1px solid var(--border-primary)',
          }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>你的置信度</span>
            <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 13 }}>{result.confidence}%</span>
          </div>
        </div>

        {/* 解释 */}
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 10, padding: 16,
          border: '1px solid var(--border-primary)', marginBottom: 20,
        }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14, marginBottom: 6 }}>
            知识点
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>
            {result.explanation}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button onClick={() => setShowStats(true)} style={{
            padding: '12px 20px', background: 'var(--bg-secondary)',
            border: '1px solid var(--border-primary)', borderRadius: 8,
            color: 'var(--text-secondary)', fontSize: 14, cursor: 'pointer',
          }}>
            📊 查看统计
          </button>
          <button onClick={handleNext} style={{
            flex: 1, padding: '12px 20px', background: '#58a6ff', border: 'none',
            borderRadius: 8, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer',
          }}>
            下一题 →
          </button>
        </div>
      </div>
    );
  }

  // 答题界面
  if (!question) return null;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h3 style={{ color: 'var(--text-primary)', margin: 0, fontSize: 18 }}>
          🎯 校准训练
        </h3>
        <button onClick={() => setShowStats(true)} style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
          borderRadius: 6, padding: '6px 12px', color: 'var(--text-muted)',
          fontSize: 12, cursor: 'pointer',
        }}>
          📊 统计
        </button>
      </div>

      {/* 进度 */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', marginBottom: 12,
        color: 'var(--text-muted)', fontSize: 13,
      }}>
        <span>类别：{question.category}</span>
        <span>已训练 {questionCount} 题</span>
      </div>

      {/* 题目 */}
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 16, padding: 24,
        border: '1px solid var(--border-primary)', marginBottom: 20,
      }}>
        <div style={{
          color: 'var(--text-primary)', fontSize: 16, fontWeight: 600,
          lineHeight: 1.7, marginBottom: 20,
        }}>
          {question.question}
        </div>

        {/* 答案输入 */}
        <div style={{ marginBottom: 20 }}>
          <label style={{
            display: 'block', color: 'var(--text-secondary)',
            fontSize: 14, fontWeight: 600, marginBottom: 6,
          }}>
            你的答案（{question.unit}）
          </label>
          <input
            type="number"
            value={userAnswer}
            onChange={(e) => setUserAnswer(e.target.value)}
            placeholder={`输入数字，单位：${question.unit}`}
            style={{
              width: '100%', padding: '12px 14px',
              background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
              borderRadius: 8, color: 'var(--text-primary)', fontSize: 16,
              outline: 'none', boxSizing: 'border-box',
            }}
          />
        </div>

        {/* 置信度选择 */}
        <div style={{ marginBottom: 20 }}>
          <label style={{
            display: 'block', color: 'var(--text-secondary)',
            fontSize: 14, fontWeight: 600, marginBottom: 10,
          }}>
            你有多确定？
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            {CONFIDENCE_LEVELS.map((level) => (
              <button
                key={level}
                onClick={() => setConfidence(level)}
                style={{
                  flex: 1, padding: '10px',
                  border: `2px solid ${confidence === level ? '#58a6ff' : 'var(--border-primary)'}`,
                  borderRadius: 8,
                  background: confidence === level ? '#58a6ff15' : 'var(--bg-secondary)',
                  color: confidence === level ? '#58a6ff' : 'var(--text-secondary)',
                  cursor: 'pointer', fontWeight: confidence === level ? 700 : 400,
                  fontSize: 14, transition: 'all 0.2s',
                }}
              >
                {level}%
              </button>
            ))}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 6 }}>
            选择一个置信度——这比答案本身更重要
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!userAnswer.trim() || loading}
          style={{
            width: '100%', padding: '14px', background: '#58a6ff', border: 'none',
            borderRadius: 8, color: '#fff', fontSize: 15, fontWeight: 700,
            cursor: userAnswer.trim() ? 'pointer' : 'not-allowed',
            opacity: userAnswer.trim() ? 1 : 0.5,
          }}
        >
          {loading ? '提交中...' : '提交答案'}
        </button>
      </div>

      {/* 说明 */}
      <div style={{
        background: '#58a6ff08', borderRadius: 10, padding: 14,
        border: '1px solid #58a6ff20',
      }}>
        <div style={{ color: '#58a6ff', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
          什么是校准训练？
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 13, lineHeight: 1.6 }}>
          校准训练的目标不是让你"答对"，而是让你的置信度和实际准确率匹配。
          如果你说"80%确定"的事情实际上只有60%是对的，说明你过度自信。
          长期训练能让你的概率直觉更准确。
        </div>
      </div>
    </div>
  );
}
