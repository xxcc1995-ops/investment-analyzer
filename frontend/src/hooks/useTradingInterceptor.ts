import { useState, useCallback, useRef } from 'react';
import RationalCheckpoint from '../components/RationalCheckpoint';

// ============================================================
// 交易拦截 Hook
//
// 用法：
//   const { intercept, checkpointOpen, checkpointMeta, handlePass, handleCancel } = useTradingInterceptor();
//
//   // 包装交易动作
//   const handleTrade = () => {
//     intercept(() => {
//       executeTrade();
//     }, { actionType: 'buy', target: '贵州茅台' });
//   };
//
//   // 在 JSX 中渲染弹窗
//   return (
//     <>
//       <button onClick={handleTrade}>执行交易</button>
//       <RationalCheckpoint open={checkpointOpen} {...checkpointMeta} onPass={handlePass} onCancel={handleCancel} />
//     </>
//   );
// ============================================================

type ActionType = 'buy' | 'sell' | 'adjust' | 'analyze';

interface InterceptorMeta {
  actionType: ActionType;
  target: string;
}

interface UseTradingInterceptorReturn {
  /** 包装一个交易动作，在执行前插入理性检查点 */
  intercept: (action: () => void, meta: InterceptorMeta) => void;
  /** 检查点是否打开 */
  checkpointOpen: boolean;
  /** 检查点元数据 */
  checkpointMeta: InterceptorMeta;
  /** 通过检查点 */
  handlePass: () => void;
  /** 取消操作 */
  handleCancel: () => void;
}

export function useTradingInterceptor(): UseTradingInterceptorReturn {
  const [open, setOpen] = useState(false);
  const [meta, setMeta] = useState<InterceptorMeta>({ actionType: 'buy', target: '' });
  // 使用ref存储pending action，避免stale closure问题
  const pendingActionRef = useRef<(() => void) | null>(null);

  const intercept = useCallback((action: () => void, actionMeta: InterceptorMeta) => {
    pendingActionRef.current = action;
    setMeta(actionMeta);
    setOpen(true);
  }, []);

  const handlePass = useCallback(() => {
    setOpen(false);
    setTimeout(() => {
      pendingActionRef.current?.();
      pendingActionRef.current = null;
    }, 100);
  }, []);

  const handleCancel = useCallback(() => {
    setOpen(false);
    pendingActionRef.current = null;
  }, []);

  return { intercept, checkpointOpen: open, checkpointMeta: meta, handlePass, handleCancel };
}
