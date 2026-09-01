import { useState, useEffect, memo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Menu, Layout } from 'antd'
import {
  LineChartOutlined,
  SearchOutlined,
  StockOutlined,
  FundOutlined,
  GlobalOutlined,
  ToolOutlined,
  DashboardOutlined,
  BarChartOutlined,
  RiseOutlined,
  FallOutlined,
  PieChartOutlined,
  AreaChartOutlined,
  SwapOutlined,
  BankOutlined,
  SafetyOutlined,
  ExperimentOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  ReconciliationOutlined,
  RetweetOutlined,
  HeatMapOutlined,
  MonitorOutlined,
  CrownOutlined,
  AlertOutlined,
  SettingOutlined,
  LinkOutlined,
  FireOutlined,
  GiftOutlined,
  ReadOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'

const { Sider } = Layout

type MenuItem = Required<MenuProps>['items'][number]

interface AppSidebarProps {
  collapsed: boolean
  onCollapse: (collapsed: boolean) => void
}

// 菜单 key → URL 路径 映射
const keyToPath: Record<string, string> = {
  stock: '/stock',
  indexVal: '/index-valuation',
  indexEarnings: '/index-earnings',
  macro: '/macro',
  futures: '/futures',
  dividend: '/dividend',
  cigarButt: '/cigar-butt',
  valueInvesting: '/value-investing',
  reit: '/reit',
  tTrading: '/t-trading',
  tTradingRealtime: '/t-trading-realtime',
  gridTrading: '/grid-trading',
  rightSide: '/right-side',
  futuOptionChain: '/futu-options',
  option: '/option-calculator',
  fundArb: '/fund-arb',
  cb: '/cb',
  cbNearMature: '/cb-near-mature',
  cbStrategies: '/cb-strategies',
  cbBacktest: '/cb-backtest',
  masterStrategy: '/master-strategy',
  polymarket: '/polymarket',
  hki: '/hki',
  cryptoMaster: '/crypto',
  airdropScanner: '/airdrop-scanner',
  nationalTeam: '/national-team',
  decisionGuard: '/decision-guard',
  prefrontalTraining: '/prefrontal-training',
  portfolio: '/portfolio',
  relativeValuation: '/relative-valuation',
  mobileSettings: '/settings',
}

// URL 路径 → 菜单 key 反向映射
const pathToKey: Record<string, string> = {}
for (const [key, path] of Object.entries(keyToPath)) {
  pathToKey[path] = key
}

function getItem(
  label: React.ReactNode,
  key: string,
  icon?: React.ReactNode,
  children?: MenuItem[]
): MenuItem {
  return { key, icon, children, label } as MenuItem
}

const menuItems: MenuItem[] = [
  getItem('行情总览', 'market', <LineChartOutlined />, [
    getItem('我的持仓', 'portfolio', <PieChartOutlined />),
    getItem('我的自选', 'stock', <DashboardOutlined />),
    getItem('指数估值', 'indexVal', <BarChartOutlined />),
    getItem('指数盈利估值', 'indexEarnings', <FundOutlined />),
    getItem('相对估值', 'relativeValuation', <PieChartOutlined />),
    getItem('宏观数据', 'macro', <AreaChartOutlined />),
    getItem('期货洞察', 'futures', <ExperimentOutlined />),
  ]),
  getItem('选股工具', 'screening', <SearchOutlined />, [
    getItem('攒股收息', 'dividend', <FundOutlined />),
    getItem('捡烟蒂', 'cigarButt', <FallOutlined />),
    getItem('价投筛选', 'valueInvesting', <RiseOutlined />),
    getItem('REIT筛选', 'reit', <BankOutlined />),
  ]),
  getItem('交易系统', 'trading', <StockOutlined />, [
    getItem('做T系统', 'tTrading', <SwapOutlined />),
    getItem('实时做T(腾讯)', 'tTradingRealtime', <AlertOutlined />),
    getItem('网格交易', 'gridTrading', <HeatMapOutlined />),
    getItem('右侧交易', 'rightSide', <RocketOutlined />),
    getItem('期权轮动(实战)', 'futuOptionChain', <PieChartOutlined />),
    getItem('期权计算', 'option', <ReconciliationOutlined />),
  ]),
  getItem('套利', 'arb', <RetweetOutlined />, [
    getItem('港股打新', 'hki', <RocketOutlined />),
    getItem('基金套利', 'fundArb', <SwapOutlined />),
  ]),
  getItem('基金与债券', 'funds', <FundOutlined />, [
    getItem('可转债', 'cb', <StockOutlined />),
    getItem('临期债筛选', 'cbNearMature', <SafetyOutlined />),
    getItem('八大战法', 'cbStrategies', <ReadOutlined />),
    getItem('大师策略', 'masterStrategy', <CrownOutlined />),
    getItem('转债回测', 'cbBacktest', <MonitorOutlined />),
  ]),
  getItem('另类投资', 'alternative', <GlobalOutlined />, [
    getItem('Polymarket', 'polymarket', <GlobalOutlined />),
    getItem('币圈大师', 'cryptoMaster', <FireOutlined />),
    getItem('空投扫描器', 'airdropScanner', <GiftOutlined />),
  ]),
  getItem('辅助工具', 'tools', <ToolOutlined />, [
    getItem('国家队监控', 'nationalTeam', <SafetyOutlined />),
    getItem('决策卫士', 'decisionGuard', <SafetyCertificateOutlined />),
    getItem('前额叶练习', 'prefrontalTraining', <ExperimentOutlined />),
    getItem('APP设置', 'mobileSettings', <SettingOutlined />),
  ]),
  getItem('量化工具', 'recommend', <LinkOutlined />, [
    getItem(
      <span>QuantDinger <span style={{ fontSize: 10, color: '#8b949e' }}>AI量化平台</span></span>,
      'ext_quantdinger',
      <RocketOutlined />,
    ),
  ]),
]

// 根据 activeKey 找到所属的父级 key
function findParentKey(items: MenuItem[], targetKey: string): string | null {
  for (const item of items) {
    if (item && 'children' in item && item.children) {
      for (const child of item.children) {
        if (child && 'key' in child && child.key === targetKey) {
          return item.key as string
        }
      }
    }
  }
  return null
}

// 从当前 pathname 推导出菜单 activeKey
function deriveActiveKey(pathname: string): string {
  // 精确匹配
  if (pathToKey[pathname]) return pathToKey[pathname]
  // 前缀匹配（如 /stock/600519 → stock）
  if (pathname.startsWith('/stock')) return 'stock'
  // 默认
  return 'indexVal'
}

const AppSidebar = memo(function AppSidebar({ collapsed, onCollapse }: AppSidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const activeKey = deriveActiveKey(location.pathname)
  const parentKey = findParentKey(menuItems, activeKey)
  const [openKeys, setOpenKeys] = useState<string[]>(parentKey ? [parentKey] : ['market'])

  // 当 activeKey 变化时，自动展开对应的子菜单
  useEffect(() => {
    const pk = findParentKey(menuItems, activeKey)
    if (pk && !openKeys.includes(pk)) {
      setOpenKeys([pk])
    }
  }, [activeKey])

  const handleOpenChange = (keys: string[]) => {
    const latestOpenKey = keys.find(key => openKeys.indexOf(key) === -1)
    const rootSubmenuKeys = ['market', 'screening', 'trading', 'arb', 'funds', 'alternative', 'tools', 'recommend']
    if (latestOpenKey && rootSubmenuKeys.indexOf(latestOpenKey) === -1) {
      setOpenKeys(keys)
    } else {
      setOpenKeys(latestOpenKey ? [latestOpenKey] : [])
    }
  }

  // 外部链接映射
  const externalLinks: Record<string, string> = {
    ext_quantdinger: 'http://localhost:8888',
  }

  const handleClick: MenuProps['onClick'] = ({ key }) => {
    // 外部链接：新窗口打开
    if (externalLinks[key]) {
      window.open(externalLinks[key], '_blank', 'noopener,noreferrer')
      return
    }
    // 忽略分组的点击
    if (['market', 'screening', 'trading', 'arb', 'funds', 'alternative', 'tools', 'recommend'].includes(key)) return
    // 导航到对应路径
    const path = keyToPath[key]
    if (path) {
      navigate(path)
    }
  }

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      onCollapse={onCollapse}
      width={220}
      collapsedWidth={60}
      style={{
        background: '#161b22',
        borderRight: '1px solid #30363d',
        height: '100%',
        overflow: 'auto',
      }}
      trigger={null}
    >
      <div style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* 折叠按钮 */}
        <div
          onClick={() => onCollapse(!collapsed)}
          style={{
            padding: collapsed ? '16px 0' : '16px 18px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: 8,
            borderBottom: '1px solid #30363d',
            color: '#8b949e',
            fontSize: 13,
            transition: 'all 0.3s',
          }}
        >
          <span style={{ fontSize: 18, lineHeight: 1 }}>☰</span>
          {!collapsed && <span style={{ whiteSpace: 'nowrap' }}>导航菜单</span>}
        </div>

        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[activeKey]}
          openKeys={collapsed ? [] : openKeys}
          onOpenChange={handleOpenChange}
          onClick={handleClick}
          items={menuItems}
          style={{
            background: 'transparent',
            borderRight: 'none',
            flex: 1,
            fontSize: 13,
          }}
        />
      </div>
    </Sider>
  )
})

export default AppSidebar
