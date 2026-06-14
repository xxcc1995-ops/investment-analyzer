import { useState, type ReactNode } from 'react'
import { Layout, ConfigProvider, theme } from 'antd'
import AppSidebar from './AppSidebar'
import TopBar from './TopBar'

const { Content } = Layout

interface SearchItem {
  code: string
  name: string
  market?: string
}

interface BondYield {
  yield?: number
  change?: number
  pe?: number
  stock_bond_ratio?: number
}

interface AppShellProps {
  // 搜索
  searchKeyword: string
  onSearchChange: (value: string) => void
  searchResults: SearchItem[]
  showSearch: boolean
  onShowSearch: (show: boolean) => void
  searchLoading: boolean
  onSelectStock: (code: string) => void
  searchBoxRef: React.RefObject<HTMLDivElement>
  // 国债收益率
  bondYields: { cn: BondYield; us: BondYield } | null
  bondLoading: boolean
  onRefreshBonds: () => void
  // 内容
  children: ReactNode
}

// Theme config is static - no need to recreate on every render
const ANTD_THEME = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#58a6ff',
    colorBgContainer: '#161b22',
    colorBgElevated: '#1c2333',
    colorBorder: '#30363d',
    colorText: '#e6edf3',
    colorTextSecondary: '#8b949e',
    colorTextPlaceholder: '#484f58',
    borderRadius: 6,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif",
  },
  components: {
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(88,166,255,0.15)',
      darkItemHoverBg: 'rgba(255,255,255,0.06)',
      itemHeight: 38,
      subMenuItemBg: 'transparent',
    },
    Layout: {
      bodyBg: '#0d1117',
      headerBg: '#161b22',
      siderBg: '#161b22',
      contentBg: '#0d1117',
    },
    Input: {
      colorBgContainer: '#0d1117',
      colorBorder: '#30363d',
      activeBorderColor: '#58a6ff',
      hoverBorderColor: '#484f58',
      colorTextPlaceholder: '#484f58',
    },
    Tooltip: {
      colorBgSpotlight: '#111827',
      colorTextLightSolid: '#d1d5db',
    },
    Table: {
      colorBgContainer: '#161b22',
      headerBg: '#1c2333',
      headerColor: '#8b949e',
      rowHoverBg: 'rgba(88,166,255,0.04)',
      borderColor: '#21262d',
    },
    Card: {
      colorBgContainer: '#161b22',
      colorBorderSecondary: '#30363d',
    },
    Tabs: {
      colorBgContainer: '#161b22',
      inkBarColor: '#58a6ff',
      itemActiveColor: '#58a6ff',
      itemHoverColor: '#e6edf3',
      itemColor: '#8b949e',
    },
    Button: {
      colorBgContainer: '#161b22',
      colorBorder: '#30363d',
    },
    Select: {
      colorBgContainer: '#0d1117',
      colorBorder: '#30363d',
      optionSelectedBg: 'rgba(88,166,255,0.15)',
    },
  },
}

// Static style objects to avoid inline object recreation
const layoutOuterStyle = { height: '100vh', overflow: 'hidden' } as const
const layoutInnerStyle = { height: 'calc(100vh - 56px)' } as const
const contentStyle = { overflow: 'auto', padding: 20, background: '#0d1117' } as const

export default function AppShell({
  searchKeyword,
  onSearchChange,
  searchResults,
  showSearch,
  onShowSearch,
  searchLoading,
  onSelectStock,
  searchBoxRef,
  bondYields,
  bondLoading,
  onRefreshBonds,
  children,
}: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <ConfigProvider theme={ANTD_THEME}>
      <Layout style={layoutOuterStyle}>
        <TopBar
          searchKeyword={searchKeyword}
          onSearchChange={onSearchChange}
          searchResults={searchResults}
          showSearch={showSearch}
          onShowSearch={onShowSearch}
          searchLoading={searchLoading}
          onSelectStock={onSelectStock}
          searchBoxRef={searchBoxRef}
          bondYields={bondYields}
          bondLoading={bondLoading}
          onRefreshBonds={onRefreshBonds}
        />
        <Layout style={layoutInnerStyle}>
          <AppSidebar
            collapsed={collapsed}
            onCollapse={setCollapsed}
          />
          <Content style={contentStyle}>
            {children}
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}
