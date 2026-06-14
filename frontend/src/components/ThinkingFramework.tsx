import React, { useState } from 'react';

const frameworks = [
  {
    id: 'system12',
    icon: '🧠',
    title: '快与慢：你的两个大脑',
    source: '《思考快与慢》— Daniel Kahneman',
    color: '#f97316',
    core: '你有两套思维系统。大多数糟糕的投资决策，都是因为让 System 1（快）代替了 System 2（慢）。',
    systems: [
      {
        name: 'System 1（快思维）',
        tag: '自动 · 不费力 · 情绪驱动',
        traits: [
          '看到涨就想买，看到跌就想卖',
          '听到"大家在买"就跟风',
          '亏损时本能地想"再等等会涨回来"',
          '盈利时本能地想"赶紧落袋为安"',
        ],
      },
      {
        name: 'System 2（慢思维）',
        tag: '刻意 · 需要努力 · 逻辑驱动',
        traits: [
          '先看估值，再决定是否买入',
          '制定止损止盈计划，严格执行',
          '用数据而非感觉做判断',
          '在不同情绪下重新审视同一个决策',
        ],
      },
    ],
    insight: '当你感到"紧迫"、"兴奋"、"害怕"时，是 System 1 在控制你。真正的投资纪律，是让 System 2 在关键时刻接管。',
    selfCheck: [
      '你现在做这个决定，是因为分析还是因为感觉？',
      '如果多给你一周时间，你会做同样的决定吗？',
      '你是在逃避痛苦（亏损）还是在追求收益？',
    ],
  },
  {
    id: 'noise',
    icon: '📡',
    title: '噪声：为什么你的判断不稳定',
    source: '《噪声》— Kahneman / Sibony / Sunstein',
    color: '#ec4899',
    core: '好的决策应该在不同时间、不同情绪下保持一致。如果你的判断很容易被外部因素左右，那就是噪声。',
    systems: [
      {
        name: '噪声的四大来源',
        tag: '这些因素让你的判断偏离理性',
        traits: [
          '⏰ 时间压力：「赶紧买，来不及了」— 仓促的判断几乎总是错的',
          '📰 近因效应：「刚看到一个利好消息」— 近期事件的权重被放大',
          '😤 情绪干扰：「今天亏了心情很差」— 情绪状态直接影响判断',
          '👥 社会压力：「群里都说要买」— 群体讨论往往增加噪声而非减少',
        ],
      },
    ],
    insight: '同一个投资决策，早上做和晚上做、开心时做和焦虑时做，可能完全不同。如果答案会变，说明你的判断被噪声污染了。',
    selfCheck: [
      '如果这件事发生在一个月前，你还会这么在意吗？',
      '如果没有人跟你讨论过这个，你还会这么想吗？',
      '如果现在心情平静，你会做同样的决定吗？',
    ],
  },
  {
    id: 'reverse',
    icon: '🔄',
    title: '反直觉思考：主动寻找反面',
    source: '《反直觉思考》— Adam Grant',
    color: '#8b5cf6',
    core: '最危险的不是不知道答案，而是太确信自己知道答案。真正的理性是拥抱被证伪。',
    systems: [
      {
        name: '三种思维模式',
        tag: '你属于哪一种？',
        traits: [
          '🔴 传教士：拼命推销自己的观点，不容质疑',
          '🔴 检察官：只找对方的漏洞，不看自己的',
          '🟢 科学家：主动寻找反面证据，愿意改变观点',
        ],
      },
      {
        name: 'Pre-Mortem（前事分析）',
        tag: '想象决策已经失败，回溯原因',
        traits: [
          '不是问"这个投资会不会亏"',
          '而是问"如果亏了50%，最可能的原因是什么"',
          '把可能的失败原因列出来，逐一检查',
          '这种方法能暴露你潜意识里忽略的风险',
        ],
      },
    ],
    insight: '你不需要证明自己是对的，你需要认真想想自己可能在哪里错了。',
    selfCheck: [
      '你能用100字说服自己不要做这个决策吗？',
      '有没有权威的反对观点？你认真研究过吗？',
      '如果你最信任的人持完全相反的观点，你会怎么想？',
    ],
  },
  {
    id: 'logic',
    icon: '📐',
    title: '逻辑学：检查你的推理链',
    source: '逻辑学基础',
    color: '#3b82f6',
    core: '你的推理链条是否逻辑自洽？很多看起来"有道理"的推理，其实充满了谬误。',
    systems: [
      {
        name: '常见推理谬误',
        tag: '你犯过几个？',
        traits: [
          '🔗 事后归因：消息出来后涨了 ≠ 消息导致了涨',
          '🏆 幸存者偏差：他赚了100倍 ≠ 你也能赚100倍（亏光的人你看不到）',
          '👔 诉诸权威：巴菲特买了 ≠ 你也能买（资金量、期限、风险承受力完全不同）',
          '📊 以偏概全：上次跌了就涨回来 ≠ 这次也会（个案不能代表规律）',
          '⚖️ 非此即彼：不是"现在买"和"永远错过"两个选项（还有回调、分批、换标的）',
          '⛷️ 滑坡谬误：不买就会错过 → 错过就会后悔（每一步都需要证据）',
        ],
      },
    ],
    insight: '投资中最危险的不是"不知道"，而是"觉得自己知道"。检查你的推理链，每一步都需要证据。',
    selfCheck: [
      '你声称的原因和结果之间，真的存在因果关系吗？',
      '你用了多少个案例来支持这个结论？有没有反例？',
      '你的推理中有没有"因为权威说了所以对"的成分？',
    ],
  },
];

