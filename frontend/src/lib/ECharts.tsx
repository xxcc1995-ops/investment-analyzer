import ReactEChartsCore from 'echarts-for-react/lib/core'
import type { EChartsReactProps } from 'echarts-for-react/lib/types'
import echarts from './echartsCore'

export default function ECharts(props: EChartsReactProps) {
  return <ReactEChartsCore echarts={echarts} {...props} />
}
