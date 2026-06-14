import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.xinyuan.invest',
  appName: '新源Invest',
  webDir: 'dist',
  server: {
    // 部署模式：APP打包时指向远程后端
    // 用户需要将后端部署到可访问的服务器，然后修改这里的URL
    url: '',
    // 如果不设置url，则使用本地文件
    cleartext: true,
    allowNavigation: ['*'],
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#0d1117',
      showSpinner: true,
      spinnerColor: '#58a6ff',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#161b22',
    },
    App: {
      // 允许APP内打开外部链接
    },
  },
  android: {
    // 允许混合内容（HTTP/HTTPS）
    allowMixedContent: true,
    // 覆盖用户代理，标识为APP
    overrideUserAgent: 'XinyuanInvest/1.0 Android',
    // 资源路径
    path: 'android',
  },
};

export default config;
