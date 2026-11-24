// WI-7 Atlas — builds every section of the page from the data files.
import * as F from "./format.js";

const d3 = window.d3;
const topojson = window.topojson;
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const params = new URLSearchParams(location.search);
const FILM = params.has("film");
const BASE = params.get("data") || "data/";
const $ = (s, r = document) => r.querySelector(s);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const FILES = ["summary", "acs", "geography", "pep", "laus", "qcew", "usaspending", "irs", "cameras", "legislators", "elections", "fec", "votes", "integrity", "notes", "manifest"];
const state = { data: {}, counties: [], byFips: new Map(), topo: null, step: "outline" };

async function load() {
  const get = (f) => fetch(`${BASE}${f}.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const summary = await get("summary");
  const META = ["summary", "integrity", "notes", "manifest"];
  // Ask only for datasets the last build says exist, so a source that has never built is not requested.
  const built = (f) => META.includes(f) || (summary?.status?.[f] && summary.status[f] !== "missing");
  const res = await Promise.all(FILES.map((f) => (f === "summary" ? summary : built(f) ? get(f) : null)));
  FILES.forEach((f, i) => (state.data[f] = res[i] ? (res[i].data !== undefined && f !== "summary" && f !== "integrity" && f !== "notes" && f !== "manifest" ? res[i].data : res[i]) : null));
  state.raw = Object.fromEntries(FILES.map((f, i) => [f, res[i]]));
  state.topo = await fetch(`${BASE}geo/district.topo.json`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const s = state.data.summary;
  state.counties = s?.counties || [];
  state.counties.forEach((c) => state.byFips.set(c.county_fips, c));
}

// ---------------------------------------------------------------- helpers
function srcChip(id, label) {
  const s = (state.data.summary?.sources || []).find((x) => x.id === id);
  const text = label || (s ? shortSource(s) : id);
  return `<a class="src" href="#src-${id}" title="${F.esc(s?.apa || id)}">${F.esc(text)}</a>`;
}
function shortSource(s) {
  if (s.vintage) return s.vintage;
  if (s.publisher?.includes("Labor")) return "BLS";
  if (s.publisher?.includes("Treasury")) return "USAspending";
  if (s.publisher?.includes("Election Commission")) return "FEC";
  if (s.publisher?.includes("Clerk")) return "House Clerk";
  if (s.publisher?.includes("MIT")) return "MIT Election Lab";
  return s.publisher?.split(" ").slice(0, 3).join(" ") || s.id;
}
function sourceLine(ids, extra = "") {
  const names = ids.map((id) => (state.data.summary?.sources || []).find((s) => s.id === id)).filter(Boolean);
  if (!names.length) return extra;
  return `Source${names.length > 1 ? "s" : ""}: ${names.map((s) => `<a href="#src-${s.id}">${F.esc(s.publisher)}, ${F.esc(s.title)}</a>`).join("; ")}.${extra ? " " + extra : ""}`;
}
function empty(sel, msg = "This data was not available in the latest build.") {
  const el = $(sel);
  if (el) el.innerHTML = `<p class="sub">${msg}</p>`;
}
function tip(html, ev) {
  const t = $("#tooltip");
  if (!html) { t.hidden = true; return; }
  t.innerHTML = html;
  t.hidden = false;
  const pad = 14, w = t.offsetWidth, h = t.offsetHeight;
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + w > innerWidth - 8) x = ev.clientX - w - pad;
  if (y + h > innerHeight - 8) y = ev.clientY - h - pad;
  t.style.left = `${x}px`;
  t.style.top = `${y}px`;
}
function svgEl(container, w, h, label) {
  return d3.select(container).html("").append("svg").attr("viewBox", `0 0 ${w} ${h}`).attr("role", "img").attr("aria-label", label);
}
function countUp(el, to, fmt) {
  if (REDUCED || to == null) { el.textContent = fmt(to); return; }
  const start = performance.now(), dur = 1400;
  const step = (t) => {
    const k = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(to * e);
    if (k < 1) requestAnimationFrame(step); else el.textContent = fmt(to);
  };
  requestAnimationFrame(step);
}
function onVisible(el, fn, threshold = 0.25) {
  if (!el) return;
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { fn(); io.disconnect(); } }), { threshold });
  io.observe(el);
}
const projection = (w, h, feature, pad = 12) =>
  d3.geoConicConformal().parallels([44, 46.5]).rotate([90.5, 0]).fitExtent([[pad, pad], [w - pad, h - pad]], feature);

// ---------------------------------------------------------------- hero
function hero() {
  const topo = state.topo;
  if (!topo) return;
  const W = 1000, H = 760;
  const district = topojson.feature(topo, topo.objects.district);
  const parts = topojson.feature(topo, topo.objects.parts).features;
  const proj = projection(W, H, district, 30);
  const path = d3.geoPath(proj);
  const svg = svgEl("#hero-map", W, H, "");
  if (topo.objects.state) svg.append("path").attr("class", "state").attr("d", path(topojson.feature(topo, topo.objects.state)));
  const pops = parts.map((f) => state.byFips.get(f.properties.county_fips)?.pop_2020_in_district || 0);
  const o = d3.scaleSqrt().domain([0, d3.max(pops) || 1]).range([0.06, 0.32]);
  const order = d3.shuffle(parts.map((_, i) => i));
  svg.selectAll("path.county").data(parts).join("path").attr("class", "county").attr("d", path)
    .style("--o", (f, i) => o(pops[i]))
    .style("animation-delay", (f, i) => `${1.4 + order.indexOf(i) * 0.06}s`)
    .classed("on", true);
  const outline = svg.append("path").attr("class", "outline").attr("d", path(district));
  const len = outline.node().getTotalLength();
  outline.style("--len", len);
  if (!REDUCED && !FILM) parallax();
}

function parallax() {
  const map = $("#hero-map"), copy = $(".hero-copy"), hero = $(".hero");
  let ticking = false;
  const update = () => {
    const h = hero.offsetHeight, y = Math.min(scrollY, h);
    const k = y / h;
    map.style.transform = `scale(${1 + k * 0.18}) translateY(${k * 40}px)`;
    map.style.opacity = String(0.8 * (1 - k * 0.9));
    copy.style.transform = `translateY(${k * -60}px)`;
    copy.style.opacity = String(1 - k * 1.2);
    ticking = false;
  };
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
}

// ---------------------------------------------------------------- glance
function glance() {
  const s = state.data.summary;
  if (!s) return;
  if (s.sample) $("#sample-banner").hidden = false;
  const grid = $("#glance-grid");
  const items = s.headline.slice(0, 8);
  grid.innerHTML = items.map((h, i) => `<div class="stat reveal" style="transition-delay:${i * 60}ms">
      <div class="num" data-i="${i}">${F.esc(h.display)}</div>
      <div class="lab">${F.esc(h.label)} ${srcChip(h.source)}</div>
      ${h.moe ? `<div class="moe">±${h.id === "income" ? F.usd(h.moe) : h.id === "age" ? F.one(h.moe) : F.int(h.moe)} margin of error</div>` : h.note ? `<div class="moe">${F.esc(h.note)}</div>` : ""}
    </div>`).join("");
  onVisible(grid, () => {
    items.forEach((h, i) => {
      const el = grid.querySelector(`.num[data-i="${i}"]`);
      if (typeof h.value !== "number") return;
      const fmt = h.id === "income" || h.id === "federal" ? (v) => (h.id === "federal" ? F.usd(v) : F.usd(Math.round(v)))
        : h.display.endsWith("%") ? (v) => `${v.toFixed(1)}%`
        : h.id === "age" ? (v) => v.toFixed(1)
        : (v) => F.int(Math.round(v));
      countUp(el, h.value, fmt);
    });
  });
  const acs = state.data.acs;
  $("#glance-note").innerHTML = acs ? `People, income, age, and homes: American Community Survey ${acs.vintage.acs1} 1-year estimates. Land and counties: Census Bureau, 119th Congress boundaries.` : "";
}

// ---------------------------------------------------------------- map (scrollytelling)
const STEPS = {
  outline: { legend: () => "", color: () => css("--accent"), opacity: () => 0.22 },
  split: { legend: () => `<span class="hatch-key"></span> Split between districts; only the part in the 7th is drawn`, color: () => css("--accent"), opacity: (c) => (c?.whole ? 0.1 : 0.6) },
  population: { metric: (c) => c?.pop_2020_in_district, scheme: "seq", label: "People living in the district, 2020 Census", fmt: F.int },
  change: { metric: (c) => c?.pop_change_pct, scheme: "div", label: "Population change since April 2020 (whole county)", fmt: F.signedPct },
  income: { metric: (c) => c?.acs?.median_household_income, scheme: "seq", label: "Median household income (whole county, ACS 5-year)", fmt: (v) => F.usd(v) },
  unemployment: { metric: (c) => c?.unemployment?.rate, scheme: "warm", label: "Unemployment rate, latest month (whole county)", fmt: (v) => F.pct(v) },
  explore: { metric: (c) => c?.pop_change_pct, scheme: "div", label: "Population change since April 2020 (whole county)", fmt: F.signedPct },
};

function scaleFor(step) {
  const vals = state.counties.map(step.metric).filter((v) => v != null);
  if (!vals.length) return null;
  if (step.scheme === "div") {
    const lim = d3.max(vals, Math.abs) || 1;
    const interp = d3.interpolateRgbBasis([css("--shrink"), css("--land"), css("--grow")]);
    return { fn: (v) => interp((v + lim) / (2 * lim)), domain: [-lim, lim], interp };
  }
  const lo = d3.min(vals), hi = d3.max(vals);
  const base = step.scheme === "warm" ? css("--shrink") : css("--accent");
  const interp = d3.interpolateRgb(css("--land"), base);
  return { fn: (v) => interp(0.15 + 0.85 * (v - lo) / ((hi - lo) || 1)), domain: [lo, hi], interp: (t) => interp(0.15 + 0.85 * t) };
}

function mapInit() {
  const topo = state.topo;
  if (!topo) { empty("#map", "The map will appear after the first data build."); return; }
  const W = 820, H = 760;
  const district = topojson.feature(topo, topo.objects.district);
  const parts = topojson.feature(topo, topo.objects.parts).features;
  const proj = projection(W, H, district, 16);
  const path = d3.geoPath(proj);
  const svg = svgEl("#map", W, H, "Map of the district's counties");
  const defs = svg.append("defs");
  defs.append("pattern").attr("id", "hatch").attr("width", 7).attr("height", 7).attr("patternUnits", "userSpaceOnUse").attr("patternTransform", "rotate(45)")
    .append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 7).attr("stroke", css("--ink")).attr("stroke-opacity", 0.38).attr("stroke-width", 1.6);
  if (topo.objects.counties) {
    svg.append("g").selectAll("path").data(topojson.feature(topo, topo.objects.counties).features).join("path").attr("class", "ctx").attr("d", path);
  }
  const g = svg.append("g");
  state.mapParts = g.selectAll("path.part").data(parts).join("path").attr("class", "part").attr("d", path)
    .attr("tabindex", 0).attr("role", "button")
    .attr("aria-label", (f) => `${f.properties.name}${state.byFips.get(f.properties.county_fips)?.whole === false ? ", split county" : ""}`)
    .on("mousemove", (ev, f) => tip(countyTip(f.properties.county_fips), ev))
    .on("mouseleave", () => tip(null))
    .on("click", (ev, f) => openCounty(f.properties.county_fips))
    .on("keydown", (ev, f) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); openCounty(f.properties.county_fips); } });
  state.mapHatch = g.selectAll("path.hatch").data(parts.filter((f) => state.byFips.get(f.properties.county_fips)?.whole === false))
    .join("path").attr("class", "hatch").attr("d", path).attr("fill", "url(#hatch)");
  svg.append("path").attr("class", "outline").attr("d", path(district));
  svg.append("g").selectAll("text").data(parts).join("text").attr("class", "label")
    .attr("transform", (f) => `translate(${path.centroid(f)})`).attr("text-anchor", "middle").attr("dy", "0.35em")
    .text((f) => (f.properties.name || "").replace(" County", ""));
  setStep("outline");
}

function countyTip(fips) {
  const c = state.byFips.get(fips);
  if (!c) return "";
  const st = STEPS[state.step];
  const line = st.metric ? `<div>${F.esc(st.label)}: <strong>${st.fmt(st.metric(c))}</strong></div>` : "";
  return `<b>${F.esc(c.short_name)} County</b>${c.whole ? "Whole county in the district" : `Split: ${F.pct((c.pop_share_in_district || 0) * 100, 0)} of its people live in the 7th`}${line}<div class="fine" style="margin-top:4px">Select for the full profile</div>`;
}

function setStep(name) {
  state.step = name;
  const st = STEPS[name];
  if (!state.mapParts) return;
  const sc = st.metric ? scaleFor(st) : null;
  state.mapParts.transition().duration(REDUCED ? 0 : 800)
    .attr("fill", (f) => {
      const c = state.byFips.get(f.properties.county_fips);
      if (sc) { const v = st.metric(c); return v == null ? css("--land") : sc.fn(v); }
      return st.color(c);
    })
    .attr("fill-opacity", (f) => (sc ? 1 : st.opacity(state.byFips.get(f.properties.county_fips))));
  state.mapHatch?.transition().duration(REDUCED ? 0 : 600).attr("opacity", name === "outline" || name === "split" ? 1 : 0.55);
  const leg = $("#map-legend");
  if (sc) {
    const ramp = d3.range(9).map((i) => `<span style="background:${sc.interp(i / 8)}"></span>`).join("");
    leg.innerHTML = `<div class="legend-title">${F.esc(st.label)}</div><div class="legend-row"><span>${st.fmt(sc.domain[0])}</span><div class="ramp">${ramp}</div><span>${st.fmt(sc.domain[1])}</span><span class="hatch-key" style="margin-left:18px"></span><span>Split county</span></div>`;
  } else {
    leg.innerHTML = st.legend();
  }
  const s = state.data.summary;
  const src = { population: ["census-cd119"], change: ["pep"], income: ["acs5"], unemployment: ["bls-laus"], explore: ["pep"] }[name] || ["census-cb", "census-rel"];
  $("#map-caption").innerHTML = sourceLine(src);
}

function stepTexts() {
  const s = state.data.summary, geo = state.data.geography;
  if (!s || !geo) return;
  const cs = state.counties;
  const split = cs.filter((c) => !c.whole);
  const land = s.headline.find((h) => h.id === "land");
  const b = geo.boundary || {};
  const share = b.share_of_state_land != null ? `, ${F.pct(b.share_of_state_land * 100, 0)} of Wisconsin's land area` : "";
  $("#step-outline").innerHTML = `<strong>${geo.county_count} counties</strong> and <strong>${land ? land.display : "n/a"} square miles of land</strong>${share}. ${geo.whole_count} counties lie wholly inside the district.`;
  if (b.land_rank_in_state === 1) $("#land-lede").textContent = `The largest of Wisconsin's ${b.districts_in_state} congressional districts by land area, drawn to the boundaries the U.S. House uses today.`;
  else if (b.land_rank_in_state) $("#land-lede").textContent = `Number ${b.land_rank_in_state} of Wisconsin's ${b.districts_in_state} congressional districts by land area, drawn to the boundaries the U.S. House uses today.`;
  if (split.length) {
    const list = split.map((c) => `${c.short_name} (${F.pct((c.pop_share_in_district || 0) * 100, 0)} of residents)`);
    $("#step-split").innerHTML = `${list.slice(0, -1).join(", ")}, and ${list.slice(-1)} are divided with neighboring districts. The map shows only the part inside the 7th.`;
  }
  const pop = [...cs].sort((a, b) => (b.pop_2020_in_district || 0) - (a.pop_2020_in_district || 0));
  if (pop.length) $("#step-population").innerHTML = `The 2020 Census counted <strong>${F.int(geo.pop_2020)}</strong> people in the district. <strong>${pop[0].short_name}</strong> is home to the most (${F.int(pop[0].pop_2020_in_district)}), <strong>${pop.at(-1).short_name}</strong> to the fewest (${F.int(pop.at(-1).pop_2020_in_district)}).`;
  const ch = cs.filter((c) => c.pop_change_pct != null);
  if (ch.length) {
    const grew = ch.filter((c) => c.pop_change_pct > 0).length;
    const top = d3.greatest(ch, (c) => c.pop_change_pct), low = d3.least(ch, (c) => c.pop_change_pct);
    const lowText = low.pop_change_pct < 0 ? `${low.short_name} lost the largest share (${F.signedPct(low.pop_change_pct)})` : `${low.short_name} grew the least (${F.signedPct(low.pop_change_pct)})`;
    $("#step-change").innerHTML = `Since April 2020, <strong>${grew} of ${ch.length} counties</strong> have gained people. ${top.short_name} grew the most (${F.signedPct(top.pop_change_pct)}); ${lowText}. Whole-county estimates to July ${ch[0].pop_latest_year}.`;
  }
  const inc = cs.filter((c) => c.acs?.median_household_income != null);
  if (inc.length) {
    const hi = d3.greatest(inc, (c) => c.acs.median_household_income), lo = d3.least(inc, (c) => c.acs.median_household_income);
    $("#step-income").innerHTML = `Median household income ranges from <strong>${F.usd(lo.acs.median_household_income)}</strong> in ${lo.short_name} County to <strong>${F.usd(hi.acs.median_household_income)}</strong> in ${hi.short_name} County (American Community Survey 5-year estimates).`;
  }
  const u = s.unemployment;
  if (u?.month) $("#step-unemployment").innerHTML = `In ${F.monthLabel(u.month)}, county unemployment ranged from <strong>${F.pct(u.county_min)}</strong> to <strong>${F.pct(u.county_max)}</strong>. Wisconsin was at ${F.pct(u.state)} and the nation at ${F.pct(u.us)}, not seasonally adjusted.`;
}

function scrolly() {
  const steps = document.querySelectorAll(".step");
  const io = new IntersectionObserver((es) => {
    es.forEach((e) => {
      if (e.isIntersecting) {
        steps.forEach((s) => s.classList.toggle("is-active", s === e.target));
        setStep(e.target.dataset.step);
      }
    });
  }, { rootMargin: "-45% 0px -45% 0px" });
  steps.forEach((s) => io.observe(s));
}

// ---------------------------------------------------------------- people
const COMPARE = [
  ["median_age", "Median age", "years", "All residents"],
  ["age_65_plus_pct", "Age 65 and older", "pct", "All residents"],
  ["veterans_pct", "Veterans", "pct", "Civilian adults"],
  ["seasonal_homes_pct", "Homes held for seasonal use", "pct", "All housing units"],
  ["owner_occupied_pct", "Homes lived in by their owners", "pct", "Occupied homes"],
  ["bachelors_plus_pct", "Bachelor's degree or more", "pct", "Adults 25 and older"],
  ["broadband_pct", "Households with broadband", "pct", "Households"],
  ["median_household_income", "Median household income", "usd", "Households"],
  ["median_home_value", "Median home value", "usd", "Owner-occupied homes"],
  ["poverty_pct", "Below the poverty line", "pct", "People"],
  ["uninsured_pct", "Without health insurance", "pct", "Civilian residents"],
  ["mean_commute_min", "Average commute", "minutes", "Workers"],
];

function people() {
  const acs = state.data.acs;
  if (!acs?.district) { empty("#compare-chart"); return; }
  const m = acs.district.metrics, s = acs.state.metrics, u = acs.us.metrics, moe = acs.district.moe || {};
  $("#people-lede").innerHTML = `The median resident is <strong>${F.one(m.median_age)}</strong> years old, compared with ${F.one(u.median_age)} nationally. ${F.pct(m.age_65_plus_pct)} of residents are 65 or older, and ${F.pct(m.seasonal_homes_pct)} of homes are held for seasonal or recreational use.`;
  const rows = COMPARE.filter(([k]) => m[k] != null);
  const box = $("#compare-chart");
  box.innerHTML = rows.map(([k, label, unit, uni]) => {
    const mx = Math.max(m[k], s[k] ?? 0, u[k] ?? 0) * 1.15 || 1;
    const pos = (v) => (v == null ? -100 : (100 * v) / mx);
    const fm = (v) => F.value(v, unit === "years" ? "years" : unit);
    const e = moe[k] ? ` ±${F.value(moe[k], unit === "years" ? "years" : unit)}` : "";
    return `<div class="compare-row">
      <div class="name">${label}<small>${uni}</small></div>
      <div class="track">
        <span class="pin us" data-left="${pos(u[k])}" style="left:0" title="United States ${fm(u[k])}"></span>
        <span class="pin state" data-left="${pos(s[k])}" style="left:0" title="Wisconsin ${fm(s[k])}"></span>
        <span class="pin district" data-left="${pos(m[k])}" style="left:0" title="District ${fm(m[k])}"></span>
      </div>
      <div class="vals"><b>${fm(m[k])}</b>${e ? `<small>${e} margin</small>` : ""}<small>WI ${unit === "usd" ? F.usd(s[k], { compact: true }) : fm(s[k])} · US ${unit === "usd" ? F.usd(u[k], { compact: true }) : fm(u[k])}</small></div>
    </div>`;
  }).join("");
  onVisible(box, () => box.querySelectorAll(".pin").forEach((p) => (p.style.left = `${p.dataset.left}%`)), 0.15);
  $("#compare-source").innerHTML = sourceLine(["acs1"], "District figures carry margins of error at 90% confidence.");

  // Age
  const bands = acs.district.age_bands, usb = Object.fromEntries(acs.us.age_bands.map((b) => [b.id, b.pct]));
  barsPaired("#age-chart", bands.map((b) => ({ label: b.label, a: b.pct, b: usb[b.id] })), "District", "United States", css("--us"));
  $("#age-source").innerHTML = sourceLine(["acs1"]);
  // Race
  const usr = Object.fromEntries(acs.us.race.map((r) => [r.id, r.pct]));
  barsPaired("#race-chart", acs.district.race.filter((r) => r.pct != null && (r.pct >= 0.3 || usr[r.id] >= 1)).map((r) => ({ label: r.label, a: r.pct, b: usr[r.id] })), "District", "United States", css("--us"));
  $("#race-source").innerHTML = sourceLine(["acs1"], "Groups other than Hispanic or Latino are not Hispanic and one race alone.");
  trends();
}

function barsPaired(sel, rows, aName, bName, bColor) {
  const W = 600, rh = 46, top = 6, left = 210, right = 70;
  const H = top + rows.length * rh;
  const svg = svgEl(sel, W, H, `${aName} compared with ${bName}`);
  const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => Math.max(r.a || 0, r.b || 0)) * 1.05]).range([left, W - right]);
  const g = svg.selectAll("g").data(rows).join("g").attr("transform", (r, i) => `translate(0,${top + i * rh})`);
  g.append("text").attr("x", 0).attr("y", 17).attr("font-size", 14).text((r) => r.label);
  const a = g.append("rect").attr("x", left).attr("y", 4).attr("height", 16).attr("rx", 4).attr("fill", css("--accent")).attr("width", 0);
  const b = g.append("rect").attr("x", left).attr("y", 24).attr("height", 9).attr("rx", 3).attr("fill", bColor).attr("width", 0);
  g.append("text").attr("x", (r) => x(r.a || 0) + 8).attr("y", 17).attr("font-size", 13).attr("font-weight", 600).text((r) => F.pct(r.a));
  g.append("text").attr("class", "muted").attr("x", (r) => x(r.b || 0) + 8).attr("y", 33).text((r) => F.pct(r.b));
  onVisible(svg.node(), () => {
    a.transition().duration(REDUCED ? 0 : 1000).delay((r, i) => i * 50).attr("width", (r) => x(r.a || 0) - left);
    b.transition().duration(REDUCED ? 0 : 1000).delay((r, i) => i * 50 + 100).attr("width", (r) => x(r.b || 0) - left);
  });
}

