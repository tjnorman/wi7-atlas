// WI-7 Atlas: optional real-time aircraft proxy (Cloudflare Worker).
//
// Flight trackers send no CORS headers, so a web page cannot ask them directly. This Worker asks
// one fixed question on the page's behalf (aircraft near the district) and returns the answer
// with the header the browser needs. It accepts no address or coordinates from the caller, so it
// cannot be used as an open relay.
//
// Adapted from proxy/worker.js in Normansrule/global-intelligence-atlas, reused with the author's
// permission (see NOTICE.md).
//
// The defaults below can be overridden with variables of the same names (wrangler.toml or the dashboard).

const SOURCES = [
  ['adsb.lol', (la, lo, nm) => `https://api.adsb.lol/v2/lat/${la}/lon/${lo}/dist/${nm}`, 'Open Database License 1.0', 'https://www.adsb.lol/'],
  ['adsb.fi', (la, lo, nm) => `https://opendata.adsb.fi/api/v2/lat/${la}/lon/${lo}/dist/${nm}`, 'adsb.fi open data terms', 'https://adsb.fi/'],
  ['airplanes.live', (la, lo, nm) => `https://api.airplanes.live/v2/point/${la}/${lo}/${nm}`, 'airplanes.live terms, non-commercial use', 'https://airplanes.live/'],
];
const DEFAULTS = { ALLOWED_ORIGINS: 'https://tjnorman.github.io', LAT: '45.4344', LON: '-90.4727', NM: '143' };
const TTL = 10; // seconds; every visitor in that window shares one upstream request

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get('Origin') || '';
    const allowed = (env.ALLOWED_ORIGINS || DEFAULTS.ALLOWED_ORIGINS).split(',').map((s) => s.trim()).filter(Boolean);
    const cors = { 'Access-Control-Allow-Origin': allowed.includes(origin) ? origin : allowed[0] || 'null', Vary: 'Origin' };
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: { ...cors, 'Access-Control-Allow-Methods': 'GET' } });
    const url = new URL(request.url);
    if (request.method !== 'GET' || url.pathname !== '/aircraft') return json({ ok: false, error: 'not found' }, 404, cors);
    if (origin && !allowed.includes(origin)) return json({ ok: false, error: 'origin not allowed' }, 403, cors);

    const cache = caches.default;
    const key = new Request(`${url.origin}/aircraft`);
    let hit = await cache.match(key);
    if (!hit) {
      hit = await ask(env);
      ctx.waitUntil(cache.put(key, hit.clone()));
    }
    const out = new Response(hit.body, hit);
    for (const [k, v] of Object.entries(cors)) out.headers.set(k, v);
    return out;
  },
};

async function ask(env) {
  const la = Number(env.LAT || DEFAULTS.LAT), lo = Number(env.LON || DEFAULTS.LON), nm = Math.min(250, Number(env.NM || DEFAULTS.NM));
  const errors = [];
  for (const [name, build, licence, home] of SOURCES) {
    try {
      const r = await fetch(build(la, lo, nm), { headers: { 'User-Agent': 'wi7-atlas proxy (+https://github.com/tjnorman/wi7-atlas)' }, signal: AbortSignal.timeout(12000) });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      return json({ ok: true, generated_at: new Date().toISOString(), source: name, source_url: home, licence, ac: data.ac || [], errors }, 200, { 'Cache-Control': `public, max-age=${TTL}` });
    } catch (e) {
      errors.push(`${name}: ${e.message}`);
    }
  }
  return json({ ok: false, generated_at: new Date().toISOString(), ac: [], errors }, 502, { 'Cache-Control': 'public, max-age=5' });
}

function json(body, status, headers) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}
