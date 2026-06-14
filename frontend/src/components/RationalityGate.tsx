import React, { useState, useCallback, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = '/api';

interface RationalityGateProps {
  onPass: () => void;      // 通过检查，进入 App
  onSkip: () => void;      // 跳过检查
  onFullCheck: (intention: string, target: string, thought: string) => void;  // 进入完整检查
}

type GateStep = 'intention' | 'details' | 'breathing' | 'scanning' | 'result';

const INTENTION_OPTIONS = [
  { value: 'browse', label: '👀 随便看看', desc: '看看行情、研究数据', color: '#3fb950', needCheck: false },
  { value: 'research', label: '📊 分析研究', desc: '做基本面分析、估值计算', color: '#58a6ff', needCheck: false },
  { value: 'trade', label: '💰 做交易', desc: '买入、卖出、调仓', color: '#f85149', needCheck: true },
];

const TRADE_TYPES = [
  { value: 'buy', label: '买入', color: '#f85149' },
  { value: 'sell', label: '卖出', color: '#3fb950' },
  { value: 'adjust', label: '调仓', color: '#d29922' },
];

// 箱式呼吸阶段
const BREATH_PHASES = [
  { label: '吸气', duration: 4, instruction: '慢慢吸气...' },
  { label: '屏住', duration: 4, instruction: '屏住呼吸...' },
  { label: '呼气', duration: 4, instruction: '慢慢呼气...' },
  { label: '屏住', duration: 4, instruction: '屏住呼吸...' },
];

interface ScanResult {
  risk_level: string;
  score: number;
  triggers: string[];
  message: string;
  recommendation: string;
}

export default function RationalityGate({ onPass, onSkip, onFullCheck }: RationalityGateProps) {
  const [step, setStep] = useState<GateStep>('intention');
  const [intention, setIntention] = useState('');
  const [tradeType, setTradeType] = useState('buy');
  const [thought, setThought] = useState('');
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);

  // 呼吸状态
  const [breathSecond, setBreathSecond] = useState(0);
  const [breathDone, setBreathDone] = useState(false);
  const breathTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const TOTAL_BREATH = 16; // 一个完整周期

  const handleIntentionSelect = (value: string) => {
    setIntention(value);
    const opt = INTENTION_OPTIONS.find(o => o.value === value);
    if (opt && !opt.needCheck) {
      onPass();
    } else {
      setStep('details');
    }
  };

  const handleStartBreathing = () => {
    setStep('breathing');
    setBreathSecond(0);
    setBreathDone(false);
  };

  // 呼吸计时器
  useEffect(() => {
    if (step !== 'breathing') return;

    breathTimerRef.current = setInterval(() => {
      setBreathSecond(prev => {
        const next = prev + 1;
        if (next >= TOTAL_BREATH) {
          clearInterval(breathTimerRef.current!);
          setBreathDone(true);
          return next;
        }
        return next;
      });
    }, 1000);

    return () => {
      if (breathTimerRef.current) clearInterval(breathTimerRef.current);
    };
  }, [step]);

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
    if (label === '吸气') return 0.5 + progress * 0.5;
    if (label === '呼气') return 1.0 - progress * 0.5;
    return breathSecond < 8 ? 1.0 : 0.5;
  };

  const handleScan = useCallback(async () => {
    setScanning(true);
    setStep('scanning');
    try {
      const res = await axios.post(`${API_BASE}/decision/quick-scan`, {
        intention: tradeType,
        thought: thought.trim(),
      });
      setScanResult(res.data);
      setStep('result');
    } catch {
      onPass();
    } finally {
      setScanning(false);
    }
  }, [tradeType, thought, onPass]);

  const getScoreColor = (score: number) => {
    if (score >= 70) return '#3fb950';
    if (score >= 40) return '#d29922';
    return '#f85149';
  };

  const getRiskIcon = (level: string) => {
    if (level === 'low') return '✅';
    if (level === 'medium') return '⚡';
    return '🛑';
  };

  // ============================================================
  // 渲染
  // ============================================================

  const renderIntention = () => (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>🛡️</div>
        <h2 style={{ color: 'var(--text-primary)', margin: '0 0 8px', fontSize: 22 }}>
          投资理性自检
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>
          在进入投资工具之前，先确认一下你的状态
        </p>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: 15, fontWeight: 600, marginBottom: 16, textAlign: 'center' }}>
          你今天来这里是想做什么？
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {INTENTION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleIntentionSelect(opt.value)}
              style={{
                padding: '16px 20px',
                border: `2px solid ${opt.color}40`,
                borderRadius: 12,
                background: `${opt.color}08`,
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontSize: 15,
                textAlign: 'left',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = opt.color;
                e.currentTarget.style.background = `${opt.color}15`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = `${opt.color}40`;
                e.currentTarget.style.background = `${opt.color}08`;
              }}
            >
              <span style={{ fontSize: 20 }}>{opt.label.split(' ')[0]}</span>
              <div>
                <div style={{ fontWeight: 600 }}>{opt.label.split(' ').slice(1).join(' ')}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 2 }}>{opt.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 只有浏览/研究才有跳过选项，交易意图不显示跳过 */}
      <div style={{ textAlign: 'center', height: 20 }} />
    </div>
  );

  const renderDetails = () => (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <button
            onClick={() => setStep('intention')}
            style={{
              background: 'none', border: 'none',
              color: 'var(--text-muted)', fontSize: 18, cursor: 'pointer',
            }}
          >
            ←
          </button>
          <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 16 }}>
            你打算做什么交易？
          </span>
        </div>

        {/* 交易类型 */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
          {TRADE_TYPES.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTradeType(opt.value)}
              style={{
                flex: 1, padding: '12px',
                border: `2px solid ${tradeType === opt.value ? opt.color : 'var(--border-primary)'}`,
                borderRadius: 8,
                background: tradeType === opt.value ? `${opt.color}15` : 'var(--bg-secondary)',
                color: tradeType === opt.value ? opt.color : 'var(--text-secondary)',
                cursor: 'pointer', fontSize: 15,
                fontWeight: tradeType === opt.value ? 700 : 400,
                transition: 'all 0.2s',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* 当前想法 */}
        <div style={{ marginBottom: 20 }}>
          <label style={{
            display: 'block', color: 'var(--text-secondary)',
            fontSize: 14, fontWeight: 600, marginBottom: 6,
          }}>
            用一句话描述你现在的想法（可选）
          </label>
          <input
            value={thought}
            onChange={(e) => setThought(e.target.value)}
            placeholder="例如：看到朋友赚了不少，我也想试试..."
            style={{
              width: '100%', padding: '12px 14px',
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-primary)',
              borderRadius: 8,
              color: 'var(--text-primary)',
              fontSize: 15, outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 6 }}>
            💡 越诚实越好——情绪化的表达更容易被检测到，这正是自检的意义
          </div>
        </div>

        {/* 开始呼吸按钮 */}
        <button
          onClick={handleStartBreathing}
          style={{
            width: '100%', padding: '14px',
            background: '#58a6ff', border: 'none',
            borderRadius: 8, color: '#fff',
            fontSize: 16, fontWeight: 700, cursor: 'pointer',
          }}
        >
          🧘 先做呼吸练习 →
        </button>
      </div>
    </div>
  );

  const renderBreathing = () => {
    const circleScale = getCircleScale();

    return (
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 24 }}>
          在做交易决定之前，先让理性上线
        </div>

        {/* 呼吸动画圆圈 */}
        <div style={{
          width: 180, height: 180, margin: '0 auto 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
        }}>
          <div style={{
            width: 180, height: 180, borderRadius: '50%',
            border: '2px solid var(--border-primary)',
            position: 'absolute',
          }} />
          <div style={{
            width: 180 * circleScale, height: 180 * circleScale,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${breathDone ? '#3fb95040' : '#58a6ff40'} 0%, transparent 70%)`,
            border: `3px solid ${breathDone ? '#3fb950' : '#58a6ff'}`,
            transition: 'all 0.8s ease-in-out',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              fontSize: 18, fontWeight: 700,
              color: breathDone ? '#3fb950' : 'var(--text-primary)',
            }}>
              {breathDone ? '✓' : currentBreath.label}
            </div>
          </div>
        </div>

        <div style={{
          fontSize: 16, fontWeight: 600,
          color: breathDone ? '#3fb950' : 'var(--text-primary)',
          marginBottom: 10,
        }}>
          {breathDone ? '呼吸练习完成' : currentBreath.instruction}
        </div>

        {!breathDone && (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>
            {breathSecond} / {TOTAL_BREATH} 秒
          </div>
        )}

        {/* 进度条 */}
        <div style={{
          height: 4, borderRadius: 2, background: 'var(--bg-tertiary)',
          marginBottom: 20, overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            background: breathDone ? '#3fb950' : '#58a6ff',
            width: breathDone ? '100%' : `${(breathSecond / TOTAL_BREATH) * 100}%`,
            transition: 'width 0.3s',
          }} />
        </div>

        <button
          onClick={handleScan}
          disabled={!breathDone}
          style={{
            width: '100%', padding: '14px',
            background: breathDone ? '#58a6ff' : 'var(--bg-tertiary)',
            border: 'none', borderRadius: 8,
            color: breathDone ? '#fff' : 'var(--text-muted)',
            fontSize: 16, fontWeight: 700,
            cursor: breathDone ? 'pointer' : 'not-allowed',
            opacity: breathDone ? 1 : 0.5,
          }}
        >
          {breathDone ? '🧠 开始情绪扫描' : '请完成呼吸练习...'}
        </button>

        <button
          onClick={() => setStep('details')}
          style={{
            width: '100%', padding: '10px', marginTop: 8,
            background: 'none', border: 'none',
            color: 'var(--text-muted)', fontSize: 13, cursor: 'pointer',
          }}
        >
          ← 返回修改
        </button>
      </div>
    );
  };

  const renderScanning = () => (
    <div style={{ textAlign: 'center', padding: '40px 0' }}>
      <div style={{
        width: 60, height: 60, borderRadius: '50%',
        border: '3px solid var(--border-primary)',
        borderTopColor: '#58a6ff',
        animation: 'spin 1s linear infinite',
        margin: '0 auto 20px',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{ color: 'var(--text-primary)', fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
        正在扫描你的情绪状态...
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>
        检查快思维陷阱、情绪化表达、噪声信号
      </div>
    </div>
  );

  const renderResult = () => {
    if (!scanResult) return null;

    const scoreColor = getScoreColor(scanResult.score);
    const riskIcon = getRiskIcon(scanResult.risk_level);

    return (
      <div>
        {/* 分数展示 */}
        <div style={{
          textAlign: 'center', marginBottom: 24,
          background: `${scoreColor}08`,
          borderRadius: 16, padding: 24,
          border: `2px solid ${scoreColor}30`,
        }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>{riskIcon}</div>
          <div style={{
            fontSize: 56, fontWeight: 900, color: scoreColor, lineHeight: 1,
          }}>
            {scanResult.score}
          </div>
          <div style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 8 }}>
            理性指数
          </div>
        </div>

        {/* 消息 */}
        <div style={{
          background: 'var(--bg-secondary)',
          borderRadius: 10, padding: 16, marginBottom: 16,
          border: '1px solid var(--border-primary)',
        }}>
          <div style={{ color: 'var(--text-primary)', fontSize: 15, lineHeight: 1.6 }}>
            {scanResult.message}
          </div>
        </div>

        {/* 触发词 */}
        {scanResult.triggers.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 8 }}>
              检测到的情绪信号：
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {scanResult.triggers.map((t, i) => (
                <span key={i} style={{
                  background: `${scoreColor}15`, color: scoreColor,
                  padding: '4px 10px', borderRadius: 6, fontSize: 13,
                }}>
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 20 }}>
          {scanResult.recommendation === 'pass' && (
            <>
              <button onClick={onPass} style={primaryBtnStyle}>
                ✅ 理性状态良好，进入投资工具
              </button>
            </>
          )}

          {scanResult.recommendation === 'warn' && (
            <>
              <div style={{
                background: '#d2992215', borderRadius: 10, padding: 14,
                border: '1px solid #d2992230', marginBottom: 4,
              }}>
                <div style={{ color: '#d29922', fontWeight: 600, fontSize: 14, marginBottom: 6 }}>
                  💡 建议
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.5 }}>
                  先深呼吸3次，想清楚再行动。问自己：如果多给我一周时间，我会做同样的决定吗？
                </div>
              </div>
              <button onClick={onPass} style={primaryBtnStyle}>
                我已冷静，继续进入
              </button>
              <button
                onClick={() => onFullCheck(tradeType, '', thought)}
                style={secondaryBtnStyle}
              >
                做完整的决策检查 →
              </button>
            </>
          )}

          {scanResult.recommendation === 'full_check' && (
            <>
              <div style={{
                background: '#f8514915', borderRadius: 10, padding: 14,
                border: '1px solid #f8514930', marginBottom: 4,
              }}>
                <div style={{ color: '#f85149', fontWeight: 600, fontSize: 14, marginBottom: 6 }}>
                  ⚠️ 强烈建议
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.5 }}>
                  你的表达充满了情绪。现在不是做投资决策的好时机。
                  建议至少冷静30分钟后再来。
                </div>
              </div>
              <button
                onClick={() => onFullCheck(tradeType, '', thought)}
                style={{ ...primaryBtnStyle, background: '#f85149' }}
              >
                做完整的决策检查 →
              </button>
              <button onClick={onPass} style={secondaryBtnStyle}>
                我坚持要继续（不推荐）
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0, 0, 0, 0.85)',
      zIndex: 9999,
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      padding: 20,
    }}>
      <div style={{
        background: 'var(--bg-primary)',
        borderRadius: 20,
        padding: 32,
        maxWidth: 480,
        width: '100%',
        maxHeight: '90vh',
        overflow: 'auto',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        {step === 'intention' && renderIntention()}
        {step === 'details' && renderDetails()}
        {step === 'breathing' && renderBreathing()}
        {step === 'scanning' && renderScanning()}
        {step === 'result' && renderResult()}
      </div>
    </div>
  );
}

const primaryBtnStyle: React.CSSProperties = {
  width: '100%', padding: '14px',
  background: '#58a6ff', border: 'none',
  borderRadius: 8, color: '#fff',
  fontSize: 15, fontWeight: 700, cursor: 'pointer',
};

const secondaryBtnStyle: React.CSSProperties = {
  width: '100%', padding: '12px',
  background: 'var(--bg-secondary)',
  border: '1px solid var(--border-primary)',
  borderRadius: 8, color: 'var(--text-secondary)',
  fontSize: 14, cursor: 'pointer',
};
