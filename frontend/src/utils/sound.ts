/** 音效和通知工具 — 使用 Web Audio API，无需外部音频文件 */

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext {
  if (!audioCtx) audioCtx = new AudioContext();
  return audioCtx;
}

/** 播放消息到达提示音（柔和的双音调叮咚） */
export function playMessageSound() {
  if (!isSoundEnabled()) return;
  try {
    const ctx = getAudioContext();
    const now = ctx.currentTime;

    // 第一个音 — 高音叮
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.value = 880;
    gain1.gain.setValueAtTime(0.15, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
    osc1.connect(gain1).connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.3);

    // 第二个音 — 稍低的咚
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.value = 660;
    gain2.gain.setValueAtTime(0.12, now + 0.15);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
    osc2.connect(gain2).connect(ctx.destination);
    osc2.start(now + 0.15);
    osc2.stop(now + 0.45);
  } catch {}
}

/** 发送浏览器通知（仅当页面不在前台时） */
export function sendNotification(title: string, body: string) {
  if (!isNotificationEnabled()) return;
  if (document.visibilityState === 'visible') return;
  if (Notification.permission !== 'granted') return;

  new Notification(title, { body, icon: '📖' });
}

/** 请求通知权限 */
export async function requestNotificationPermission(): Promise<boolean> {
  if (!('Notification' in window)) return false;
  if (Notification.permission === 'granted') return true;
  if (Notification.permission === 'denied') return false;
  const result = await Notification.requestPermission();
  return result === 'granted';
}

// ---- localStorage 设置 ----
const SOUND_KEY = 'inkless-sound-enabled';
const NOTIFICATION_KEY = 'inkless-notification-enabled';

export function isSoundEnabled(): boolean {
  return localStorage.getItem(SOUND_KEY) !== 'false';
}

export function setSoundEnabled(v: boolean) {
  localStorage.setItem(SOUND_KEY, String(v));
}

export function isNotificationEnabled(): boolean {
  return localStorage.getItem(NOTIFICATION_KEY) === 'true';
}

export function setNotificationEnabled(v: boolean) {
  localStorage.setItem(NOTIFICATION_KEY, String(v));
}