function trends() {
  const acs = state.data.acs;
  const t = acs?.district_trend || {};
  const years = Object.keys(t).sort();
  if (years.length < 2) { $("#trend-grid").innerHTML = `<p class="sub">Year-to-year district estimates appear once two comparable years are available.</p>`; return; }
  $("#trend-sub").textContent = `American Community Survey 1-year estimates, ${years[0]} to ${years.at(-1)}. These years share the same district lines. Income is in each year's dollars, not adjusted for inflation.`;
  const items = [["population", "Population", "count"], ["median_household_income", "Median household income", "usd"], ["poverty_pct", "Below the poverty line", "pct"],
    ["median_age", "Median age", "years"], ["age_65_plus_pct", "Age 65 and older", "pct"], ["broadband_pct", "Households with broadband", "pct"]]
    .filter(([k]) => years.every((y) => t[y][k] != null));
  $("#trend-grid").innerHTML = items.map(([k, lab, unit]) => `<div class="trend" data-k="${k}"><div class="t-label">${lab}</div><div class="t-value">${F.value(t[years.at(-1)][k], unit)}</div><div class="spark"></div><div class="fine" style="margin-top:6px">${years[0]}: ${F.value(t[years[0]][k], unit)}</div></div>`).join("");
  items.forEach(([k]) => sparkline(`.trend[data-k="${k}"] .spark`, years.map((y) => t[y][k])));
}

