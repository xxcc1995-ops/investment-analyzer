import React, { useState } from 'react';
import { Card, Input, Button, Descriptions, Spin, message } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { stockApi, valuationApi, StockBasicInfo, StockFinancials, DCFValuation } from '../services/api';

const StockAnalysis: React.FC = () => {
  const [stockCode, setStockCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [basicInfo, setBasicInfo] = useState<StockBasicInfo | null>(null);
  const [financials, setFinancials] = useState<StockFinancials | null>(null);
  const [dcf, setDcf] = useState<DCFValuation | null>(null);

  const handleSearch = async () => {
    if (!stockCode) {
      message.warning('请输入股票代码');
      return;
    }

    setLoading(true);
    try {
      const [basicRes, finRes, dcfRes] = await Promise.all([
        stockApi.getBasicInfo(stockCode),
        stockApi.getFinancials(stockCode),
        valuationApi.calculateDCF(stockCode),
      ]);

      setBasicInfo(basicRes.data);
      setFinancials(finRes.data);
      setDcf(dcfRes.data);
    } catch (error) {
      message.error('查询失败，请检查股票代码');
    } finally {
      setLoading(false);
    }
  };

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
