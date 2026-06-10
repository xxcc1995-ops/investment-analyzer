// @ts-nocheck
import React, { useState, useMemo } from 'react';
import ReactECharts from '../lib/ECharts';
import { stockApi, valuationApi, StockBasicInfo, StockFinancials, DCFValuation } from '../services/api';

interface FragilityDimension {
  name: string;
  score: number;
  max: number;
  label: string;
  signal: string;
  value: string;
}

interface FragilityResult {
  code: string;
  name: string;
  total_score: number;
  max_score: number;
  verdict: string;
  verdict_desc: string;
  color: string;
  dimensions: FragilityDimension[];
  warnings: { name: string; label: string; signal: string }[];
  report_period: string;
}

const VERDICT_COLORS: Record<string, string> = {
  '反脆弱型': '#16a34a',
  '稳健型': '#ca8a04',
  '脆弱型': '#ea580c',
  '高度脆弱': '#dc2626',
};

/* Local UI helpers replacing antd components */
const Card: React.FC<{ title?: React.ReactNode; style?: React.CSSProperties; children: React.ReactNode }> = ({ title, style, children }) => (
  <div style={{ background: '#1f2937', borderRadius: 10, border: '1px solid #374151', overflow: 'hidden', ...style }}>
    {title && (
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #374151', fontWeight: 600, color: '#f3f4f6', fontSize: 15 }}>
        {title}
      </div>
    )}
    <div style={{ padding: 16 }}>{children}</div>
  </div>
);

const DescItem: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div>
    <div style={{ color: '#9ca3af', fontSize: 12, marginBottom: 4 }}>{label}</div>
    <div style={{ color: '#f3f4f6', fontSize: 14 }}>{children}</div>
  </div>
);

