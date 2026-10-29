from pathlib import Path

SRC = Path('src/migraine-risk-card.js')
text = SRC.read_text()

old = """function flushTranslationWaiters(lang) {
  const waiters = TRANSLATION_WAITERS[lang] || [];
  delete TRANSLATION_WAITERS[lang];
  waiters.forEach(cb => { try { cb(); } catch (e) { /* rendering callback */ } });
}
"""
new = """function flushTranslationWaiters(lang) {
  const waiters = TRANSLATION_WAITERS[lang] || [];
  delete TRANSLATION_WAITERS[lang];
  waiters.forEach(cb => {
    try { cb(); }
    catch (e) { console.warn(`[migraine-risk-card] translation callback for ${lang} failed`, e); }
  });
}
"""
if old not in text:
    raise SystemExit('flushTranslationWaiters block not found')
text = text.replace(old, new, 1)

old = """  if (state && state !== 'loading' && state !== 'failed') {
    if (onLoad) Promise.resolve().then(onLoad);
    return;
  }
  if (state === 'failed' && Date.now() - (TRANSLATION_FAILED_AT[lang] || 0) < TRANSLATION_RETRY_MS) {
    if (onLoad) Promise.resolve().then(onLoad); // built-in EN fallback is already usable
    return;
  }
"""
new = """  // A cached dictionary is already visible to tr() synchronously. Do not fire
  // onLoad again: set hass() calls this on every HA state update, and doing so
  // would defeat the card's state-hash short-circuit and force a second render.
  if (state && state !== 'loading' && state !== 'failed') return;
  // A failed load has already flushed the original waiters so they could render
  // the built-in English fallback. Stay quiet until the retry window expires.
  if (state === 'failed' && Date.now() - (TRANSLATION_FAILED_AT[lang] || 0) < TRANSLATION_RETRY_MS) return;
"""
if old not in text:
    raise SystemExit('loadTranslation cached-state block not found')
text = text.replace(old, new, 1)

old = """  static getStubConfig(hass) {
    const ids = Object.keys(hass.states);
    const find = (p) => ids.find(id => id.includes(p)) || '';
    const cfg = { type: 'custom:migraine-risk-card' };
    // Auto-detect integration entities
    const rs = find('migraine_risk_score');
    if (rs) cfg.entity_risk_score = rs;
    const rl = find('migraine_risk_level');
    if (rl) cfg.entity_risk_level = rl;
    const fc = find('migraine_risk_forecast');
    if (fc) cfg.entity_forecast = fc;
    // Factor entities
    const map = {
      entity_pressure_6h: 'pressure_drop_6h',
      entity_pressure_24h: 'pressure_drop_24h',
      entity_humidity: 'migraine_humidity',
      entity_temperature: 'migraine_temperature',
      entity_temperature_change: 'migraine_temperature_change_6h',
      entity_wind_speed: 'migraine_wind',
      entity_uv_index: 'migraine_uv',
      entity_storm: 'thunderstorm',
      entity_air_quality: 'waqi_aqi',
    };
    for (const [key, pattern] of Object.entries(map)) {
      const e = find(pattern);
      if (e) cfg[key] = e;
    }
    return cfg;
  }
"""
new = """  static getStubConfig(hass) {
    const ids = Object.keys(hass.states);
    const find = (pattern, exact = '', exclude = []) => {
      if (exact && ids.includes(exact)) return exact;
      return ids.find(id => id.includes(pattern) && !exclude.some(x => id.includes(x))) || '';
    };
    const cfg = { type: 'custom:migraine-risk-card' };
    // Prefer canonical package IDs, then fall back to a conservative substring
    // match for renamed/legacy installations.
    const rs = find('migraine_risk_score', 'sensor.migraine_risk_score');
    if (rs) cfg.entity_risk_score = rs;
    const rl = find('migraine_risk_level', 'sensor.migraine_risk_level');
    if (rl) cfg.entity_risk_level = rl;
    const fc = find('migraine_risk_forecast', 'sensor.migraine_risk_forecast_tomorrow');
    if (fc) cfg.entity_forecast = fc;
    // Factor entities. In particular, never pick the signed Statistics
    // *_rolling helper instead of the public absolute 6h delta sensor.
    const map = {
      entity_pressure_6h: ['pressure_drop_6h', 'sensor.migraine_pressure_drop_6h'],
      entity_pressure_24h: ['pressure_drop_24h', 'sensor.migraine_pressure_drop_24h'],
      entity_humidity: ['migraine_humidity', 'sensor.migraine_humidity'],
      entity_temperature: ['migraine_temperature', 'sensor.migraine_temperature', ['temperature_change_6h']],
      entity_temperature_change: ['migraine_temperature_change_6h', 'sensor.migraine_temperature_change_6h', ['_rolling']],
      entity_wind_speed: ['migraine_wind', 'sensor.migraine_wind_speed'],
      entity_uv_index: ['migraine_uv', 'sensor.migraine_uv_index'],
      entity_storm: ['thunderstorm', ''],
      entity_air_quality: ['waqi_aqi', ''],
    };
    for (const [key, spec] of Object.entries(map)) {
      const [pattern, exact, exclude = []] = spec;
      const e = find(pattern, exact, exclude);
      if (e) cfg[key] = e;
    }
    return cfg;
  }
"""
if old not in text:
    raise SystemExit('getStubConfig block not found')
