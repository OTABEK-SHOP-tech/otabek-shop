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

export const initTelegramApp = () => {
  const tg = getTelegramWebApp();
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      // Set header color to match Moonlight boutique theme
      if (tg.setHeaderColor) {
        tg.setHeaderColor('#FFF7F9');
      }
      if (tg.setBackgroundColor) {
        tg.setBackgroundColor('#FFF8F5');
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

/**
 * Synthesizes soft, luxurious boutique chimes using Web Audio API (#13).
 * Requires zero external audio files and triggers with zero latency.
 */
export const playBoutiqueSound = (type: 'chime' | 'success' | 'tap' = 'tap') => {
  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const now = ctx.currentTime;

    if (type === 'tap') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, now); // D5
      gain.gain.setValueAtTime(0.04, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
      osc.start(now);
      osc.stop(now + 0.08);
    } else if (type === 'chime') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.exponentialRampToValueAtTime(659.25, now + 0.12); // E5
      gain.gain.setValueAtTime(0.06, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
      osc.start(now);
      osc.stop(now + 0.22);
    } else if (type === 'success') {
      // 3-note harmonic arpeggio
      const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
      notes.forEach((freq, i) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g);
        g.connect(ctx.destination);
        o.type = 'sine';
        o.frequency.setValueAtTime(freq, now + i * 0.07);
        g.gain.setValueAtTime(0.07, now + i * 0.07);
        g.gain.exponentialRampToValueAtTime(0.001, now + i * 0.07 + 0.2);
        o.start(now + i * 0.07);
        o.stop(now + i * 0.07 + 0.2);
      });
    }
  } catch (e) {
    // Audio context not allowed before user gesture or not supported
  }
};

/**
 * TMA 2.0 Add to Home Screen shortcut (#14)
 */
export const addToHomeScreen = () => {
  const tg = getTelegramWebApp();
  if (tg?.addToHomeScreen) {
    tg.addToHomeScreen();
  } else {
    alert("Ilovani ekranga o'rnatish uchun Telegram menyusi (yuqoridagi uch nuqta) orqali 'Asosiy ekranga qo'shish' tugmasini bosing! 📲✨");
  }
};

/**
 * Story-to-Earn share to Telegram Stories (#5)
 */
export const shareToStory = (mediaUrl: string, text: string) => {
  const tg = getTelegramWebApp();
  if (tg?.shareToStory) {
    try {
      tg.shareToStory(mediaUrl, {
        text,
        widget_link: {
          url: "https://t.me/moonlight_chinese_bot",
          name: "Moonlight Chinese Shop"
        }
      });
      return true;
    } catch (e) {
      console.warn("shareToStory error:", e);
    }
  }
  return false;
};

export const openTelegramLink = (url: string) => {
  const tg = getTelegramWebApp();
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(url);
  } else {
    window.open(url, '_blank');
  }
};

export const openLink = (url: string) => {
  const tg = getTelegramWebApp();
  if (tg?.openLink) {
    tg.openLink(url);
  } else {
    window.open(url, '_blank');
  }
};