const StockAnalysis: React.FC = () => {
  const [stockCode, setStockCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [basicInfo, setBasicInfo] = useState<StockBasicInfo | null>(null);
  const [financials, setFinancials] = useState<StockFinancials | null>(null);
  const [dcf, setDcf] = useState<DCFValuation | null>(null);
  const [fragility, setFragility] = useState<FragilityResult | null>(null);
  const [notice, setNotice] = useState<{ type: 'warning' | 'error'; text: string } | null>(null);

  const showMessage = (type: 'warning' | 'error', text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 3000);
  };

  const handleSearch = async () => {
    if (!stockCode) {
      showMessage('warning', '请输入股票代码');
      return;
    }

    setLoading(true);
    setFragility(null);
    try {
      const [basicRes, finRes] = await Promise.all([
        stockApi.getBasicInfo(stockCode),
        stockApi.getFinancials(stockCode),
      ]);

      setBasicInfo(basicRes.data);
      setFinancials(finRes.data);

      // DCF暂不可用，静默处理
      try {
        const dcfRes = await valuationApi.calculateDCF(stockCode);
        setDcf(dcfRes.data);
      } catch {
        setDcf(null);
      }

      // 脆弱性分析
      try {
        const fragRes = await fetch(`/api/stocks/${stockCode}/fragility`);
        if (fragRes.ok) {
          setFragility(await fragRes.json());
        }
      } catch {
        setFragility(null);
      }
    } catch (error) {
      showMessage('error', '查询失败，请检查股票代码');
    } finally {
      setLoading(false);
    }
  };

  const fragilityRadarOption = useMemo(() => {
    if (!fragility) return {};
    const dims = fragility.dimensions;
    return {
      tooltip: {},
      radar: {
        indicator: dims.map(d => ({ name: d.name, max: d.max })),
        shape: 'polygon',
        splitArea: { areaStyle: { color: ['rgba(59,130,246,0.05)', 'rgba(59,130,246,0.1)'] } },
        axisLine: { lineStyle: { color: '#374151' } },
        splitLine: { lineStyle: { color: '#374151' } },
        axisName: { color: '#9ca3af', fontSize: 11 },
      },
      series: [{
        type: 'radar',
        data: [{
          value: dims.map(d => d.score),
          name: fragility.verdict,
          areaStyle: { color: `${fragility.color}33` },
          lineStyle: { color: fragility.color, width: 2 },
          itemStyle: { color: fragility.color },
        }],
      }],
      backgroundColor: 'transparent',
    };
  }, [fragility]);

  const getFCFChartOption = () => {
    if (!dcf) return {};

    const years = Array.from({ length: 10 }, (_, i) => `第${i + 1}年`);
    return {
      title: { text: '自由现金流预测 (亿元)' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: years },
      yAxis: { type: 'value' },
      series: [
        {
          name: 'FCF',
          type: 'bar',
          data: dcf.fcf_projections,
          itemStyle: { color: '#1890ff' },
        },
      ],
    };
  };

  return (
    <div style={{ padding: '24px' }}>
      {/* Notice banner */}
      {notice && (
        <div style={{
          padding: '10px 16px', marginBottom: 16, borderRadius: 8,
          background: notice.type === 'error' ? '#7f1d1d' : '#78350f',
          color: notice.type === 'error' ? '#fca5a5' : '#fcd34d',
          fontSize: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 18, lineHeight: 1 }}>&times;</button>
        </div>
      )}

      <Card title="投资分析工具">
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            placeholder="输入股票代码，如：600519"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            style={{
              flex: 1, padding: '12px 16px', fontSize: 16,
              background: '#111827', border: '1px solid #374151', borderRadius: 8,
              color: '#f3f4f6', outline: 'none',
            }}
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            style={{
              padding: '12px 24px', fontSize: 16,
              background: '#3b82f6', border: 'none', borderRadius: 8,
              color: '#fff', cursor: loading ? 'wait' : 'pointer', fontWeight: 600,
            }}
          >
            {loading ? '搜索中...' : '搜索'}
          </button>
        </div>
      </Card>

      {/* Loading indicator */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60, color: '#9ca3af' }}>
          <div style={{ fontSize: 18, marginBottom: 8 }}>正在分析...</div>
        </div>
      )}

      {/* Results */}
      {!loading && basicInfo && (
        <Card title="基本面指标" style={{ marginTop: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px 24px' }}>
            <DescItem label="股票代码">{basicInfo.code}</DescItem>
            <DescItem label="股票名称">{basicInfo.name}</DescItem>
            <DescItem label="总市值">{basicInfo.market_cap}亿</DescItem>
            <DescItem label="PE (市盈率)">{basicInfo.pe}</DescItem>
            <DescItem label="PB (市净率)">{basicInfo.pb}</DescItem>
            <DescItem label="ROE (%)">{basicInfo.roe}%</DescItem>
            <DescItem label="PEG">
              {(() => {
                const pe = basicInfo.pe;
                const growth = financials?.profit_growth;
                if (pe && growth && growth > 0) {
                  const peg = (pe / growth).toFixed(2);
                  const color = parseFloat(peg) < 1 ? '#52c41a' : parseFloat(peg) <= 2 ? '#1890ff' : '#ff4d4f';
                  return <span style={{ color, fontWeight: 600 }}>{peg}</span>;
                }
                return '--';
              })()}
            </DescItem>
          </div>
        </Card>
      )}

      {!loading && financials && (
        <Card title="财务数据" style={{ marginTop: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px 24px' }}>
            <DescItem label="营业收入">{financials.revenue}亿</DescItem>
            <DescItem label="净利润">{financials.net_profit}亿</DescItem>
            <DescItem label="自由现金流">{financials.fcf}亿</DescItem>
            <DescItem label="营收同比增长">{financials.revenue_growth}%</DescItem>
            <DescItem label="净利润同比增长">{financials.profit_growth}%</DescItem>
          </div>
        </Card>
      )}

      {!loading && fragility && (
        <Card
          title={
            <span>
              商业模式脆弱性分析
              <span style={{
                display: 'inline-block', padding: '2px 10px', borderRadius: 4,
                fontSize: 13, fontWeight: 600, marginLeft: 12,
                background: `${fragility.color}20`, color: fragility.color,
              }}>
                {fragility.verdict} {fragility.total_score}分
              </span>
            </span>
          }
          style={{ marginTop: 16 }}
        >
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <div style={{ flex: '0 0 320px' }}>
              <ReactECharts option={fragilityRadarOption} style={{ height: 300 }} />
            </div>
            <div style={{ flex: 1, minWidth: 300 }}>
              <div style={{ marginBottom: 16, padding: 12, background: `${fragility.color}15`, borderRadius: 8, border: `1px solid ${fragility.color}40` }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: fragility.color }}>{fragility.verdict}</div>
                <div style={{ fontSize: 13, color: '#d1d5db', marginTop: 4 }}>{fragility.verdict_desc}</div>
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>报告期: {fragility.report_period}</div>
              </div>
              {fragility.dimensions.map((d, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid #1f2937' }}>
                  <div style={{ width: 80, fontSize: 13, color: '#9ca3af' }}>{d.name}</div>
                  <div style={{ flex: 1, height: 6, background: '#1f2937', borderRadius: 3 }}>
                    <div style={{ height: '100%', width: `${(d.score / d.max) * 100}%`, background: d.score / d.max >= 0.6 ? '#16a34a' : d.score / d.max >= 0.4 ? '#ca8a04' : '#dc2626', borderRadius: 3 }} />
                  </div>
                  <div style={{ width: 50, fontSize: 13, color: '#f3f4f6', textAlign: 'right' }}>{d.score}/{d.max}</div>
                  <div style={{ width: 60, fontSize: 11, color: '#6b7280' }}>{d.value}</div>
                </div>
              ))}
              {fragility.warnings.length > 0 && (
                <div style={{ marginTop: 12, padding: 10, background: '#7f1d1d20', borderRadius: 6, border: '1px solid #7f1d1d40' }}>
                  <div style={{ fontSize: 12, color: '#fca5a5', fontWeight: 600, marginBottom: 6 }}>薄弱环节</div>
                  {fragility.warnings.map((w, i) => (
                    <div key={i} style={{ fontSize: 12, color: '#fca5a5', padding: '2px 0' }}>{w.name}: {w.signal}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {!loading && dcf && (
        <>
          <Card title="DCF估值分析" style={{ marginTop: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px 24px' }}>
              <DescItem label="当前股价">{dcf.current_price}元</DescItem>
              <DescItem label="内在价值">{dcf.intrinsic_value}元</DescItem>
              <DescItem label="买点价格">{dcf.buy_price}元</DescItem>
              <DescItem label="安全边际">{(dcf.safety_margin * 100).toFixed(0)}%</DescItem>
              <DescItem label="折现率">{(dcf.discount_rate * 100).toFixed(0)}%</DescItem>
              <DescItem label="增长率">{(dcf.growth_rate * 100).toFixed(1)}%</DescItem>
              <DescItem label="上行空间">
                <span style={{ color: dcf.upside > 0 ? '#52c41a' : '#ff4d4f' }}>
                  {dcf.upside > 0 ? '+' : ''}{dcf.upside}%
                </span>
              </DescItem>
            </div>
          </Card>

          <Card title="现金流预测" style={{ marginTop: 16 }}>
            <ReactECharts option={getFCFChartOption()} style={{ height: 400 }} />
          </Card>
        </>
      )}
    </div>
  );
};

export default StockAnalysis;
