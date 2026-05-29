// @ts-nocheck
import React, { useState, useMemo } from 'react';
import { Card, Input, Button, Descriptions, Spin, message, Tag } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
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

const StockAnalysis: React.FC = () => {
  const [stockCode, setStockCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [basicInfo, setBasicInfo] = useState<StockBasicInfo | null>(null);
  const [financials, setFinancials] = useState<StockFinancials | null>(null);
  const [dcf, setDcf] = useState<DCFValuation | null>(null);
  const [fragility, setFragility] = useState<FragilityResult | null>(null);

  const handleSearch = async () => {
    if (!stockCode) {
      message.warning('请输入股票代码');
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
      message.error('查询失败，请检查股票代码');
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
      <Card title="投资分析工具">
        <Input.Search
          placeholder="输入股票代码，如：600519"
          enterButton={<SearchOutlined />}
          size="large"
          value={stockCode}
          onChange={(e) => setStockCode(e.target.value)}
          onSearch={handleSearch}
          loading={loading}
        />
      </Card>

      <Spin spinning={loading}>
        {basicInfo && (
          <Card title="基本面指标" style={{ marginTop: 16 }}>
            <Descriptions column={3}>
              <Descriptions.Item label="股票代码">{basicInfo.code}</Descriptions.Item>
              <Descriptions.Item label="股票名称">{basicInfo.name}</Descriptions.Item>
              <Descriptions.Item label="总市值">{basicInfo.market_cap}亿</Descriptions.Item>
              <Descriptions.Item label="PE (市盈率)">{basicInfo.pe}</Descriptions.Item>
              <Descriptions.Item label="PB (市净率)">{basicInfo.pb}</Descriptions.Item>
              <Descriptions.Item label="ROE (%)">{basicInfo.roe}%</Descriptions.Item>
              {(() => {
                const pe = basicInfo.pe;
                const growth = financials?.profit_growth;
                if (pe && growth && growth > 0) {
                  const peg = (pe / growth).toFixed(2);
                  const color = parseFloat(peg) < 1 ? '#52c41a' : parseFloat(peg) <= 2 ? '#1890ff' : '#ff4d4f';
                  return <Descriptions.Item label="PEG"><span style={{ color, fontWeight: 600 }}>{peg}</span></Descriptions.Item>;
                }
                return <Descriptions.Item label="PEG">--</Descriptions.Item>;
              })()}
            </Descriptions>
          </Card>
        )}

        {financials && (
          <Card title="财务数据" style={{ marginTop: 16 }}>
            <Descriptions column={3}>
              <Descriptions.Item label="营业收入">{financials.revenue}亿</Descriptions.Item>
              <Descriptions.Item label="净利润">{financials.net_profit}亿</Descriptions.Item>
              <Descriptions.Item label="自由现金流">{financials.fcf}亿</Descriptions.Item>
              <Descriptions.Item label="营收同比增长">{financials.revenue_growth}%</Descriptions.Item>
              <Descriptions.Item label="净利润同比增长">{financials.profit_growth}%</Descriptions.Item>
            </Descriptions>
          </Card>
        )}

        {fragility && (
          <Card
            title={
              <span>
                商业模式脆弱性分析
                <Tag color={fragility.color} style={{ marginLeft: 12 }}>
                  {fragility.verdict} {fragility.total_score}分
                </Tag>
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

        {dcf && (
          <>
            <Card title="DCF估值分析" style={{ marginTop: 16 }}>
              <Descriptions column={3}>
                <Descriptions.Item label="当前股价">{dcf.current_price}元</Descriptions.Item>
                <Descriptions.Item label="内在价值">{dcf.intrinsic_value}元</Descriptions.Item>
                <Descriptions.Item label="买点价格">{dcf.buy_price}元</Descriptions.Item>
                <Descriptions.Item label="安全边际">{(dcf.safety_margin * 100).toFixed(0)}%</Descriptions.Item>
                <Descriptions.Item label="折现率">{(dcf.discount_rate * 100).toFixed(0)}%</Descriptions.Item>
                <Descriptions.Item label="增长率">{(dcf.growth_rate * 100).toFixed(1)}%</Descriptions.Item>
                <Descriptions.Item label="上行空间">
                  <span style={{ color: dcf.upside > 0 ? '#52c41a' : '#ff4d4f' }}>
                    {dcf.upside > 0 ? '+' : ''}{dcf.upside}%
                  </span>
                </Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title="现金流预测" style={{ marginTop: 16 }}>
              <ReactECharts option={getFCFChartOption()} style={{ height: 400 }} />
            </Card>
          </>
        )}
      </Spin>
    </div>
  );
};

export default StockAnalysis;