text = text.replace(old, new, 1)
SRC.write_text(text)
Path('dist/migraine-risk-card.js').write_text(text)

TEST = Path('tests/test-core.js')
t = TEST.read_text()
old = """assert(source.includes(\"entity_temperature_change: 'migraine_temperature_change_6h'\"), 'stub config must prefer the delta sensor');
assert(source.includes(\"if (!customElements.get('migraine-risk-card'))\"), 'duplicate resource registration must be guarded');
"""
new = """const translationLoader = source.slice(source.indexOf('function loadTranslation'), source.indexOf('function dictFor'));
assert(!translationLoader.includes('Promise.resolve().then(onLoad)'), 'cached translations must not schedule redundant renders');
assert(source.includes(\"'sensor.migraine_temperature_change_6h', ['_rolling']\"), 'stub config must prefer the public delta sensor over the rolling helper');
assert(source.includes(\"if (!customElements.get('migraine-risk-card'))\"), 'duplicate resource registration must be guarded');
"""
if old not in t:
    raise SystemExit('test replacement point not found')
t = t.replace(old, new, 1)
TEST.write_text(t)

README = Path('README.md')
r = README.read_text()
needle = """Starting with v3.0, the card does **not** use `sensor-package/migraine_sensors.yaml` as its backend. The package is retained as an optional compatibility/server-side layer for users migrating from 1.x/2.x installations and for users who explicitly want server-side score entities, automations, or WAQI-derived sensors. A normal standalone 3.x installation does not need it. In v3.4 its pressure/temperature windows were also changed to true rolling Statistics windows so legacy package users no longer get reset-boundary discontinuities.\n"""
addition = needle + """\n> **Recorder note for the optional package:** the Statistics sensors restore their rolling buffers from Recorder after a restart. If Recorder is disabled, the database was cleared, or the source entities are excluded, a nominal 6h/24h window initially covers only the samples collected since startup and becomes a full window only after enough time has elapsed. Use the public `sensor.migraine_temperature_change_6h` delta sensor rather than the internal `*_rolling` Statistics helper.\n"""
if needle not in r:
    raise SystemExit('README optional-package paragraph not found')
README.write_text(r.replace(needle, addition, 1))

YAML = Path('sensor-package/migraine_sensors.yaml')
y = YAML.read_text()
old = """###############################################################################
# INPUT HELPERS — pressure & temperature tracking state
# (These are managed automatically by the automations below)
###############################################################################
"""
new = """###############################################################################
# INPUT HELPERS — calibration plus legacy tracking state
# pressure_*_peak/reset_time and temperature_6h_baseline/reset_time are retained
# for 1.x/2.x compatibility only. v3.4 rolling calculations do not read or
# update them; they are candidates for removal in a future major release.
###############################################################################
"""
if old not in y:
    raise SystemExit('legacy helper heading not found')
y = y.replace(old, new, 1)
needle = """# The statistics integration restores its buffer from Recorder on startup.\n"""
replacement = needle + """# Without Recorder history, a restored window initially covers only samples\n# collected since startup until the configured max_age has elapsed.\n# The *_rolling sensors are internal helpers; consume the public template delta\n# sensors below for scoring/card mappings.\n"""
if needle not in y:
    raise SystemExit('statistics Recorder comment not found')
YAML.write_text(y.replace(needle, replacement, 1))

NOTES = Path('RELEASE_NOTES_3.4.0.md')
n = NOTES.read_text()
needle = '- Hardened translation loading for multiple cards and transient failures.\n'
replacement = needle + '- Kept cached translation lookups render-neutral so normal Home Assistant state updates still use the card state-hash short-circuit.\n'
if needle not in n:
    raise SystemExit('release notes translation bullet not found')
NOTES.write_text(n.replace(needle, replacement, 1))

print('3.4.0 review follow-up applied')
