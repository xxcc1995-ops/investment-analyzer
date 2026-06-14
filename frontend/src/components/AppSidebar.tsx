import { useState, useEffect } from 'react'
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

  TrophyOutlined,
  SafetyOutlined,
  TeamOutlined,
  BulbOutlined,
  ExperimentOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  ReconciliationOutlined,
  HeatMapOutlined,
  MonitorOutlined,
  CrownOutlined,
  AlertOutlined,
  SettingOutlined,
  LinkOutlined,
  FireOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'

const { Sider } = Layout

type MenuItem = Required<MenuProps>['items'][number]

interface AppSidebarProps {
  activeKey: string
  onNavigate: (key: string) => void
  collapsed: boolean
  onCollapse: (collapsed: boolean) => void
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
    getItem('每日资讯', 'dailyInfo', <DashboardOutlined />),
    getItem('我的自选', 'stock', <DashboardOutlined />),
    getItem('指数估值', 'indexVal', <BarChartOutlined />),

    getItem('宏观数据', 'macro', <AreaChartOutlined />),
    getItem('期货洞察', 'futures', <ExperimentOutlined />),
  ]),
  getItem('选股工具', 'screening', <SearchOutlined />, [
    getItem('攒股收息', 'dividend', <FundOutlined />),
    getItem('捡烟蒂', 'cigarButt', <FallOutlined />),
    getItem('价投筛选', 'valueInvesting', <RiseOutlined />),
    getItem('REIT筛选', 'reit', <BankOutlined />),
    getItem('出口冠军', 'exportChampions', <TrophyOutlined />),
    getItem('机哥体系', 'jcScreener', <BulbOutlined />),
  ]),
  getItem('交易系统', 'trading', <StockOutlined />, [
    getItem('做T系统', 'tTrading', <SwapOutlined />),
    getItem('网格交易', 'gridTrading', <HeatMapOutlined />),
    getItem('右侧交易', 'rightSide', <RocketOutlined />),
    getItem('期权轮动(实战)', 'futuOptionChain', <PieChartOutlined />),
    getItem('期权计算', 'option', <ReconciliationOutlined />),
    getItem('策略回测', 'backtestReport', <MonitorOutlined />),
    getItem('回撤控制', 'drawdownControl', <AlertOutlined />),
  ]),
  getItem('基金与债券', 'funds', <FundOutlined />, [
    getItem('基金套利', 'fundArb', <SwapOutlined />),
    getItem('拖拉机套利', 'tractorTrading', <SwapOutlined />),
    getItem('可转债', 'cb', <StockOutlined />),
    getItem('大师策略', 'masterStrategy', <CrownOutlined />),
    getItem('转债回测', 'cbBacktest', <MonitorOutlined />),
  ]),
  getItem('另类投资', 'alternative', <GlobalOutlined />, [
    getItem('Polymarket', 'polymarket', <GlobalOutlined />),
    getItem('港股打新', 'hki', <RocketOutlined />),
    getItem('币圈大师', 'cryptoMaster', <FireOutlined />),
  ]),
  getItem('辅助工具', 'tools', <ToolOutlined />, [
    getItem('国家队监控', 'nationalTeam', <SafetyOutlined />),

    getItem('决策卫士', 'decisionGuard', <SafetyCertificateOutlined />),
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

export default function AppSidebar({ activeKey, onNavigate, collapsed, onCollapse }: AppSidebarProps) {
  const parentKey = findParentKey(menuItems, activeKey)
  const [openKeys, setOpenKeys] = useState<string[]>(parentKey ? [parentKey] : ['market'])

  // 当activeKey变化时，自动展开对应的子菜单
  useEffect(() => {
    const pk = findParentKey(menuItems, activeKey)
    if (pk && !openKeys.includes(pk)) {
      setOpenKeys([pk])
    }
  }, [activeKey])

  const handleOpenChange = (keys: string[]) => {
    // 只展开最后一个打开的子菜单
    const latestOpenKey = keys.find(key => openKeys.indexOf(key) === -1)
    const rootSubmenuKeys = ['market', 'screening', 'trading', 'funds', 'alternative', 'tools', 'recommend']
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
    if (['market', 'screening', 'trading', 'funds', 'alternative', 'tools', 'recommend'].includes(key)) return
    onNavigate(key)
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
}