function sparkline(sel, vals, color = css("--accent")) {
  const W = 260, H = 54;
  const svg = svgEl(sel, W, H, "Trend");
  const x = d3.scaleLinear().domain([0, vals.length - 1]).range([4, W - 4]);
  const ext = d3.extent(vals);
  const pad = (ext[1] - ext[0]) * 0.2 || 1;
  const y = d3.scaleLinear().domain([ext[0] - pad, ext[1] + pad]).range([H - 4, 4]);
  const line = d3.line().x((v, i) => x(i)).y((v) => y(v)).curve(d3.curveMonotoneX);
  svg.append("path").attr("d", line(vals)).attr("fill", "none").attr("stroke", color).attr("stroke-width", 2.4).attr("stroke-linecap", "round");
  svg.append("circle").attr("cx", x(vals.length - 1)).attr("cy", y(vals.at(-1))).attr("r", 4).attr("fill", color);
}

// ---------------------------------------------------------------- work
function work() {
  const acs = state.data.acs, laus = state.data.laus, q = state.data.qcew;
  if (acs?.district) {
    const ind = acs.district.industry.filter((r) => r.pct != null);
    const stI = Object.fromEntries(acs.state.industry.map((r) => [r.id, r.pct]));
    barsPaired("#industry-chart", ind.slice(0, 9).map((r) => ({ label: r.short || r.label, a: r.pct, b: stI[r.id] })), "District", "Wisconsin", css("--state"));
    $("#industry-source").innerHTML = sourceLine(["acs1"], "Share of employed residents, by where they live. Blue: district; gray: Wisconsin.");
    const mf = ind.find((r) => r.id === "manufacturing");
    $("#work-lede").innerHTML = `${ind[0] ? `The most common line of work is <strong>${ind[0].label.toLowerCase()}</strong>, at ${F.pct(ind[0].pct)} of working residents.` : ""} ${mf ? `Manufacturing employs ${F.pct(mf.pct)}, compared with ${F.pct(stI.manufacturing)} statewide.` : ""}`;
  } else empty("#industry-chart");
  if (laus) lausChart(); else empty("#laus-chart");
  if (q) payChart(); else empty("#pay-chart");
}

