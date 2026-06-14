import React, { useState, useCallback, useEffect } from 'react';
import axios from 'axios';

const API_BASE = '/api';

interface Exercise {
  id: number;
  dimension: string;
  name: string;
  icon: string;
  instruction: string;
  prompt: string;
  hint: string;
}

interface WarmupData {
  purpose: string;
  exercises: Exercise[];
}

interface PrefrontalWarmupProps {
  decisionType?: string;
  target?: string;
  thought?: string;
  onComplete?: (answers: Record<number, string>) => void;
}

export default function PrefrontalWarmup({
  decisionType = '',
  target = '',
  thought = '',
  onComplete,
}: PrefrontalWarmupProps) {
  const [warmup, setWarmup] = useState<WarmupData | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [completed, setCompleted] = useState(false);
  const [startTime] = useState(Date.now());

  useEffect(() => {
    const fetchWarmup = async () => {
      try {
        const res = await axios.post(`${API_BASE}/decision/prefrontal-warmup`, {
          decision_type: decisionType,
          target,
          thought,
        });
        setWarmup(res.data);
      } catch {
        // 使用默认热身
        setWarmup({
          purpose: '在做投资决策前，先做5个小练习，让理性大脑上线。',
          exercises: [
            { id: 1, dimension: 'perspective_shift', name: '视角切换', icon: '👤',
              instruction: '你现在不是你自己，而是一个理性的投资顾问。',
              prompt: '作为投资顾问，你会给朋友什么建议？', hint: '切换视角能让你跳出情绪。' },
            { id: 2, dimension: 'probability_calibration', name: '概率校准', icon: '🎲',
              instruction: '不要说会涨或会跌，用概率来表达。',
              prompt: '你认为盈利的概率是多少？给出一个具体百分比。', hint: '说70%比说应该会涨更理性。' },
            { id: 3, dimension: 'disconfirmation_search', name: '证伪搜索', icon: '🔍',
              instruction: '花1分钟专门寻找反对你的证据。',
              prompt: '如果不应该操作，最可能的原因是什么？', hint: '不要问我对不对，要问我可能在哪里错了。' },
            { id: 4, dimension: 'temporal_distance', name: '时间拉远', icon: '⏰',
              instruction: '想象一年后的你回看今天这个决定。',
              prompt: '一年后你会怎么评价现在的你？', hint: '想象未来的自己能降低冲动决策。' },
            { id: 5, dimension: 'quantification_forcing', name: '量化强迫', icon: '📊',
              instruction: '把模糊感觉变成具体数字。',
              prompt: '用一个具体数字表达你的判断。', hint: '量化会让你发现自己的判断没那么确定。' },
          ],
        });
      } finally {
        setLoading(false);
      }
    };
    fetchWarmup();
  }, [decisionType, target, thought]);

  const handleAnswer = (exerciseId: number, answer: string) => {
    setAnswers(prev => ({ ...prev, [exerciseId]: answer }));
  };

  const handleNext = () => {
    if (!warmup) return;
    if (currentStep < warmup.exercises.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      setCompleted(true);
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      onComplete?.(answers);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) setCurrentStep(prev => prev - 1);
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
        正在准备前额叶热身...
      </div>
    );
  }

  if (!warmup) return null;

  if (completed) {
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    const answeredCount = Object.keys(answers).filter(k => answers[Number(k)]?.trim()).length;

    return (
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 16, padding: 32,
        border: '1px solid var(--border-primary)', textAlign: 'center',
      }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🧠</div>
        <h3 style={{ color: 'var(--text-primary)', margin: '0 0 8px', fontSize: 20 }}>
          前额叶已激活
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 20 }}>
          你完成了 {answeredCount}/5 个练习，用时 {elapsed} 秒
        </p>

        <div style={{
          background: '#3fb95015', borderRadius: 10, padding: 16,
          border: '1px solid #3fb95030', marginBottom: 20, textAlign: 'left',
        }}>
          <div style={{ fontWeight: 600, color: '#3fb950', fontSize: 14, marginBottom: 8 }}>
            你的前额叶皮层现在更活跃了
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.7 }}>
            通过视角切换、概率思考、证伪搜索、时间拉远和量化强迫，
            你已经激活了负责理性决策的前额叶皮层。
            现在去做投资决策，你会比刚才更理性。
          </div>
        </div>

        {onComplete && (
          <button onClick={() => onComplete(answers)} style={{
            padding: '12px 24px', background: '#58a6ff', border: 'none',
            borderRadius: 8, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer',
          }}>
            继续做决策 →
          </button>
        )}
      </div>
    );
  }

  const exercise = warmup.exercises[currentStep];
  const progress = ((currentStep + 1) / warmup.exercises.length) * 100;

  return (
    <div>
      {/* 热身说明 */}
      {currentStep === 0 && (
        <div style={{
          background: 'var(--bg-secondary)', borderRadius: 12, padding: 16,
          border: '1px solid var(--border-primary)', marginBottom: 20,
        }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14, marginBottom: 6 }}>
            为什么要做前额叶热身？
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
            {warmup.purpose}
          </div>
        </div>
      )}

      {/* 进度条 */}
      <div style={{
        height: 4, borderRadius: 2, background: 'var(--bg-tertiary)',
        marginBottom: 24, overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', background: '#58a6ff',
          width: `${progress}%`, transition: 'width 0.3s',
        }} />
      </div>

      {/* 练习卡片 */}
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 16, padding: 24,
        border: '1px solid var(--border-primary)', marginBottom: 20,
      }}>
        {/* 步骤信息 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <span style={{ fontSize: 28 }}>{exercise.icon}</span>
          <div>
            <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 17 }}>
              {exercise.name}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
              练习 {currentStep + 1} / {warmup.exercises.length}
            </div>
          </div>
        </div>

        {/* 指导语 */}
        <div style={{
          background: 'var(--bg-tertiary)', borderRadius: 10, padding: 14,
          marginBottom: 16, borderLeft: '3px solid #58a6ff',
        }}>
          <div style={{ color: 'var(--text-primary)', fontSize: 14, lineHeight: 1.7 }}>
            {exercise.instruction}
          </div>
        </div>

        {/* 问题 */}
        <div style={{
          fontWeight: 600, color: 'var(--text-primary)', fontSize: 15,
          marginBottom: 12, lineHeight: 1.6,
        }}>
          {exercise.prompt}
        </div>

        {/* 回答输入 */}
        <textarea
          value={answers[exercise.id] || ''}
          onChange={(e) => handleAnswer(exercise.id, e.target.value)}
          placeholder="认真思考后写下你的回答..."
          style={{
            width: '100%', minHeight: 100, padding: '12px 14px',
            background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
            borderRadius: 8, color: 'var(--text-primary)', fontSize: 15,
            outline: 'none', resize: 'vertical' as const, boxSizing: 'border-box',
          }}
        />

        {/* 提示 */}
        <div style={{
          marginTop: 12, padding: '10px 14px',
          background: '#58a6ff08', borderRadius: 8,
          border: '1px solid #58a6ff20',
        }}>
          <div style={{ color: '#58a6ff', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
            为什么这个练习有用？
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 13, lineHeight: 1.5 }}>
            {exercise.hint}
          </div>
        </div>
      </div>

      {/* 导航按钮 */}
      <div style={{ display: 'flex', gap: 12 }}>
        <button onClick={handlePrev} disabled={currentStep === 0} style={{
          padding: '12px 20px',
          background: currentStep === 0 ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
          border: '1px solid var(--border-primary)', borderRadius: 8,
          color: currentStep === 0 ? 'var(--text-muted)' : 'var(--text-secondary)',
          fontSize: 14, cursor: currentStep === 0 ? 'not-allowed' : 'pointer',
        }}>
          上一个
        </button>
        <button onClick={handleNext} style={{
          flex: 1, padding: '12px 20px', background: '#58a6ff', border: 'none',
          borderRadius: 8, color: '#fff', fontSize: 15, fontWeight: 700, cursor: 'pointer',
        }}>
          {currentStep < warmup.exercises.length - 1 ? '下一个 →' : '完成热身 ✓'}
        </button>
      </div>
    </div>
  );
}
