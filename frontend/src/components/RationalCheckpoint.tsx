import React, { useState, useEffect, useRef, useCallback } from 'react';

// ============================================================
// 交易前强制理性检查点
//
// 三阶段设计（基于认知科学）：
// Phase 1: 箱式呼吸 — 激活副交感神经，抑制杏仁核
// Phase 2: 关键一问 — 强制 System 2 参与
// Phase 3: 预承诺 — 实施意图，锁定纪律
// ============================================================

interface RationalCheckpointProps {
  open: boolean;
  actionType: 'buy' | 'sell' | 'adjust' | 'analyze';
  target: string;
  onPass: () => void;
  onCancel: () => void;
}

type CheckpointPhase = 'breathing' | 'question' | 'commitment';

// 呼吸阶段配置
const BREATH_PHASES = [
  { label: '吸气', duration: 4, instruction: '慢慢吸气...' },
  { label: '屏住', duration: 4, instruction: '屏住呼吸...' },
  { label: '呼气', duration: 4, instruction: '慢慢呼气...' },
  { label: '屏住', duration: 4, instruction: '屏住呼吸...' },
];
const TOTAL_BREATH_SECONDS = 16; // 一个完整周期
const BREATH_CYCLES = 1; // 做几个周期

// 根据操作类型的问题配置
const ACTION_CONFIG = {
  buy: {
    question: '如果你明天看到这只股票跌了20%，你还会买入吗？请写下你的理由。',
    placeholder: '例如：我会买入，因为我分析的是长期价值，短期波动不影响我的判断...',
    commitmentLabel: '我已设置止损价位',
    commitmentPlaceholder: '例如：跌破15元止损',
    commitmentHint: '写下具体的止损价格，而不是"跌了就卖"',
    icon: '🔴',
    actionLabel: '买入',
  },
  sell: {
    question: '如果你今天不看账户，你还会做这个卖出决定吗？请写下你的理由。',
    placeholder: '例如：会，因为公司基本面发生了变化，ROE连续两个季度下滑...',
    commitmentLabel: '我确认卖出理由基于基本面变化，而非恐慌',
    commitmentPlaceholder: '',
    commitmentHint: '如果你的理由只是"亏了心里难受"，请重新考虑',
    icon: '🟢',
    actionLabel: '卖出',
  },
  adjust: {
    question: '如果多给你一周时间思考，你会做同样的调仓决定吗？请写下你的理由。',
    placeholder: '例如：会，因为我的资产配置偏离了目标比例，需要再平衡...',
    commitmentLabel: '我已确认调仓逻辑，不是追涨杀跌',
    commitmentPlaceholder: '',
    commitmentHint: '调仓应该基于资产配置策略，而非短期涨跌',
    icon: '🟡',
    actionLabel: '调仓',
  },
  analyze: {
    question: '你做这个分析的目的是什么？是已经决定了想找证据支持，还是真的在客观分析？',
    placeholder: '例如：我还在评估阶段，想客观了解这只标的的优劣...',
    commitmentLabel: '我会客观看待分析结果，包括负面结论',
    commitmentPlaceholder: '',
    commitmentHint: '确认偏差是最常见的认知陷阱',
    icon: '🔍',
    actionLabel: '分析',
  },
};