function lausChart() {
  const laus = state.data.laus;
  const fips = state.counties.map((c) => c.county_fips);
  const series = laus.series;
  const dates = [...new Set(fips.flatMap((f) => (series[f] || []).map((p) => p.date)))].sort();
  const parse = d3.timeParse("%Y-%m");
  const W = 1080, H = 420, m = { t: 16, r: 150, b: 34, l: 44 };
  const svg = svgEl("#laus-chart", W, H, "Monthly unemployment rate");
  const x = d3.scaleTime().domain(d3.extent(dates, parse)).range([m.l, W - m.r]);
  const byDate = new Map(dates.map((dt) => [dt, fips.map((f) => (series[f] || []).find((p) => p.date === dt)?.rate).filter((v) => v != null)]));
  const ymax = d3.max([...byDate.values()].flat()) * 1.08;
  const y = d3.scaleLinear().domain([0, ymax]).nice().range([H - m.b, m.t]);
  svg.append("g").attr("class", "grid").selectAll("line").data(y.ticks(5)).join("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y).attr("y2", y);
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(d3.timeYear.every(1)).tickSize(0).tickPadding(10));
  svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(8).tickFormat((v) => `${v}%`));
  const area = d3.area().x((d) => x(parse(d[0]))).y0((d) => y(d3.min(d[1]))).y1((d) => y(d3.max(d[1]))).curve(d3.curveMonotoneX);
  svg.append("path").datum([...byDate.entries()].filter((d) => d[1].length)).attr("d", area).attr("fill", css("--accent")).attr("fill-opacity", 0.14);
  const line = d3.line().x((p) => x(parse(p.date))).y((p) => y(p.rate)).curve(d3.curveMonotoneX);
  const labels = [];
  [["us", css("--us"), "United States"], ["state", css("--state"), "Wisconsin"]].forEach(([k, col, name]) => {
    const s = (series[k] || []).filter((p) => p.date >= dates[0]);
    if (!s.length) return;
    const p = svg.append("path").attr("d", line(s)).attr("fill", "none").attr("stroke", col).attr("stroke-width", 2.4);
    drawIn(p);
    labels.push([y(s.at(-1).rate), name, col]);
  });
  const hl = svg.append("path").attr("fill", "none").attr("stroke", css("--accent")).attr("stroke-width", 2.6);
  const last = byDate.get(dates.at(-1));
  labels.push([(y(d3.min(last)) + y(d3.max(last))) / 2, "District counties", css("--accent")]);
  const hlLabel = svg.append("text").attr("font-size", 13).attr("font-weight", 600).attr("fill", css("--accent"));
  spreadLabels(labels, 17).forEach(([yy, name, col]) => svg.append("text").attr("x", W - m.r + 12).attr("y", yy + 4).attr("font-size", 13).attr("fill", col).text(name));
  const sel = $("#laus-county");
  sel.innerHTML = `<option value="">None</option>` + state.counties.map((c) => `<option value="${c.county_fips}">${F.esc(c.short_name)}</option>`).join("");
  sel.onchange = () => {
    const f = sel.value, s = series[f] || [];
    hl.attr("d", s.length ? line(s.filter((p) => p.date >= dates[0])) : null);
    if (s.length) drawIn(hl);
    hlLabel.attr("x", s.length ? x(parse(s.at(-1).date)) - 6 : -999).attr("y", s.length ? y(s.at(-1).rate) - 10 : -999).attr("text-anchor", "end").text(s.length ? `${state.byFips.get(f).short_name} ${F.pct(s.at(-1).rate)}` : "");
  };
  // hover crosshair
  const cross = svg.append("line").attr("y1", m.t).attr("y2", H - m.b).attr("stroke", css("--faint")).attr("stroke-dasharray", "3 3").attr("opacity", 0);
  svg.append("rect").attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b).attr("fill", "transparent")
    .on("mousemove", (ev) => {
      const [px] = d3.pointer(ev);
      const dt = d3.timeFormat("%Y-%m")(x.invert(px));
      const vals = byDate.get(dt);
      if (!vals) return;
      cross.attr("x1", x(parse(dt))).attr("x2", x(parse(dt))).attr("opacity", 1);
      const st = (series.state || []).find((p) => p.date === dt), us = (series.us || []).find((p) => p.date === dt);
      const f = sel.value, cv = f ? (series[f] || []).find((p) => p.date === dt) : null;
      tip(`<b>${F.monthLabel(dt)}</b>Counties: ${F.pct(d3.min(vals))} to ${F.pct(d3.max(vals))}<br>Wisconsin: ${F.pct(st?.rate)}<br>United States: ${F.pct(us?.rate)}${cv ? `<br>${state.byFips.get(f).short_name}: ${F.pct(cv.rate)}` : ""}${(st?.preliminary || cv?.preliminary) ? "<br><em>Preliminary</em>" : ""}`, ev);
    })
    .on("mouseleave", () => { cross.attr("opacity", 0); tip(null); });
  $("#laus-source").innerHTML = sourceLine(["bls-laus"], `Not seasonally adjusted, through ${F.monthLabel(laus.latest_month)}; the latest month is preliminary. The band spans the lowest and highest county each month.`);
}

function drawIn(path) {
  if (REDUCED) return;
  const len = path.node().getTotalLength();
  path.attr("stroke-dasharray", `${len} ${len}`).attr("stroke-dashoffset", len);
  onVisible(path.node().ownerSVGElement, () => path.transition().duration(2200).ease(d3.easeCubicInOut).attr("stroke-dashoffset", 0).on("end", () => path.attr("stroke-dasharray", null)), 0.2);
}

function spreadLabels(items, gap) {
  items.sort((a, b) => a[0] - b[0]);
  for (let k = 0; k < 50; k++) {
    let moved = false;
    for (let i = 1; i < items.length; i++) {
      const d = items[i][0] - items[i - 1][0];
      if (d < gap) { const p = (gap - d) / 2; items[i - 1][0] -= p; items[i][0] += p; moved = true; }
    }
    if (!moved) break;
  }
  return items;
}

function payChart() {
  const q = state.data.qcew;
  const rows = state.counties.filter((c) => c.avg_annual_pay).sort((a, b) => b.avg_annual_pay - a.avg_annual_pay);
  const W = 560, rh = 22, left = 110, right = 120;
  const H = rows.length * rh + 10;
  const svg = svgEl("#pay-chart", W, H, "Average annual pay by county");
  const x = d3.scaleLinear().domain([0, d3.max(rows, (r) => r.avg_annual_pay)]).range([left, W - right]);
  const g = svg.selectAll("g").data(rows).join("g").attr("transform", (r, i) => `translate(0,${i * rh})`);
  g.append("text").attr("x", 0).attr("y", 14).attr("font-size", 12.5).text((r) => r.short_name);
  const b = g.append("rect").attr("x", left).attr("y", 3).attr("height", 14).attr("rx", 3).attr("fill", css("--accent")).attr("fill-opacity", (r) => (r.whole ? 1 : 0.55)).attr("width", 0);
  g.append("text").attr("x", (r) => x(r.avg_annual_pay) + 6).attr("y", 14).attr("font-size", 12).attr("font-weight", 600).text((r) => F.usd(r.avg_annual_pay));
  g.append("text").attr("class", "muted").attr("x", W).attr("y", 14).attr("text-anchor", "end").text((r) => `${F.int(r.jobs)} jobs`);
  onVisible(svg.node(), () => b.transition().duration(REDUCED ? 0 : 1000).delay((r, i) => i * 25).attr("width", (r) => x(r.avg_annual_pay) - left));
  $("#pay-source").innerHTML = sourceLine(["bls-qcew"], `${q.year} annual averages, whole counties, all ownerships. Lighter bars are split counties.`);
}

