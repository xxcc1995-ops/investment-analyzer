/**
 * Capacitor移动端配置工具
 * 用于APP模式下配置后端API地址
 */
import { Preferences } from '@capacitor/preferences';
import { Capacitor } from '@capacitor/core';

const BACKEND_URL_KEY = 'backend_url';
const DEFAULT_BACKEND_URL = 'http://192.168.1.100:8002'; // 局域网默认地址

/** 判断是否在Capacitor原生环境中运行 */
export function isNativePlatform(): boolean {
  return Capacitor.isNativePlatform();
}

/** 获取后端API基础URL */
export async function getBackendUrl(): Promise<string> {
  // Web模式下使用相对路径（由Vite代理处理）
  if (!isNativePlatform()) {
    return '/api';
  }

  // APP模式下读取用户配置的后端地址
  try {
    const { value } = await Preferences.get({ key: BACKEND_URL_KEY });
    if (value) {
      return `${value}/api`;
    }
  } catch (e) {
    console.warn('读取后端地址配置失败:', e);
  }

  // 返回默认地址
  return `${DEFAULT_BACKEND_URL}/api`;
}

/** 保存后端API地址 */
export async function setBackendUrl(url: string): Promise<void> {
  // 移除末尾斜杠
  const cleanUrl = url.replace(/\/+$/, '');
  await Preferences.set({ key: BACKEND_URL_KEY, value: cleanUrl });
}

/** 获取当前配置的后端地址（不含/api后缀） */
export async function getBackendBaseUrl(): Promise<string> {
  if (!isNativePlatform()) {
    return '';
  }
  try {
    const { value } = await Preferences.get({ key: BACKEND_URL_KEY });
    return value || DEFAULT_BACKEND_URL;
  } catch {
    return DEFAULT_BACKEND_URL;
  }
}

/** 测试后端连接 */
export async function testBackendConnection(url: string): Promise<{ success: boolean; message: string }> {
  try {
    const cleanUrl = url.replace(/\/+$/, '');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(`${cleanUrl}/health`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (response.ok) {
      const data = await response.json();
      return { success: true, message: `连接成功: ${data.status || 'OK'}` };
    }
    return { success: false, message: `服务器返回 ${response.status}` };
  } catch (e: any) {
    if (e.name === 'AbortError') {
      return { success: false, message: '连接超时(5秒)' };
    }
    return { success: false, message: `连接失败: ${e.message}` };
  }
}
