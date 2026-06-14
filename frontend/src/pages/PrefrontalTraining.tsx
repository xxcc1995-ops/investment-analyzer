import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';

const API_BASE = '/api';

// ============================================================
// 类型定义
// ============================================================

interface Exercise {
  id: string;
  name: string;
  icon: string;
  color: string;
  desc: string;
  investment_tip: string;
  duration: string;
  question_count: number;
}

interface TrainingQuestion {
  exercise_type: string;
  exercise_name: string;
  question: any;
}

interface TrainingResult {
  score: number;
  correct: boolean;
  feedback: string;
  explanation: string;
  difficulty: number;
}

interface TrainingStats {
  status: string;
  total_sessions: number;
  by_exercise: Record<string, { count: number; avg_score: number; accuracy: number }>;
  recent_scores: { exercise_type: string; score: number; timestamp: string }[];
  streak: number;
  recommendation: { exercise_type: string; name: string; reason: string } | null;
  message?: string;
}

// ============================================================
// 主组件
// ============================================================

export default function PrefrontalTraining() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [stats, setStats] = useState<TrainingStats | null>(null);
  const [loading, setLoading] = useState(true);

  // 当前练习状态
  const [activeExercise, setActiveExercise] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<TrainingQuestion | null>(null);
  const [questionLoading, setQuestionLoading] = useState(false);
  const [answer, setAnswer] = useState<any>(null);
  const [answerText, setAnswerText] = useState('');
  const [result, setResult] = useState<TrainingResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);

  // 加载数据
  useEffect(() => {
    const load = async () => {
      try {
        const [exRes, statsRes] = await Promise.all([
          axios.get(`${API_BASE}/decision/training/exercises`),
          axios.get(`${API_BASE}/decision/training/stats`),
        ]);
        setExercises(exRes.data);
        setStats(statsRes.data);
      } catch (e) {
        console.error('加载训练数据失败:', e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // 获取题目
  const fetchQuestion = useCallback(async (exerciseType: string) => {
    setQuestionLoading(true);
    setResult(null);
    setAnswer(null);
    setAnswerText('');
    try {
      const res = await axios.get(`${API_BASE}/decision/training/question`, {
        params: { exercise_type: exerciseType },
      });
      setCurrentQuestion(res.data);
    } catch (e) {
      console.error('获取题目失败:', e);
    } finally {
      setQuestionLoading(false);
    }
  }, []);

  // 开始练习
  const startExercise = (exerciseType: string) => {
    setActiveExercise(exerciseType);
    setQuestionCount(0);
    fetchQuestion(exerciseType);
  };

  // 提交答案
  const handleSubmit = async () => {
    if (!currentQuestion || answer === null && !answerText.trim()) return;
    setSubmitting(true);
    try {
      const finalAnswer = answer !== null ? answer : answerText.trim();
      const res = await axios.post(`${API_BASE}/decision/training/submit`, {
        exercise_type: currentQuestion.exercise_type,
        question_id: currentQuestion.question.id,
        answer: finalAnswer,
        confidence: 70,
      });
      setResult(res.data);
      setQuestionCount(prev => prev + 1);
      // 刷新统计
      const statsRes = await axios.get(`${API_BASE}/decision/training/stats`);
      setStats(statsRes.data);
    } catch (e) {
      console.error('提交失败:', e);
    } finally {
      setSubmitting(false);
    }
  };

  // 下一题
  const handleNext = () => {
    if (activeExercise) {
      fetchQuestion(activeExercise);
    }
  };

  // 返回列表
  const handleBack = () => {
    setActiveExercise(null);
    setCurrentQuestion(null);
    setResult(null);
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
        加载训练数据...
      </div>
    );
  }

  // ============================================================
  // 渲染：练习列表
  // ============================================================
  if (!activeExercise) {
    return (
      <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 20px' }}>
        {/* 标题 */}
        <div style={{ marginBottom: 32 }}>
          <h2 style={{ color: 'var(--text-primary)', margin: '0 0 8px', fontSize: 24 }}>
            🧠 前额叶练习
          </h2>
          <p style={{ color: 'var(--text-muted)', margin: 0, fontSize: 14, lineHeight: 1.6 }}>
            前额叶皮层是理性决策的生理基础。像肌肉一样，它可以通过刻意练习增强。
            每天练习几分钟，让你的投资决策更理性。
          </p>
        </div>

        {/* 统计概览 */}
        {stats && stats.status === 'ok' && (
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 16, padding: 24,
            border: '1px solid var(--border-primary)', marginBottom: 24,
          }}>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
              {[
                { label: '总练习', value: stats.total_sessions, suffix: '次', color: '#58a6ff' },
                { label: '连续天数', value: stats.streak, suffix: '天', color: '#3fb950' },
              ].map((item, i) => (
                <div key={i} style={{
                  flex: '1 1 100px', textAlign: 'center',
                  background: 'var(--bg-tertiary)', borderRadius: 10, padding: 16,
                }}>
                  <div style={{ fontSize: 28, fontWeight: 900, color: item.color }}>
                    {item.value}{item.suffix}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                    {item.label}
                  </div>
                </div>
              ))}
            </div>

            {/* 推荐练习 */}
            {stats.recommendation && (
              <div style={{
                background: '#58a6ff10', borderRadius: 10, padding: 14,
                border: '1px solid #58a6ff20',
              }}>
                <div style={{ fontSize: 13, color: '#58a6ff', fontWeight: 600, marginBottom: 4 }}>
                  💡 今日推荐
                </div>
                <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                  <strong>{stats.recommendation.name}</strong> — {stats.recommendation.reason}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 练习卡片 */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
          gap: 16,
        }}>
          {exercises.map(ex => {
            const exStats = stats?.by_exercise?.[ex.id];
            return (
              <div
                key={ex.id}
                onClick={() => startExercise(ex.id)}
                style={{
                  background: 'var(--bg-secondary)', borderRadius: 16, padding: 20,
                  border: '1px solid var(--border-primary)',
                  borderLeft: `4px solid ${ex.color}`,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = ex.color;
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-primary)';
                  e.currentTarget.style.borderLeftColor = ex.color;
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <span style={{ fontSize: 28 }}>{ex.icon}</span>
                  <div>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 16 }}>
                      {ex.name}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {ex.duration} · {ex.question_count}题
                    </div>
                  </div>
                </div>
                <div style={{
                  fontSize: 13, color: 'var(--text-secondary)',
                  lineHeight: 1.6, marginBottom: 12,
                }}>
                  {ex.desc}
                </div>
                <div style={{
                  fontSize: 12, color: ex.color,
                  padding: '6px 10px', background: `${ex.color}10`,
                  borderRadius: 6, lineHeight: 1.5,
                }}>
                  💡 {ex.investment_tip}
                </div>
                {exStats && (
                  <div style={{
                    display: 'flex', gap: 12, marginTop: 12,
                    paddingTop: 12, borderTop: '1px solid var(--border-primary)',
                  }}>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      已练 {exStats.count} 次
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      平均 {exStats.avg_score} 分
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      准确率 {exStats.accuracy}%
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ============================================================
  // 渲染：练习进行中
  // ============================================================
  const exercise = exercises.find(e => e.id === activeExercise);

  if (questionLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
        加载题目...
      </div>
    );
  }

  if (!currentQuestion) return null;

  const q = currentQuestion.question;
  const isDelayDiscounting = activeExercise === 'delay_discounting';
  const isSunkCost = activeExercise === 'sunk_cost';
  const isEmotionLabeling = activeExercise === 'emotion_labeling';
  const isBaseRate = activeExercise === 'base_rate';
  const isAnchoring = activeExercise === 'anchoring';
  const isInversion = activeExercise === 'inversion';

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 20px' }}>
      {/* 头部 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button onClick={handleBack} style={{
          background: 'none', border: 'none', color: 'var(--text-muted)',
          fontSize: 20, cursor: 'pointer',
        }}>←</button>
        <span style={{ fontSize: 24 }}>{exercise?.icon}</span>
        <div>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 18 }}>
            {exercise?.name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            第 {questionCount + 1} 题
          </div>
        </div>
      </div>

      {/* 题目卡片 */}
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 16, padding: 24,
        border: '1px solid var(--border-primary)', marginBottom: 20,
      }}>
        {/* 延迟满足 & 沉没成本 */}
        {(isDelayDiscounting || isSunkCost) && (
          <>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
              {q.scenario}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { value: 'A', label: q.option_a },
                { value: 'B', label: q.option_b },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => !result && setAnswer(opt.value)}
                  style={{
                    padding: '14px 16px', borderRadius: 10,
                    border: `2px solid ${answer === opt.value
                      ? (result ? (opt.value === q.correct || q.correct === 'depends' ? '#3fb950' : '#f85149') : '#58a6ff')
                      : 'var(--border-primary)'}`,
                    background: answer === opt.value
                      ? (result ? (opt.value === q.correct || q.correct === 'depends' ? '#3fb95015' : '#f8514915') : '#58a6ff15')
                      : 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                    cursor: result ? 'default' : 'pointer',
                    fontSize: 15, textAlign: 'left',
                    transition: 'all 0.2s',
                  }}
                >
                  <strong>{opt.value}.</strong> {opt.label}
                </button>
              ))}
            </div>
          </>
        )}

        {/* 情绪标签 */}
        {isEmotionLabeling && (
          <>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
              {q.scenario}
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 12 }}>
              选择你感受到的情绪（可多选）：
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {q.emotions?.map((emotion: string) => {
                const isSelected = Array.isArray(answer) && answer.includes(emotion);
                const isCorrect = q.correct?.includes(emotion);
                return (
                  <button
                    key={emotion}
                    onClick={() => {
                      if (result) return;
                      const current = Array.isArray(answer) ? [...answer] : [];
                      if (current.includes(emotion)) {
                        setAnswer(current.filter(e => e !== emotion));
                      } else {
                        setAnswer([...current, emotion]);
                      }
                    }}
                    style={{
                      padding: '8px 16px', borderRadius: 20,
                      border: `2px solid ${isSelected
                        ? (result ? (isCorrect ? '#3fb950' : '#f85149') : '#8b5cf6')
                        : 'var(--border-primary)'}`,
                      background: isSelected
                        ? (result ? (isCorrect ? '#3fb95015' : '#f8514915') : '#8b5cf615')
                        : 'var(--bg-tertiary)',
                      color: isSelected ? '#8b5cf6' : 'var(--text-secondary)',
                      cursor: result ? 'default' : 'pointer',
                      fontSize: 14,
                    }}
                  >
                    {emotion}
                  </button>
                );
              })}
            </div>
          </>
        )}

        {/* 基准率 */}
        {isBaseRate && (
          <>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
              {q.question}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="number"
                value={answerText}
                onChange={e => setAnswerText(e.target.value)}
                placeholder="输入你的答案"
                disabled={!!result}
                style={{
                  flex: 1, padding: '12px 14px',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-primary)',
                  borderRadius: 8, color: 'var(--text-primary)',
                  fontSize: 16, outline: 'none',
                }}
              />
              <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>{q.unit}</span>
            </div>
          </>
        )}

        {/* 反转思维 */}
        {isInversion && (
          <>
            <div style={{
              fontSize: 16, fontWeight: 600, color: 'var(--text-primary)',
              marginBottom: 8, fontStyle: 'italic',
            }}>
              "{q.thesis}"
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 16 }}>
              {q.task}
            </div>
            <textarea
              value={answerText}
              onChange={e => setAnswerText(e.target.value)}
              placeholder="写下你的反面观点..."
              disabled={!!result}
              style={{
                width: '100%', minHeight: 120, padding: '14px',
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-primary)',
                borderRadius: 8, color: 'var(--text-primary)',
                fontSize: 15, outline: 'none',
                resize: 'vertical' as const, boxSizing: 'border-box',
              }}
            />
            {result && q.hints && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>
                  参考反面观点：
                </div>
                {q.hints.map((hint: string, i: number) => (
                  <div key={i} style={{
                    fontSize: 13, color: 'var(--text-secondary)',
                    padding: '6px 0', borderBottom: '1px solid var(--border-primary)',
                  }}>
                    {i + 1}. {hint}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* 锚定抵抗 */}
        {isAnchoring && (
          <>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
              {q.scenario}
            </div>
            <div style={{
              fontSize: 13, color: '#ec4899', marginBottom: 16,
              padding: '8px 12px', background: '#ec489910', borderRadius: 8,
            }}>
              ⚓ {q.anchor}
            </div>
            {q.options ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {q.options.map((opt: string, i: number) => (
                  <button
                    key={i}
                    onClick={() => !result && setAnswer(i)}
                    style={{
                      padding: '14px 16px', borderRadius: 10,
                      border: `2px solid ${answer === i
                        ? (result ? (i === q.correct ? '#3fb950' : '#f85149') : '#ec4899')
                        : 'var(--border-primary)'}`,
                      background: answer === i
                        ? (result ? (i === q.correct ? '#3fb95015' : '#f8514915') : '#ec489915')
                        : 'var(--bg-tertiary)',
                      color: 'var(--text-primary)',
                      cursor: result ? 'default' : 'pointer',
                      fontSize: 15, textAlign: 'left',
                    }}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="number"
                  value={answerText}
                  onChange={e => setAnswerText(e.target.value)}
                  placeholder="输入你的答案"
                  disabled={!!result}
                  style={{
                    flex: 1, padding: '12px 14px',
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-primary)',
                    borderRadius: 8, color: 'var(--text-primary)',
                    fontSize: 16, outline: 'none',
                  }}
                />
                <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>{q.unit}</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* 结果 */}
      {result && (
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 16, padding: 24,
          border: `2px solid ${result.score >= 80 ? '#3fb950' : result.score >= 50 ? '#d29922' : '#f85149'}`,
          marginBottom: 20,
        }}>
          <div style={{ textAlign: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>
              {result.score >= 80 ? '🎯' : result.score >= 50 ? '👍' : '🤔'}
            </div>
            <div style={{
              fontSize: 32, fontWeight: 900,
              color: result.score >= 80 ? '#3fb950' : result.score >= 50 ? '#d29922' : '#f85149',
            }}>
              {result.score} 分
            </div>
          </div>
          <div style={{
            fontSize: 15, color: 'var(--text-primary)',
            lineHeight: 1.7, marginBottom: 12,
          }}>
            {result.feedback}
          </div>
          {result.explanation && (
            <div style={{
              fontSize: 13, color: 'var(--text-muted)',
              padding: '10px 14px', background: 'var(--bg-tertiary)',
              borderRadius: 8, lineHeight: 1.6,
            }}>
              💡 {result.explanation}
            </div>
          )}
        </div>
      )}

      {/* 按钮 */}
      <div style={{ display: 'flex', gap: 12 }}>
        {!result ? (
          <button
            onClick={handleSubmit}
            disabled={submitting || (answer === null && !answerText.trim())}
            style={{
              flex: 1, padding: '14px',
              background: (answer !== null || answerText.trim()) ? '#58a6ff' : 'var(--bg-tertiary)',
              border: 'none', borderRadius: 8,
              color: (answer !== null || answerText.trim()) ? '#fff' : 'var(--text-muted)',
              fontSize: 15, fontWeight: 700,
              cursor: (answer !== null || answerText.trim()) ? 'pointer' : 'not-allowed',
            }}
          >
            {submitting ? '提交中...' : '提交答案'}
          </button>
        ) : (
          <>
            <button onClick={handleNext} style={{
              flex: 1, padding: '14px', background: '#58a6ff',
              border: 'none', borderRadius: 8, color: '#fff',
              fontSize: 15, fontWeight: 700, cursor: 'pointer',
            }}>
              下一题 →
            </button>
            <button onClick={handleBack} style={{
              padding: '14px 20px', background: 'var(--bg-secondary)',
              border: '1px solid var(--border-primary)', borderRadius: 8,
              color: 'var(--text-secondary)', fontSize: 14, cursor: 'pointer',
            }}>
              返回列表
            </button>
          </>
        )}
      </div>
    </div>
  );
}