// ---------------------------------------------------------------- right now: cameras and aircraft
// Camera and aircraft handling is adapted from cameras.js and flights.js in
// Normansrule/global-intelligence-atlas, reused with the author's permission (see NOTICE.md).
const PLANE = "M0,-9 L2,-3 L9,2 L9,4 L2,2 L1.4,7 L4,9 L4,10 L0,9 L-4,10 L-4,9 L-1.4,7 L-2,2 L-9,4 L-9,2 L-2,-3 Z";
function liveNow() {
  const topo = state.topo, cams = state.data.cameras?.cameras || [], repo = state.data.summary?.district?.repo;
  const box = $("#now");
  if (!box || !topo || (!cams.length && !repo)) return;
  box.hidden = false;
  const W = 820, H = 700;
  const district = topojson.feature(topo, topo.objects.district);
  const proj = projection(W, H, district, 16);
  const path = d3.geoPath(proj);
  const svg = svgEl("#now-map", W, H, "Map of the district with public road cameras and aircraft overhead");
  if (topo.objects.counties) svg.append("g").selectAll("path").data(topojson.feature(topo, topo.objects.counties).features).join("path").attr("class", "ctx").attr("d", path);
  svg.append("g").selectAll("path").data(topojson.feature(topo, topo.objects.parts).features).join("path").attr("class", "part now-part").attr("d", path);
  svg.append("path").attr("class", "now-outline").attr("d", path(district));
  const gPlanes = svg.append("g"), gCams = svg.append("g");

  const show = (c) => {
    $("#cam-view").hidden = false;
    const img = $("#cam-img");
    img.alt = `Current view from the camera at ${c.name}`;
    img.onerror = () => { $("#cam-cap").innerHTML = `${F.esc(c.name)}: the agency's image did not load. <a href="${F.esc(c.image_url)}" target="_blank" rel="noopener">Open it at the source</a>.`; img.hidden = true; img.removeAttribute("src"); };
    img.hidden = false;
    img.src = `${c.image_url}${c.image_url.includes("?") ? "&" : "?"}t=${Math.floor(Date.now() / 60000)}`;
    $("#cam-cap").innerHTML = `<b>${F.esc(c.name)}</b> · ${F.esc(c.county || "")} County<br>Image: ${F.esc(c.operator)}. <a href="${F.esc(c.image_url)}" target="_blank" rel="noopener">Open at the source</a>`;
    gCams.selectAll("circle").classed("on", (d) => d.id === c.id);
    document.querySelectorAll("#cam-list button").forEach((b) => b.classList.toggle("on", b.dataset.id === c.id));
  };
  gCams.selectAll("circle").data(cams).join("circle").attr("class", "cam").attr("r", 7)
    .attr("cx", (c) => proj([c.lon, c.lat])[0]).attr("cy", (c) => proj([c.lon, c.lat])[1])
    .attr("tabindex", 0).attr("role", "button").attr("aria-label", (c) => `Camera: ${c.name}, ${c.county} County`)
    .on("mousemove", (ev, c) => tip(`<b>${F.esc(c.name)}</b>${F.esc(c.county || "")} County`, ev)).on("mouseleave", () => tip(null))
    .on("click", (ev, c) => show(c)).on("keydown", (ev, c) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); show(c); } });
  $("#cam-title").textContent = `Road cameras (${cams.length})`;
  $("#cam-list").innerHTML = cams.length ? cams.map((c) => `<button type="button" data-id="${F.esc(c.id)}">${F.esc(c.name)}<span>${F.esc(c.county || "")}</span></button>`).join("") : `<p class="sub">No public cameras are listed inside the district in the latest build.</p>`;
  document.querySelectorAll("#cam-list button").forEach((b) => (b.onclick = () => show(cams.find((c) => c.id === b.dataset.id))));
  if (!cams.length) $("#cam-sub").textContent = "";

  const alt = (a) => (a.on_ground ? "on the ground" : a.altitude_ft != null ? `${F.int(a.altitude_ft)} ft` : "altitude not reported");
  const drawPlanes = (snap) => {
    const ac = snap?.ok ? snap.aircraft : [];
    gPlanes.selectAll("path").data(ac, (a) => a.hex).join("path").attr("class", "plane").attr("d", PLANE)
      .attr("transform", (a) => { const p = proj([a.lon, a.lat]); return `translate(${p[0]},${p[1]}) rotate(${a.track || 0}) scale(1.25)`; })
      .on("mousemove", (ev, a) => tip(`<b>${F.esc(a.callsign || "No callsign")}</b>${a.type ? F.esc(a.type) + " · " : ""}${alt(a)}${a.speed_kt != null ? ` · ${a.speed_kt} kt` : ""}`, ev))
      .on("mouseleave", () => tip(null));
    const when = snap?.generated_at ? new Date(snap.generated_at) : null;
    const mins = when ? Math.max(0, Math.round((Date.now() - when) / 60000)) : null;
    const stale = mins != null && mins > 90;
    $("#air-title").textContent = snap?.ok ? `Aircraft overhead (${ac.length})` : "Aircraft overhead";
    $("#air-list").innerHTML = !snap ? `<p class="sub">The aircraft snapshot is not available yet.</p>`
      : !snap.ok ? `<p class="sub">No flight source answered at the last attempt.</p>`
      : ac.length ? `<table><thead><tr><th>Flight</th><th>Type</th><th class="num">Altitude</th><th class="num">Speed</th></tr></thead><tbody>${ac.slice().sort((x, y) => (y.altitude_ft || 0) - (x.altitude_ft || 0)).slice(0, 14).map((a) => `<tr><td>${F.esc(a.callsign || "—")}</td><td>${F.esc(a.type || "—")}</td><td class="num">${alt(a)}</td><td class="num">${a.speed_kt != null ? a.speed_kt + " kt" : "—"}</td></tr>`).join("")}</tbody></table>${ac.length > 14 ? `<p class="fine">Showing the 14 highest of ${ac.length}.</p>` : ""}`
      : `<p class="sub">No aircraft were heard over the district at the last snapshot.</p>`;
    const stamp = when ? `${when.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} (${mins} minute${mins === 1 ? "" : "s"} ago)` : "";
    $("#now-lede").innerHTML = `${cams.length ? `${cams.length} public road cameras show current conditions. ` : ""}${snap?.ok ? `At the last snapshot, <strong>${ac.length}</strong> aircraft ${ac.length === 1 ? "was" : "were"} over the district.` : ""}`;
    $("#now-source").innerHTML = `${snap?.ok ? `Aircraft: a snapshot taken ${stamp} from <a href="${F.esc(snap.source_url)}" target="_blank" rel="noopener">${F.esc(snap.source)}</a> (${F.esc(snap.licence)}), refreshed about twice an hour, not real time. ${stale ? "<strong>This snapshot is more than 90 minutes old.</strong> " : ""}Positions come from volunteer receivers, which are sparse over the Northwoods, so some aircraft are not shown. ` : ""}${sourceLine(["open-eagle-eye"], "Camera images load from, and belong to, the agency that runs each camera. The registry does not list every public camera.")}`;
  };
  drawPlanes(null);
  if (repo) {
    const pull = () => fetch(`https://raw.githubusercontent.com/${repo}/live/aircraft.json?t=${Math.floor(Date.now() / 300000)}`).then((r) => (r.ok ? r.json() : null)).then(drawPlanes).catch(() => {});
    onVisible(box, () => { pull(); setInterval(() => { if (!document.hidden) pull(); }, 300000); }, 0.05);
  }
}

// ---------------------------------------------------------------- federal income tax
function taxes() {
  const t = state.data.irs, box = $("#taxes");
  const d = t?.district;
  if (!box || !d?.total_tax_liability) return;
  box.hidden = false;
  $("#taxes-title").textContent = `What residents paid in federal income tax, ${t.tax_year}`;
  $("#taxes-lede").innerHTML = `On ${F.int(d.returns)} individual returns for tax year ${t.tax_year}, people living in the district reported a total federal tax liability of <strong>${F.usd(d.total_tax_liability)}</strong>, or ${F.pct(d.tax_share_of_agi_pct)} of their adjusted gross income.`;
  const stat = (label, value) => `<div><b>${value}</b><span>${label}</span></div>`;
  $("#taxes-stats").innerHTML = stat("Returns filed", F.int(d.returns)) + stat("Adjusted gross income", F.usd(d.agi, { compact: true })) + stat("Tax per return", F.usd(d.tax_per_return)) + (d.refunds != null ? stat("Refunded after filing", F.usd(d.refunds, { compact: true })) : "");
  const rows = [["The district", d], [state.data.summary?.district?.state || "State", t.state], ["United States", t.us]].filter((r) => r[1]);
  $("#taxes-table").innerHTML = `<thead><tr><th>Per return</th><th class="num">Adjusted gross income</th><th class="num">Federal income tax</th><th class="num">Tax as a share of income</th></tr></thead><tbody>${rows.map(([n, r]) => `<tr><td>${F.esc(n)}</td><td class="num">${F.usd(r.agi_per_return)}</td><td class="num">${F.usd(r.tax_per_return)}</td><td class="num">${F.pct(r.tax_share_of_agi_pct)}</td></tr>`).join("")}</tbody>`;
  $("#taxes-source").innerHTML = sourceLine(["irs-soi-cd"], `Individual income tax returns only. Payroll taxes paid by employers, corporate income tax, excise taxes, and estate taxes are not published by congressional district, so this is not the district's total federal tax. Tax year ${t.tax_year} and the award fiscal years above cover different periods and different things, so the two are not a balance sheet.`);
}