export default function ThinkingFramework() {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h3 style={{ color: 'var(--text-primary)', margin: '0 0 8px', fontSize: 20 }}>
          🧠 决策卫士的思维框架
        </h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>
          决策卫士不只是一个检查工具，它背后有一套完整的认知科学体系。
          理解这些框架，能帮你从根本上提升投资决策的质量。
        </p>
      </div>

      {frameworks.map((fw) => (
        <div
          key={fw.id}
          style={{
            background: 'var(--bg-secondary)',
            borderRadius: 12,
            marginBottom: 12,
            border: '1px solid var(--border-primary)',
            borderLeft: `4px solid ${fw.color}`,
            overflow: 'hidden',
          }}
        >
          {/* 标题栏 */}
          <div
            onClick={() => setExpanded(expanded === fw.id ? null : fw.id)}
            style={{
              padding: '16px 20px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              transition: 'background 0.2s',
            }}
          >
            <span style={{ fontSize: 24 }}>{fw.icon}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 16 }}>
                {fw.title}
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>
                {fw.source}
              </div>
            </div>
            <span style={{
              color: 'var(--text-muted)', fontSize: 18,
              transform: expanded === fw.id ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.3s',
            }}>
              ▼
            </span>
          </div>

          {/* 展开内容 */}
          {expanded === fw.id && (
            <div style={{ padding: '0 20px 20px', borderTop: '1px solid var(--border-primary)' }}>
              {/* 核心思想 */}
              <div style={{
                background: `${fw.color}10`,
                borderRadius: 8, padding: 14, marginTop: 16, marginBottom: 16,
                border: `1px solid ${fw.color}30`,
              }}>
                <div style={{ fontWeight: 600, color: fw.color, fontSize: 13, marginBottom: 6 }}>
                  💡 核心思想
                </div>
                <div style={{ color: 'var(--text-primary)', fontSize: 14, lineHeight: 1.7 }}>
                  {fw.core}
                </div>
              </div>

              {/* 系统/概念 */}
              {fw.systems.map((sys, i) => (
                <div key={i} style={{ marginBottom: 16 }}>
                  <div style={{
                    fontWeight: 600, color: 'var(--text-primary)', fontSize: 15, marginBottom: 4,
                  }}>
                    {sys.name}
                  </div>
                  <div style={{
                    color: fw.color, fontSize: 12, marginBottom: 10, fontWeight: 500,
                  }}>
                    {sys.tag}
                  </div>
                  {sys.traits.map((trait, j) => (
                    <div key={j} style={{
                      color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6,
                      paddingLeft: 12, marginBottom: 6,
                      borderLeft: `2px solid ${fw.color}40`,
                    }}>
                      {trait}
                    </div>
                  ))}
                </div>
              ))}

              {/* 洞察 */}
              <div style={{
                background: 'var(--bg-tertiary)',
                borderRadius: 8, padding: 14, marginBottom: 16,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13, marginBottom: 6 }}>
                  🎯 关键洞察
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.7, fontStyle: 'italic' }}>
                  "{fw.insight}"
                </div>
              </div>

              {/* 自检问题 */}
              <div>
                <div style={{
                  fontWeight: 600, color: 'var(--text-primary)', fontSize: 13, marginBottom: 10,
                }}>
                  ✅ 自检问题
                </div>
                {fw.selfCheck.map((q, k) => (
                  <div key={k} style={{
                    background: 'var(--bg-secondary)',
                    borderRadius: 6, padding: '10px 14px', marginBottom: 6,
                    border: '1px solid var(--border-primary)',
                    color: 'var(--text-primary)', fontSize: 14, lineHeight: 1.5,
                  }}>
                    {k + 1}. {q}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}

      {/* 底部总结 */}
      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: 12, padding: 20, marginTop: 8,
        border: '1px solid var(--border-primary)',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
          🛡️ 决策卫士的核心信念
        </div>
        <div style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.8 }}>
          投资中最危险的不是亏损，而是在情绪驱动下做出的决策。<br />
          真正的理性不是"不犯错"，而是"知道自己可能在哪里犯错"。<br />
          每一次决策前的自检，都是在训练你的 System 2 接管 System 1。
        </div>
      </div>
    </div>
  );
}
