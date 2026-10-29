const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('src/migraine-risk-card.js', 'utf8');
const marker = '/* ─── Styles';
const prefix = source.slice(0, source.indexOf(marker));
assert(prefix.length > 0, 'pure-function prefix not found');

const context = {
  console: { info() {}, warn() {} },
  Date,
  Intl,
  Promise,
  setTimeout,
  clearTimeout,
};
vm.createContext(context);
vm.runInContext(prefix + `\nthis.__mrc = {\n  THRESHOLD_DEFAULTS, tempToC, pressureToHpa, windToKmh,\n  computeDropFromPeak, computeChange, scoreTomorrow, computeFactorPoints,\n  extractFactorValue, dateKeyInTimeZone, tomorrowDateKey, tomorrowFromForecast\n};`, context);
const m = context.__mrc;

function close(actual, expected, epsilon = 1e-6) {
  assert(Math.abs(actual - expected) <= epsilon, `${actual} != ${expected}`);
}

// Unit conversion.
close(m.tempToC(86, '°F'), 30);
close(m.pressureToHpa(101.3, 'kPa'), 1013);
close(m.pressureToHpa(760, 'mmHg'), 1013.2472, 0.001);
close(m.windToKmh(10, 'm/s'), 36);
close(m.windToKmh(10, 'kt'), 18.52);

// Rolling pressure peak and temperature-change tolerance.
const anchor = Date.parse('2026-10-29T12:00:00Z');
const h = 3600e3;
assert.equal(m.computeDropFromPeak([
  { t: anchor - 5*h, v: 1020 },
  { t: anchor - 2*h, v: 1016 },
], 6, 1010, anchor), 10);
assert.equal(m.computeChange([{ t: anchor - 6*h, v: 10 }], 6, 16, anchor), 6);
assert.equal(m.computeChange([{ t: anchor - 3*h, v: 10 }], 6, 16, anchor), null);

// Fahrenheit forecast scoring must match the equivalent Celsius forecast.
const c = { temp_max: 30, temp_min: 20, uv: null, rain: null, wind: null, thunder: false };
const f = { temp_max: 86, temp_min: 68, uv: null, rain: null, wind: null, thunder: false };
assert.equal(m.scoreTomorrow(f, 'km/h', '°F', m.THRESHOLD_DEFAULTS),
             m.scoreTomorrow(c, 'km/h', '°C', m.THRESHOLD_DEFAULTS));

// Day selection is tied to the HA timezone, not the browser timezone.
const nearMidnight = Date.parse('2026-10-29T22:30:00Z');
assert.equal(m.dateKeyInTimeZone(nearMidnight, 'Europe/Riga'), '2026-10-30');
assert.equal(m.dateKeyInTimeZone(nearMidnight, 'America/New_York'), '2026-10-29');
assert.equal(m.tomorrowDateKey('Europe/Riga', nearMidnight), '2026-10-31');
assert.equal(m.tomorrowDateKey('America/New_York', nearMidnight), '2026-10-30');

// Current storm conditions beyond lightning-* are recognised.
assert.equal(m.extractFactorValue({
  entity_id: 'weather.test', state: 'thunderstorm', attributes: {}
}, 'thunderstorm', { unit: '' }).score, 2);
assert.equal(m.extractFactorValue({
  entity_id: 'weather.test', state: 'storm', attributes: {}
}, 'thunderstorm', { unit: '' }).score, 2);

// Structural regressions around Home Assistant APIs and lifecycle.
assert(source.includes('significant_changes_only=0'), 'history must include attribute-only changes');
assert(source.includes('s.last_updated || s.last_changed'), 'history must timestamp attribute changes by last_updated');
assert(source.includes("(a.pressure ?? '')"), 'weather pressure must participate in the state hash');
const translationLoader = source.slice(source.indexOf('function loadTranslation'), source.indexOf('function dictFor'));
assert(!translationLoader.includes('Promise.resolve().then(onLoad)'), 'cached translations must not schedule redundant renders');
assert(source.includes("'sensor.migraine_temperature_change_6h', ['_rolling']"), 'stub config must prefer the public delta sensor over the rolling helper');
assert(source.includes("if (!customElements.get('migraine-risk-card'))"), 'duplicate resource registration must be guarded');
const editorStart = source.indexOf('class MigraineRiskCardEditor');
const editorTranslation = source.slice(editorStart, source.indexOf('  _render() {', editorStart));
const editorLookup = editorTranslation.slice(editorTranslation.indexOf('  _t(path, fallback)'));
assert(!editorLookup.includes('loadTranslation('), 'editor translation lookup must be side-effect free');
assert(editorTranslation.includes('_requestTranslation()'), 'editor must request translations outside render lookups');
assert(source.includes("type: 'call_service'"), 'forecast fallback must use non-admin websocket call_service');
assert(!source.includes("type: 'execute_script'"), 'forecast fallback must not require admin-only execute_script');
assert(source.includes('FORECAST_RECOVERY_MS'), 'forecast failures must retain a long-term recovery path');

console.log('All migraine-risk-card core tests passed.');