// ---------------------------------------------------------------- federal dollars
function dollars() {
  const u = state.data.usaspending;
  if (!u?.years?.length) { empty("#fed-chart"); return; }
  let types = (u.award_types || []).filter((t) => u.years.some((y) => (y[t.id] || 0) > 0));
  if (!types.length) types = [{ id: "total", label: "All awards" }];
  const colors = d3.scaleOrdinal().domain(types.map((t) => t.id)).range([css("--accent"), css("--accent-2"), css("--grow"), css("--shrink"), css("--state"), css("--us")]);
  const W = 1080, H = 380, m = { t: 30, r: 10, b: 34, l: 64 };
  const svg = svgEl("#fed-chart", W, H, "Federal award obligations by fiscal year");
  const x = d3.scaleBand().domain(u.years.map((y) => y.fy)).range([m.l, W - m.r]).padding(0.28);
  const stack = d3.stack().keys(types.map((t) => t.id)).value((d, k) => Math.max(0, d[k] || 0))(u.years);
  const y = d3.scaleLinear().domain([0, d3.max(u.years, (r) => Math.max(r.total, d3.sum(types, (t) => Math.max(0, r[t.id] || 0))))]).nice().range([H - m.b, m.t]);
  svg.append("g").attr("class", "grid").selectAll("line").data(y.ticks(5)).join("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y).attr("y2", y);
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).tickFormat((v) => `FY${v}`).tickSize(0).tickPadding(10));
  svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(8).tickFormat(F.usdShort));
  const layers = svg.append("g").selectAll("g").data(stack).join("g").attr("fill", (s) => colors(s.key));
  const rects = layers.selectAll("rect").data((s) => s).join("rect").attr("x", (d) => x(d.data.fy)).attr("width", x.bandwidth()).attr("y", H - m.b).attr("height", 0)
    .on("mousemove", (ev, d) => tip(`<b>FY${d.data.fy}</b>Total: ${F.usd(d.data.total)}${types.map((t) => d.data[t.id] ? `<br>${t.label}: ${F.usd(d.data[t.id])}` : "").join("")}`, ev))
    .on("mouseleave", () => tip(null));
  onVisible(svg.node(), () => rects.transition().duration(REDUCED ? 0 : 1000).delay((d, i) => i * 40).attr("y", (d) => y(d[1])).attr("height", (d) => Math.max(0, y(d[0]) - y(d[1]))));
  svg.append("g").selectAll("text").data(u.years).join("text").attr("x", (d) => x(d.fy) + x.bandwidth() / 2).attr("y", (d) => y(d.total) - 8).attr("text-anchor", "middle").attr("font-size", 12).attr("font-weight", 600).text((d) => F.usdShort(d.total));
  const lg = svg.append("g").attr("transform", `translate(${m.l},10)`);
  let lx = 0;
  types.forEach((t) => { lg.append("rect").attr("x", lx).attr("y", -9).attr("width", 11).attr("height", 11).attr("rx", 2).attr("fill", colors(t.id)); lg.append("text").attr("x", lx + 16).attr("y", 0).attr("class", "muted").text(t.label); lx += 26 + t.label.length * 6.6; });
  const last = u.years.find((y) => y.fy === u.last_complete_fy);
  $("#dollars-lede").innerHTML = last ? `In fiscal year ${last.fy}, federal agencies committed <strong>${F.usd(last.total)}</strong> to contracts, grants, loans, and other awards for work performed in the district.` : "";
  $("#fed-source").innerHTML = sourceLine(["usaspending"], "Obligations are commitments to spend and are revised by agencies over time. Payments reported only at the county or state level, such as many benefits paid to individuals, are not included.");
  $("#agencies-title").textContent = `Top awarding agencies, FY${u.last_complete_fy}`;
  $("#programs-title").textContent = `Top programs, FY${u.last_complete_fy}`;
  rank("#agencies", u.top_agencies);
  rank("#programs", u.top_programs);
  taxes();
}

function rank(sel, rows) {
  const el = $(sel);
  if (!rows?.length) { el.innerHTML = `<p class="sub">Not available in this build.</p>`; return; }
  const mx = d3.max(rows, (r) => r.amount) || 1;
  el.innerHTML = rows.slice(0, 7).map((r) => `<div class="rank-row"><span>${F.esc(r.name)}</span><span class="amt">${F.usd(r.amount)}</span><div class="bar"><span style="width:${Math.max(0, (100 * r.amount) / mx)}%"></span></div></div>`).join("");
  el.closest(".panel")?.classList.add("reveal");
}

// ---------------------------------------------------------------- the seat
function partyColor(p) {
  const s = (p || "").toLowerCase();
  return s.startsWith("republican") ? css("--rep") : s.startsWith("democrat") ? css("--dem") : css("--oth");
}

function seat() {
  const leg = state.data.legislators;
  if (leg?.current) {
    const c = leg.current;
    const members = leg.members || [];
    $("#member-card").innerHTML = `<div class="role">Representative for the 7th District</div>
      <div class="who">${F.esc(c.name)}</div>
      <span class="party"><span class="party-chip" style="background:${partyColor(c.party)}"></span>${F.esc(c.party)}</span>
      <dl><dt>Current term</dt><dd>${F.longDate(c.start)} to ${F.longDate(c.end)}</dd>
      <dt>Held the seat since</dt><dd>${F.longDate(members.at(-1)?.start)}</dd>
      <dt>Members since ${members[0]?.start?.slice(0, 4) || ""}</dt><dd>${members.length}</dd></dl>
      <p class="fine">${sourceLine(["congress-legislators", "clerk-members"])}</p>`;
  } else empty("#member-card");
  const notes = (state.data.notes?.notes || []).filter((n) => n.section === "representation");
  $("#notes-card").innerHTML = notes.length ? `<h3>Notes</h3>` + notes.map((n) => `<div class="note ${n.status}">
      <span class="tag">${F.esc(n.status)}</span><h4>${F.esc(n.title)}</h4><p>${F.esc(n.text)}</p>
      <div class="refs">Verified ${F.longDate(n.verified_on)} · review by ${F.longDate(n.review_by)} · ${n.sources.map((s) => `<a href="${s.url}" title="${F.esc(s.apa)}">${F.esc(s.label || s.id)}</a>`).join(" · ")}</div></div>`).join("") : "";
  if (leg?.members?.length) seatTimeline(leg); else empty("#seat-chart");
  votes();
  elections();
  fec();
}

function seatTimeline(leg) {
  const members = leg.members.filter((m) => m.end >= "1963-01-01");
  const W = 1080, H = 170, m = { l: 10, r: 10 };
  const svg = svgEl("#seat-chart", W, H, "Timeline of members who have held the seat");
  const parse = (s) => new Date(`${s}T12:00:00`);
  const x = d3.scaleTime().domain([parse(members[0].start), d3.max([new Date(), parse(members.at(-1).end)])]).range([m.l, W - m.r]);
  svg.append("g").attr("class", "axis").attr("transform", "translate(0,22)").call(d3.axisTop(x).ticks(d3.timeYear.every(10)).tickSize(0).tickPadding(6));
  const g = svg.selectAll("g.m").data(members).join("g").attr("class", "m");
  const bars = g.append("rect").attr("x", (d) => x(parse(d.start))).attr("y", 36).attr("height", 44).attr("rx", 8).attr("fill", (d) => partyColor(d.parties.at(-1))).attr("width", 0)
    .on("mousemove", (ev, d) => tip(`<b>${F.esc(d.name)}</b>${d.parties.join(", ")}<br>${F.longDate(d.start)} to ${F.longDate(d.end)}<br>${d.terms} term${d.terms > 1 ? "s" : ""}`, ev)).on("mouseleave", () => tip(null));
  onVisible(svg.node(), () => bars.transition().duration(REDUCED ? 0 : 1200).delay((d, i) => i * 200).attr("width", (d) => Math.max(3, x(parse(d.end)) - x(parse(d.start)) - 2)));
  let rowEnd = [-1e9, -1e9];
  members.forEach((d) => {
    const a = x(parse(d.start)), b = x(parse(d.end)), room = Math.max(d.name.length * 7.8, 150);
    const anchorEnd = a + room > W - 10;
    const left = anchorEnd ? b - room : a, tx = anchorEnd ? b - 2 : a + 2;
    const row = left > rowEnd[0] + 12 ? 0 : 1;
    rowEnd[row] = left + room;
    const yy = 104 + row * 38;
    svg.append("text").attr("x", tx).attr("y", yy).attr("text-anchor", anchorEnd ? "end" : "start").attr("font-size", 14).attr("font-weight", 600).text(d.name);
    svg.append("text").attr("class", "muted").attr("x", tx).attr("y", yy + 16).attr("text-anchor", anchorEnd ? "end" : "start").text(`${d.start.slice(0, 4)} to ${d.end.slice(0, 4)} · ${d.parties.at(-1)}`);
  });
  $("#seat-source").innerHTML = sourceLine(["congress-legislators"], "District lines were redrawn after each census, so the area represented has changed over time.");
}

function votes() {
  const v = state.data.votes;
  if (!v?.yes_no_votes_while_held) { $("#votes-panel").hidden = true; return; }
  $("#votes-title").textContent = `How the seat has voted in the ${v.congress}th Congress`;
  const rings = [["missed_pct", "Votes missed", `${v.definitions.missed_pct || ""} House-wide: ${F.pct(v.house_missed_pct)}.`],
    ["with_party_majority_pct", "With own party's majority", v.definitions.with_party_majority_pct || ""],
    ["on_winning_side_pct", "On the winning side", v.definitions.on_winning_side_pct || ""]];
  const R = 60, C = 2 * Math.PI * R;
  $("#vote-rings").innerHTML = rings.map(([k, lab, def]) => `<div class="ring"><svg viewBox="0 0 150 150" role="img" aria-label="${lab}: ${F.pct(v[k])}">
      <circle class="track" cx="75" cy="75" r="${R}" fill="none" stroke-width="12"/>
      <circle class="fill" cx="75" cy="75" r="${R}" fill="none" stroke-width="12" stroke-linecap="round" transform="rotate(-90 75 75)" stroke-dasharray="${C}" stroke-dashoffset="${C}" data-off="${C * (1 - (v[k] || 0) / 100)}"/>
      <text class="r-val" x="75" y="84" text-anchor="middle">${F.pct(v[k])}</text></svg>
      <div class="r-lab">${lab}</div><div class="r-def">${F.esc(def)}</div></div>`).join("");
  onVisible($("#vote-rings"), () => document.querySelectorAll("#vote-rings circle.fill").forEach((c) => (c.style.strokeDashoffset = c.dataset.off)));
  $("#recent-votes").innerHTML = `<thead><tr><th>Date</th><th>Roll call</th><th>Measure</th><th>Question</th><th>Result</th><th>The seat</th></tr></thead><tbody>` +
    (v.recent || []).map((r) => `<tr><td>${F.longDate(r.date)}</td><td><a href="${r.clerk_url}">${r.roll}</a></td>
      <td>${r.bill_url ? `<a href="${r.bill_url}">${F.esc(r.legis)}</a>` : F.esc(r.legis || "")}<div class="fine" style="margin:2px 0 0">${F.esc(r.desc || "")}</div></td>
      <td>${F.esc(r.question)}</td><td>${F.esc(r.result)}</td><td><span class="vote-chip">${F.esc(r.member_vote)}</span></td></tr>`).join("") + "</tbody>";
  $("#votes-source").innerHTML = sourceLine(["clerk-votes"], `${F.int(v.yes_no_votes_while_held)} yes-or-no roll calls while the member held the seat.`);
}

