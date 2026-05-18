// Reusable countdown timer

export function createCountdown({ seconds, onTick, onDone }) {
  let remaining = seconds;
  let intervalId = null;
  let stopped = false;

  function tick() {
    if (stopped) return;
    remaining -= 1;
    if (remaining <= 0) {
      stop();
      onTick && onTick(0);
      onDone && onDone();
      return;
    }
    onTick && onTick(remaining);
  }

  function start() {
    if (intervalId) return;
    onTick && onTick(remaining);
    intervalId = setInterval(tick, 1000);
  }

  function stop() {
    stopped = true;
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  return { start, stop, get remaining() { return remaining; } };
}

export function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  if (s >= 60) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, '0')}`;
  }
  return String(s).padStart(2, '0');
}
