declare global {
  interface Window {
    Telegram?: {
      WebApp: any;
    };
  }
}

export const getTelegramWebApp = () => {
  if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp) {
    return window.Telegram.WebApp;
  }
  return null;
};

export const getTelegramInitData = (): string => {
  const tg = getTelegramWebApp();
  if (tg && tg.initData) {
    return tg.initData;
  }
  // Public browser visitors can browse, but private actions require Telegram authentication.
  return '';
};

export const initTelegramApp = () => {
  const tg = getTelegramWebApp();
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) {
        tg.setHeaderColor('#f7f8f4');
      }
      if (tg.setBackgroundColor) {
        tg.setBackgroundColor('#f7f8f4');
      }
    } catch (e) {
      console.warn('Telegram WebApp init warning:', e);
    }
  }
};

export const haptic = {
  impact: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft' = 'light') => {
    const tg = getTelegramWebApp();
    try {
      tg?.HapticFeedback?.impactOccurred(style);
    } catch (e) {}
  },
  notification: (type: 'error' | 'success' | 'warning' = 'success') => {
    const tg = getTelegramWebApp();
    try {
      tg?.HapticFeedback?.notificationOccurred(type);
    } catch (e) {}
  },
  selection: () => {
    const tg = getTelegramWebApp();
    try {
      tg?.HapticFeedback?.selectionChanged();
    } catch (e) {}
  },
};

export const setBackButton = (visible: boolean, onClick?: () => void) => {
  const tg = getTelegramWebApp();
  if (!tg?.BackButton) return;

  if (visible) {
    tg.BackButton.show();
    if (onClick) {
      tg.BackButton.onClick(onClick);
    }
  } else {
    if (onClick) tg.BackButton.offClick?.(onClick);
    tg.BackButton.hide();
  }
};

export const openTelegramLink = (url: string) => {
  const tg = getTelegramWebApp();
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(url);
  } else {
    window.open(url, '_blank');
  }
};