function elections() {
  const e = state.data.elections;
  if (!e?.results?.length) { empty("#elections-chart"); return; }
  const res = e.results;
  const W = 1080, H = 400, m = { t: 58, r: 10, b: 34, l: 44 };
  const svg = svgEl("#elections-chart", W, H, "Share of the vote in each general election for the seat");
  const x = d3.scaleBand().domain(res.map((r) => r.year)).range([m.l, W - m.r]).padding(0.22);
  const y = d3.scaleLinear().domain([0, 100]).range([H - m.b, m.t]);
  svg.append("g").attr("class", "grid").selectAll("line").data([0, 25, 50, 75, 100]).join("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y).attr("y2", y).attr("stroke-width", (v) => (v === 50 ? 1.6 : 1));
  svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).tickValues([0, 25, 50, 75, 100]).tickSize(0).tickPadding(8).tickFormat((v) => `${v}%`));
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - m.b})`).call(d3.axisBottom(x).tickValues(res.filter((r, i) => i % 2 === 0 || i === res.length - 1).map((r) => r.year)).tickSize(0).tickPadding(10));
  const order = (c) => ((c.party || "").toLowerCase().startsWith("democrat") ? 0 : (c.party || "").toLowerCase().startsWith("republican") ? 1 : 2);
  const cols = svg.append("g").selectAll("g").data(res).join("g").attr("transform", (r) => `translate(${x(r.year)},0)`)
    .on("mousemove", (ev, r) => tip(`<b>${r.year}${r.new_lines ? " · new district lines" : ""}</b>${r.candidates.map((c) => `<span class="party-chip" style="background:${partyColor(c.party)}"></span>${F.esc(c.name)} (${F.esc(c.party || "no party")}): ${F.pct(c.pct)} · ${F.int(c.votes)}`).join("<br>")}<br>Total: ${F.int(r.total_votes)}`, ev))
    .on("mouseleave", () => tip(null));
  cols.each(function (r) {
    let acc = 0;
    const g = d3.select(this);
    [...r.candidates].sort((a, b) => order(a) - order(b)).forEach((c) => {
      const y0 = acc; acc += c.pct || 0;
      g.append("rect").attr("x", 0).attr("width", x.bandwidth()).attr("fill", partyColor(c.party)).attr("data-y", y(acc)).attr("data-h", y(y0) - y(acc)).attr("y", H - m.b).attr("height", 0);
    });
  });
  onVisible(svg.node(), () => svg.selectAll("rect[data-y]").transition().duration(REDUCED ? 0 : 900).delay((d, i) => i * 12).attr("y", function () { return this.dataset.y; }).attr("height", function () { return this.dataset.h; }));
  res.filter((r) => r.new_lines).forEach((r) => {
    const xx = x(r.year) - (x.step() * x.paddingInner()) / 2;
    svg.append("line").attr("x1", xx).attr("x2", xx).attr("y1", m.t - 8).attr("y2", H - m.b).attr("stroke", css("--ink")).attr("stroke-opacity", 0.5).attr("stroke-dasharray", "4 4");
    svg.append("text").attr("class", "muted").attr("x", xx + 4).attr("y", m.t - 12).text("New lines");
  });
  const lg = svg.append("g").attr("transform", `translate(${m.l},14)`);
  [["Democratic", css("--dem")], ["Republican", css("--rep")], ["Other", css("--oth")]].forEach(([n, c], i) => { lg.append("rect").attr("x", i * 110).attr("y", -9).attr("width", 11).attr("height", 11).attr("rx", 2).attr("fill", c); lg.append("text").attr("class", "muted").attr("x", i * 110 + 16).attr("y", 0).text(n); });
  $("#elections-source").innerHTML = sourceLine(["medsl-house", "fec-results"], "General elections only; special elections are not shown. Results for the most recent election appear after official certification.");
}

function fec() {
  const f = state.data.fec;
  if (!f?.cycles) { empty("#fec-table"); return; }
  const cycles = Object.keys(f.cycles).sort();
  const seg = $("#fec-cycles");
  seg.innerHTML = cycles.map((c) => `<button role="tab" data-c="${c}">${c}</button>`).join("");
  const show = (c) => {
    seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.c === c));
    const rows = f.cycles[c] || [];
    $("#fec-table").innerHTML = `<thead><tr><th>Candidate</th><th>Party</th><th class="num">Raised</th><th class="num">Spent</th><th class="num">Cash on hand</th><th>Through</th></tr></thead><tbody>` +
      (rows.length ? rows.map((r) => `<tr><td>${r.url ? `<a href="${r.url}">${F.esc(titleCase(r.name))}</a>` : F.esc(titleCase(r.name))}<div class="fine" style="margin:2px 0 0">${F.esc(r.status || "")}</div></td>
        <td><span class="party-chip" style="background:${partyColor(r.party)}"></span>${F.esc(r.party || "")}</td><td class="num">${F.usd(r.receipts)}</td><td class="num">${F.usd(r.disbursements)}</td><td class="num">${F.usd(r.cash_on_hand)}</td><td>${r.coverage_end ? F.longDate(r.coverage_end.slice(0, 10)) : ""}</td></tr>`).join("")
        : `<tr><td colspan="6">No candidate reported financial activity for this cycle.</td></tr>`) + "</tbody>";
  };
  seg.onclick = (e) => { const b = e.target.closest("button"); if (b) show(b.dataset.c); };
  show(cycles.at(-1));
  $("#fec-source").innerHTML = sourceLine(["fec"], "Totals for each candidate's principal campaign committee over the two-year cycle, through its latest report, sorted by amount raised.");
}
const titleCase = (s) => (s || "").toLowerCase().replace(/\b([a-z])/g, (m) => m.toUpperCase()).replace(/\bIi\b/, "II").replace(/\bIii\b/, "III");

// ---------------------------------------------------------------- counties
function counties() {
  const grid = $("#county-grid");
  if (!state.counties.length) { empty("#county-grid"); return; }
  let sort = "name", q = "";
  const keys = { name: (c) => c.short_name, pop: (c) => -(c.pop_latest || 0), change: (c) => -(c.pop_change_pct ?? -99), income: (c) => -(c.acs?.median_household_income || 0), unemp: (c) => -(c.unemployment?.rate || 0) };
  const render = () => {
    const rows = state.counties.filter((c) => c.short_name.toLowerCase().includes(q)).sort((a, b) => d3.ascending(keys[sort](a), keys[sort](b)));
    grid.innerHTML = rows.map((c) => `<button class="county-card" data-f="${c.county_fips}">
      <h3>${F.esc(c.short_name)}</h3>
      <div class="kind ${c.whole ? "" : "split"}">${c.whole ? "Whole county" : `Split · ${F.pct((c.pop_share_in_district || 0) * 100, 0)} of residents in the 7th`}</div>
      <div class="row"><span>Population ${c.pop_latest_year || ""}</span><span>${F.int(c.pop_latest)}</span></div>
      <div class="row"><span>Since 2020</span><span>${F.signedPct(c.pop_change_pct)}</span></div>
      <div class="row"><span>Median household income</span><span>${F.usd(c.acs?.median_household_income)}</span></div>
      <div class="row"><span>Unemployment</span><span>${F.pct(c.unemployment?.rate)}</span></div>
      <div class="spark-${c.county_fips}"></div></button>`).join("");
    rows.forEach((c) => { const s = Object.values(c.pop_series || {}); if (s.length > 1) sparkline(`.spark-${c.county_fips}`, s, (c.pop_change_pct ?? 0) >= 0 ? css("--grow") : css("--shrink")); });
  };
  $("#county-sort").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; sort = b.dataset.sort; $("#county-sort").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); render(); };
  $("#county-search").oninput = (e) => { q = e.target.value.trim().toLowerCase(); render(); };
  grid.onclick = (e) => { const b = e.target.closest(".county-card"); if (b) openCounty(b.dataset.f); };
  render();
}

function openCounty(fips) {
  const c = state.byFips.get(fips);
  if (!c) return;
  const a = c.acs || {}, laus = state.data.laus?.series?.[fips] || [], q = state.data.qcew?.counties?.[fips], u = state.data.usaspending;
  $("#drawer-body").innerHTML = `
    <div class="eyebrow">County profile</div>
    <h2 id="drawer-title">${F.esc(c.short_name)} County</h2>
    <div class="kind">${c.whole ? "Wholly inside the 7th District" : `Split: ${F.pct((c.pop_share_in_district || 0) * 100, 1)} of its 2020 residents (${F.int(c.pop_2020_in_district)}) live in the 7th`}</div>
    <section><h4>People ${srcChip("census-cd119", "2020 Census")} ${srcChip("pep")}</h4><div class="kv">
      <span>2020 Census, whole county</span><span class="v">${F.int(c.pop_2020_county)}</span>
      ${c.whole ? "" : `<span>2020 Census, part in the district</span><span class="v">${F.int(c.pop_2020_in_district)}</span>`}
      <span>Estimate, July ${c.pop_latest_year || ""}</span><span class="v">${F.int(c.pop_latest)}</span>
      <span>Change since April 2020</span><span class="v">${F.signedPct(c.pop_change_pct)}</span>
      <span>Births minus deaths since 2020</span><span class="v">${F.signedInt(c.natural_change)}</span>
      <span>Net migration since 2020</span><span class="v">${F.signedInt(c.net_migration)}</span></div></section>
    <section><h4>Life in the county ${srcChip("acs5")}</h4><div class="kv">
      <span>Median household income</span><span class="v">${F.usd(a.median_household_income)}</span>
      <span>Median age</span><span class="v">${F.one(a.median_age)}</span>
      <span>Age 65 and older</span><span class="v">${F.pct(a.age_65_plus_pct)}</span>
      <span>Below the poverty line</span><span class="v">${F.pct(a.poverty_pct)}</span>
      <span>Bachelor's degree or more</span><span class="v">${F.pct(a.bachelors_plus_pct)}</span>
      <span>Households with broadband</span><span class="v">${F.pct(a.broadband_pct)}</span>
      <span>Veterans (adults)</span><span class="v">${F.pct(a.veterans_pct)}</span>
      <span>Homes held for seasonal use</span><span class="v">${F.pct(a.seasonal_homes_pct)}</span>
      <span>Median home value</span><span class="v">${F.usd(a.median_home_value)}</span>
      <span>Without health insurance</span><span class="v">${F.pct(a.uninsured_pct)}</span></div></section>
    <section><h4>Work ${srcChip("bls-laus", "BLS LAUS")} ${srcChip("bls-qcew", "BLS QCEW")}</h4><div class="kv">
      <span>Unemployment, ${F.monthLabel(c.unemployment?.date)}${c.unemployment?.preliminary ? " (preliminary)" : ""}</span><span class="v">${F.pct(c.unemployment?.rate)}</span>
      <span>Jobs located in the county${q ? ` (${state.data.qcew.year})` : ""}</span><span class="v">${F.int(c.jobs)}</span>
      <span>Average annual pay</span><span class="v">${F.usd(c.avg_annual_pay)}</span>
      <span>Largest private sector by jobs</span><span class="v">${F.esc(c.top_private_sector || "n/a")}</span></div>
      <div id="drawer-laus" style="margin-top:12px"></div></section>
    <section><h4>Federal awards ${srcChip("usaspending", "USAspending")}</h4><div class="kv">
      <span>Obligations, FY${u?.last_complete_fy || ""} (whole county)</span><span class="v">${F.usd(c.federal_awards)}</span></div></section>
    <p class="fine">County figures describe the whole county${c.whole ? "" : ", including the part outside the district"}. Population for the part in the district comes from the 2020 Census.</p>`;
  if (laus.length > 2) sparkline("#drawer-laus", laus.slice(-60).map((p) => p.rate), css("--shrink"));
  $("#drawer").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
  $("#scrim").hidden = false;
  $("#drawer-close").focus();
  history.replaceState(null, "", `#county-${fips}`);
}
function closeDrawer() {
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#scrim").hidden = true;
  if (location.hash.startsWith("#county-")) history.replaceState(null, "", location.pathname + location.search);
}

