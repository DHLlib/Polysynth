const ANSI_TO_HEX: Record<string, string> = {
  "[30m": "#000000",
  "[31m": "#AA0000",
  "[32m": "#00AA00",
  "[33m": "#AA5500",
  "[34m": "#0000AA",
  "[35m": "#AA00AA",
  "[36m": "#00AAAA",
  "[37m": "#AAAAAA",
  "[90m": "#555555",
  "[91m": "#FF5555",
  "[92m": "#55FF55",
  "[93m": "#FFFF55",
  "[94m": "#5555FF",
  "[95m": "#FF55FF",
  "[96m": "#55FFFF",
  "[97m": "#FFFFFF",
};

const HEX_TO_ANSI: Record<string, string> = Object.fromEntries(
  Object.entries(ANSI_TO_HEX).map(([ansi, hex]) => [hex.toLowerCase(), ansi])
);

export function ansiToHex(ansi: string | null | undefined): string {
  if (!ansi) return "#888888";
  // 去除可能的重置码后缀
  const clean = ansi.replace(/\[0m$/, "");
  return ANSI_TO_HEX[clean] || "#888888";
}

export function hexToAnsi(hex: string): string {
  const normalized = hex.toLowerCase().trim();
  if (HEX_TO_ANSI[normalized]) return HEX_TO_ANSI[normalized];
  // 找到欧几里得距离最近的 ANSI 颜色
  const target = hexToRgb(normalized);
  if (!target) return "[90m";
  let best = "[90m";
  let bestDist = Infinity;
  for (const [h, ansi] of Object.entries(HEX_TO_ANSI)) {
    const rgb = hexToRgb(h);
    if (!rgb) continue;
    const dist =
      Math.pow(target.r - rgb.r, 2) +
      Math.pow(target.g - rgb.g, 2) +
      Math.pow(target.b - rgb.b, 2);
    if (dist < bestDist) {
      bestDist = dist;
      best = ansi;
    }
  }
  return best;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!m) return null;
  return {
    r: parseInt(m[1], 16),
    g: parseInt(m[2], 16),
    b: parseInt(m[3], 16),
  };
}
