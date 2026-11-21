// Number and date formatting, written once so every section reads the same way.

const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const int = (n) => (n == null || Number.isNaN(n) ? "n/a" : nf0.format(n));
export const one = (n) => (n == null || Number.isNaN(n) ? "n/a" : nf1.format(n));
export const pct = (n, d = 1) => (n == null || Number.isNaN(n) ? "n/a" : `${n.toFixed(d)}%`);
export const signedPct = (n, d = 1) => (n == null ? "n/a" : `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(d)}%`);
export const signedInt = (n) => (n == null ? "n/a" : `${n > 0 ? "+" : n < 0 ? "−" : ""}${nf0.format(Math.abs(n))}`);

export function usd(n, { compact = false } = {}) {
  if (n == null || Number.isNaN(n)) return "n/a";
  const a = Math.abs(n);
  if (compact || a >= 1e6) {
    if (a >= 1e9) return `$${(n / 1e9).toFixed(a >= 1e10 ? 1 : 2)} billion`;
    if (a >= 1e6) return `$${(n / 1e6).toFixed(1)} million`;
    if (a >= 1e3 && compact) return `$${Math.round(n / 1e3)}k`;
  }
  return `$${nf0.format(n)}`;
}

export function usdShort(n) {
  if (n == null) return "n/a";
  const a = Math.abs(n);
  if (a >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  if (a >= 1e3) return `$${(n / 1e3).toFixed(0)}k`;
  return `$${nf0.format(n)}`;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export function monthLabel(ym) {
  if (!ym) return "n/a";
  const [y, m] = ym.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

export function longDate(iso) {
  if (!iso) return "n/a";
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "America/Chicago" });
}

export function value(v, unit) {
  if (unit === "usd") return usd(v);
  if (unit === "pct") return pct(v);
  if (unit === "count") return int(v);
  if (unit === "minutes") return `${one(v)} min`;
  return one(v);
}

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