// ---------------------------------------------------------------- trust
function trust() {
  const integ = state.data.integrity, s = state.data.summary, man = state.data.manifest;
  if (integ) {
    const sm = integ.summary;
    $("#checks-summary").textContent = `${sm.pass || 0} of ${sm.total} passing${sm.warn ? ` · ${sm.warn} for review` : ""}${sm.fail ? ` · ${sm.fail} failing` : ""}${sm.skip ? ` · ${sm.skip} not run` : ""}`;
    const icon = { pass: "✓", warn: "!", fail: "×", skip: "–" };
    $("#checks").innerHTML = integ.checks.map((c) => `<li class="${c.status}"><span class="icon" aria-label="${c.status}">${icon[c.status] || "?"}</span><div><div class="ct">${F.esc(c.title)}</div><div class="cd">${F.esc(c.detail)}</div></div></li>`).join("");
  }
  const files = [["summary", "Headline numbers and county table"], ["acs", "American Community Survey measures"], ["geography", "Counties, split shares, land area"], ["pep", "County population estimates"], ["laus", "Monthly unemployment"], ["qcew", "Jobs and pay by county"], ["usaspending", "Federal award obligations"], ["legislators", "Members who have held the seat"], ["elections", "General election results"], ["fec", "Campaign finance totals"], ["votes", "Roll-call participation"], ["integrity", "Cross-check results"], ["manifest", "Build status of every source"]];
  $("#downloads").innerHTML = files.filter(([f]) => state.raw[f]).map(([f, lab]) => `<li><a href="${BASE}${f}.json" download>${lab}<span>${f}.json</span></a></li>`).join("") + (state.topo ? `<li><a href="${BASE}geo/district.topo.json" download>District and county boundaries<span>district.topo.json</span></a></li>` : "");
  if (man?.built_at) $("#built-at").textContent = `Data built ${F.longDate(man.built_at)}. Refreshed weekly by GitHub Actions.`;
  if (s?.sources) {
    $("#sources").innerHTML = s.sources.map((x) => `<li id="src-${x.id}">${F.esc(x.apa)}${x.url ? ` <a href="${x.url}">Link</a>` : ""}${x.query ? `<span class="q">${F.esc(x.query)}</span>` : ""}</li>`).join("");
  }
  if (s?.district?.publisher) $("#publisher").textContent = s.district.publisher;
}

// ---------------------------------------------------------------- page chrome
function chrome() {
  document.querySelectorAll(".reveal").forEach((el) => {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12 });
    io.observe(el);
  });
  const links = [...document.querySelectorAll(".nav nav a")];
  const secs = links.map((a) => $(a.getAttribute("href")));
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${e.target.id}`)); }), { rootMargin: "-40% 0px -55% 0px" });
  secs.forEach((s) => s && io.observe(s));
  const root = document.documentElement;
  const saved = (() => { try { return localStorage.getItem("wi7-theme"); } catch { return null; } })();
  if (saved) root.classList.add(saved);
  $("#theme-toggle").onclick = () => {
    const dark = root.classList.contains("dark") || (!root.classList.contains("light") && matchMedia("(prefers-color-scheme: dark)").matches);
    root.classList.remove("dark", "light");
    root.classList.add(dark ? "light" : "dark");
    try { localStorage.setItem("wi7-theme", dark ? "light" : "dark"); } catch {}
    location.reload();
  };
  $("#drawer-close").onclick = closeDrawer;
  $("#scrim").onclick = closeDrawer;
  addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
  const m = location.hash.match(/^#county-(\d{3})$/);
  if (m) setTimeout(() => openCounty(m[1]), 400);
}

// Film mode: a scripted, smooth scroll through the page for recording the tour video.
async function film() {
  document.documentElement.classList.add("film");
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const glide = (to, ms) => new Promise((res) => {
    const from = scrollY, start = performance.now();
    const f = (t) => { const k = Math.min(1, (t - start) / ms), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; scrollTo(0, from + (to - from) * e); k < 1 ? requestAnimationFrame(f) : res(); };
    requestAnimationFrame(f);
  });
  const y = (sel) => $(sel).getBoundingClientRect().top + scrollY - 60;
  window.__filmDone = false;
  await wait(4800);
  await glide(y("#glance"), 1600); await wait(2600);
  for (const s of document.querySelectorAll(".step")) { await glide(s.getBoundingClientRect().top + scrollY - innerHeight * 0.35, 1300); await wait(1500); }
  for (const sel of ["#people", "#compare-chart", "#work", "#laus-chart", "#dollars", "#seat", "#seat-chart", "#elections-chart", "#counties", "#trust"]) { await glide(y(sel), 1500); await wait(1700); }
  window.__filmDone = true;
}

(async function main() {
  await load();
  chrome();
  hero();
  glance();
  mapInit();
  stepTexts();
  scrolly();
  people();
  work();
  dollars();
  liveNow();
  seat();
  counties();
  trust();
  chrome2();
  if (!FILM) fetch("media/tour.mp4", { method: "HEAD" }).then((r) => { if (r.ok) { $("#tour-video").poster = "media/poster.jpg"; $("#tour").hidden = false; $("#tour-btn").hidden = false; chrome2(); } }).catch(() => {});
  if (FILM) film();
})();

function chrome2() {
  // Panels created after first paint need the reveal observer too.
  document.querySelectorAll(".reveal:not(.in)").forEach((el) => {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12 });
    io.observe(el);
  });
}