export default function RationalCheckpoint({
  open, actionType, target, onPass, onCancel,
}: RationalCheckpointProps) {
  const [phase, setPhase] = useState<CheckpointPhase>('breathing');

  // 呼吸状态
  const [breathSecond, setBreathSecond] = useState(0);
  const [breathCycle, setBreathCycle] = useState(0);
  const [breathDone, setBreathDone] = useState(false);

  // 问题状态
  const [answer, setAnswer] = useState('');

  // 预承诺状态
  const [committed, setCommitted] = useState(false);
  const [stopLossValue, setStopLossValue] = useState('');

  const breathTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const config = ACTION_CONFIG[actionType];

  // ============================================================
  // 呼吸计时器
  // ============================================================
  useEffect(() => {
    if (!open || phase !== 'breathing') return;

    setBreathSecond(0);
    setBreathCycle(0);
    setBreathDone(false);

    breathTimerRef.current = setInterval(() => {
      setBreathSecond(prev => {
        const next = prev + 1;
        if (next >= TOTAL_BREATH_SECONDS) {
          setBreathCycle(c => {
            const nextCycle = c + 1;
            if (nextCycle >= BREATH_CYCLES) {
              // 所有周期完成
              clearInterval(breathTimerRef.current!);
              setBreathDone(true);
              return nextCycle;
            }
            return nextCycle;
          });
          return 0; // 重置秒数
        }
        return next;
      });
    }, 1000);

    return () => {
      if (breathTimerRef.current) clearInterval(breathTimerRef.current);
    };
  }, [open, phase]);

  // 重置状态
  useEffect(() => {
    if (open) {
      setPhase('breathing');
      setBreathSecond(0);
      setBreathCycle(0);
      setBreathDone(false);
      setAnswer('');
      setCommitted(false);
      setStopLossValue('');
    }
  }, [open]);

  // 计算当前呼吸阶段
  const getCurrentBreathPhase = () => {
    let elapsed = breathSecond;
    for (const p of BREATH_PHASES) {
      if (elapsed < p.duration) return { ...p, progress: elapsed / p.duration };
      elapsed -= p.duration;
    }
    return { ...BREATH_PHASES[0], progress: 0 };
  };

  const currentBreath = getCurrentBreathPhase();

  // 呼吸动画圆圈大小
  const getCircleScale = () => {
    const label = currentBreath.label;
    const progress = currentBreath.progress;
    if (label === '吸气') return 0.5 + progress * 0.5; // 0.5 → 1.0
    if (label === '呼气') return 1.0 - progress * 0.5; // 1.0 → 0.5
    return label === '屏住' && breathSecond < 8 ? 1.0 : 0.5; // 屏住时保持
  };

  const circleScale = getCircleScale();
  const answerValid = answer.trim().length >= 10;
  const commitmentValid = actionType === 'buy'
    ? (committed && stopLossValue.trim().length > 0)
    : committed;

  // ============================================================
  // 渲染：Phase 1 — 呼吸练习
  // ============================================================
  const renderBreathing = () => (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 8 }}>
        在做{config.actionLabel}决定之前，先让理性上线
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 32 }}>
        {target && `标的：${target}`}
      </div>

      {/* 呼吸动画圆圈 */}
      <div style={{
        width: 200, height: 200, margin: '0 auto 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        {/* 外圈 */}
        <div style={{
          width: 200, height: 200, borderRadius: '50%',
          border: '2px solid var(--border-primary)',
          position: 'absolute',
        }} />
        {/* 动态圆 */}
        <div style={{
          width: 200 * circleScale, height: 200 * circleScale,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${breathDone ? '#3fb95040' : '#58a6ff40'} 0%, transparent 70%)`,
          border: `3px solid ${breathDone ? '#3fb950' : '#58a6ff'}`,
          transition: 'all 0.8s ease-in-out',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            fontSize: 20, fontWeight: 700,
            color: breathDone ? '#3fb950' : 'var(--text-primary)',
          }}>
            {breathDone ? '✓' : currentBreath.label}
          </div>
        </div>
      </div>

      {/* 指导文字 */}
      <div style={{
        fontSize: 18, fontWeight: 600,
        color: breathDone ? '#3fb950' : 'var(--text-primary)',
        marginBottom: 12,
      }}>
        {breathDone ? '呼吸练习完成' : currentBreath.instruction}
      </div>

      {/* 进度 */}
      {!breathDone && (
        <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 24 }}>
          {breathSecond} / {TOTAL_BREATH_SECONDS} 秒
          {BREATH_CYCLES > 1 && ` · 第 ${breathCycle + 1} / ${BREATH_CYCLES} 轮`}
        </div>
      )}

      {/* 进度条 */}
      <div style={{
        height: 4, borderRadius: 2, background: 'var(--bg-tertiary)',
        marginBottom: 24, overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          background: breathDone ? '#3fb950' : '#58a6ff',
          width: breathDone ? '100%' : `${(breathSecond / TOTAL_BREATH_SECONDS) * 100}%`,
          transition: 'width 0.3s',
        }} />
      </div>

      {/* 继续按钮 */}
      <button
        onClick={() => setPhase('question')}
        disabled={!breathDone}
        style={{
          width: '100%', padding: '14px',
          background: breathDone ? '#58a6ff' : 'var(--bg-tertiary)',
          border: 'none', borderRadius: 8,
          color: breathDone ? '#fff' : 'var(--text-muted)',
          fontSize: 15, fontWeight: 700,
          cursor: breathDone ? 'pointer' : 'not-allowed',
          opacity: breathDone ? 1 : 0.5,
          transition: 'all 0.3s',
        }}
      >
        {breathDone ? '继续 →' : '请完成呼吸练习...'}
      </button>

      {/* 取消按钮 */}
      <button
        onClick={onCancel}
        style={{
          width: '100%', padding: '10px',
          background: 'none', border: 'none',
          color: 'var(--text-muted)', fontSize: 13,
          cursor: 'pointer', marginTop: 8,
        }}
      >
        取消操作
      </button>
    </div>
  );

  // ============================================================
  // 渲染：Phase 2 — 关键一问
  // ============================================================
  const renderQuestion = () => (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <div style={{ fontSize: 36, marginBottom: 8 }}>🧠</div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          {config.icon} {config.actionLabel} · {target || '投资标的'}
        </div>
      </div>

      {/* 问题 */}
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 12, padding: 20,
        border: '1px solid var(--border-primary)',
        borderLeft: '4px solid #58a6ff',
        marginBottom: 20,
      }}>
        <div style={{
          fontSize: 16, fontWeight: 600,
          color: 'var(--text-primary)', lineHeight: 1.7,
        }}>
          {config.question}
        </div>
      </div>

      {/* 回答 */}
      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder={config.placeholder}
        style={{
          width: '100%', minHeight: 120, padding: '14px',
          background: 'var(--bg-tertiary)',
          border: `2px solid ${answer.length > 0 && !answerValid ? '#f8514940' : 'var(--border-primary)'}`,
          borderRadius: 10, color: 'var(--text-primary)',
          fontSize: 15, outline: 'none',
          resize: 'vertical' as const, boxSizing: 'border-box',
          lineHeight: 1.6,
        }}
      />

      {/* 字数提示 */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', marginTop: 6, marginBottom: 20,
      }}>
        <span style={{
          fontSize: 12,
          color: answer.length > 0 && !answerValid ? '#f85149' : 'var(--text-muted)',
        }}>
          {answer.length > 0 && !answerValid
            ? `至少需要10个字（当前 ${answer.length} 字）`
            : '认真思考后回答'}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {answer.length} 字
        </span>
      </div>

      {/* 导航 */}
      <div style={{ display: 'flex', gap: 12 }}>
        <button
          onClick={() => setPhase('breathing')}
          style={{
            padding: '12px 20px',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-primary)',
            borderRadius: 8, color: 'var(--text-secondary)',
            fontSize: 14, cursor: 'pointer',
          }}
        >
          ← 重做呼吸
        </button>
        <button
          onClick={() => setPhase('commitment')}
          disabled={!answerValid}
          style={{
            flex: 1, padding: '14px',
            background: answerValid ? '#58a6ff' : 'var(--bg-tertiary)',
            border: 'none', borderRadius: 8,
            color: answerValid ? '#fff' : 'var(--text-muted)',
            fontSize: 15, fontWeight: 700,
            cursor: answerValid ? 'pointer' : 'not-allowed',
            opacity: answerValid ? 1 : 0.5,
          }}
        >
          继续 →
        </button>
      </div>

      {/* 取消 */}
      <button
        onClick={onCancel}
        style={{
          width: '100%', padding: '10px', marginTop: 8,
          background: 'none', border: 'none',
          color: 'var(--text-muted)', fontSize: 13, cursor: 'pointer',
        }}
      >
        取消操作
      </button>
    </div>
  );

  // ============================================================
  // 渲染：Phase 3 — 预承诺
  // ============================================================
  const renderCommitment = () => (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <div style={{ fontSize: 36, marginBottom: 8 }}>🔒</div>
        <div style={{
          fontSize: 18, fontWeight: 700,
          color: 'var(--text-primary)', marginBottom: 4,
        }}>
          最后一步：锁定纪律
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          {config.icon} {config.actionLabel} · {target || '投资标的'}
        </div>
      </div>

      {/* 预承诺勾选 */}
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 12, padding: 20,
        border: '1px solid var(--border-primary)', marginBottom: 16,
      }}>
        <label style={{
          display: 'flex', alignItems: 'flex-start', gap: 12,
          cursor: 'pointer',
        }}>
          <input
            type="checkbox"
            checked={committed}
            onChange={(e) => setCommitted(e.target.checked)}
            style={{
              width: 20, height: 20, marginTop: 2,
              accentColor: '#58a6ff',
              flexShrink: 0,
            }}
          />
          <div>
            <div style={{
              fontSize: 15, fontWeight: 600,
              color: 'var(--text-primary)', lineHeight: 1.6,
            }}>
              {config.commitmentLabel}
            </div>
            {config.commitmentHint && (
              <div style={{
                fontSize: 13, color: 'var(--text-muted)',
                marginTop: 4, lineHeight: 1.5,
              }}>
                {config.commitmentHint}
              </div>
            )}
          </div>
        </label>

        {/* 止损价位输入（仅买入时） */}
        {actionType === 'buy' && committed && (
          <div style={{ marginTop: 16, marginLeft: 32 }}>
            <input
              value={stopLossValue}
              onChange={(e) => setStopLossValue(e.target.value)}
              placeholder={config.commitmentPlaceholder}
              style={{
                width: '100%', padding: '10px 14px',
                background: 'var(--bg-tertiary)',
                border: `2px solid ${stopLossValue.trim() ? '#3fb95040' : '#f8514940'}`,
                borderRadius: 8, color: 'var(--text-primary)',
                fontSize: 15, outline: 'none', boxSizing: 'border-box',
              }}
            />
            <div style={{
              fontSize: 12, color: 'var(--text-muted)', marginTop: 4,
            }}>
              💡 没有止损计划的投资 = 赌博
            </div>
          </div>
        )}
      </div>

      {/* 风险提示 */}
      <div style={{
        background: '#d2992210', borderRadius: 10, padding: 14,
        border: '1px solid #d2992220', marginBottom: 20,
      }}>
        <div style={{
          fontSize: 13, color: '#d29922', lineHeight: 1.7,
        }}>
          ⚠️ 你即将执行{config.actionLabel}操作。请确认你已经：
          <br />1. 完成了呼吸练习，情绪平稳
          <br />2. 认真回答了关键问题
          <br />3. 设定了纪律约束
        </div>
      </div>

      {/* 按钮 */}
      <div style={{ display: 'flex', gap: 12 }}>
        <button
          onClick={() => setPhase('question')}
          style={{
            padding: '12px 20px',
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-primary)',
            borderRadius: 8, color: 'var(--text-secondary)',
            fontSize: 14, cursor: 'pointer',
          }}
        >
          ← 修改回答
        </button>
        <button
          onClick={onPass}
          disabled={!commitmentValid}
          style={{
            flex: 1, padding: '14px',
            background: commitmentValid ? '#3fb950' : 'var(--bg-tertiary)',
            border: 'none', borderRadius: 8,
            color: commitmentValid ? '#fff' : 'var(--text-muted)',
            fontSize: 16, fontWeight: 700,
            cursor: commitmentValid ? 'pointer' : 'not-allowed',
            opacity: commitmentValid ? 1 : 0.5,
          }}
        >
          ✅ 我已理性，执行{config.actionLabel}
        </button>
      </div>

      {/* 取消 */}
      <button
        onClick={onCancel}
        style={{
          width: '100%', padding: '10px', marginTop: 8,
          background: 'none', border: 'none',
          color: 'var(--text-muted)', fontSize: 13, cursor: 'pointer',
        }}
      >
        取消操作
      </button>
    </div>
  );

  if (!open) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      zIndex: 10000,
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      padding: 20,
    }}>
      <div style={{
        background: 'var(--bg-primary)',
        borderRadius: 20, padding: 32,
        maxWidth: 480, width: '100%',
        maxHeight: '90vh', overflow: 'auto',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        {/* 顶部标题 */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 24,
        }}>
          <div style={{
            fontSize: 15, fontWeight: 700,
            color: 'var(--text-primary)',
          }}>
            🛡️ 理性检查点
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['breathing', 'question', 'commitment'] as CheckpointPhase[]).map((p, i) => (
              <div key={p} style={{
                width: 8, height: 8, borderRadius: '50%',
                background: phase === p ? '#58a6ff'
                  : (['breathing', 'question', 'commitment'].indexOf(phase) > i ? '#3fb950' : 'var(--border-primary)'),
                transition: 'all 0.3s',
              }} />
            ))}
          </div>
        </div>

        {phase === 'breathing' && renderBreathing()}
        {phase === 'question' && renderQuestion()}
        {phase === 'commitment' && renderCommitment()}
      </div>
    </div>
  );
}
