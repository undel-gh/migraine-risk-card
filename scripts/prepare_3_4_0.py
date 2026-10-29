from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    text = text.replace(old, new, 1)
    write(path, text)


def replace_all_checked(path, old, new, expected):
    text = read(path)
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"Expected {expected} occurrences in {path}, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new))


# ---------------------------------------------------------------------------
# Core card (standalone v3.x engine)
# ---------------------------------------------------------------------------
JS = "src/migraine-risk-card.js"

replace_once(JS, "const CARD_VERSION = '3.3.3';", "const CARD_VERSION = '3.4.0';")
replace_once(
    JS,
    " * Installation: Copy to /config/www/migraine-risk-card.js\n * Add resource: /local/migraine-risk-card.js (JavaScript Module)",
    " * Installation: HACS is recommended. Manual installs must copy the full dist/\n * directory (card + translations) and register dist/migraine-risk-card.js.",
)

replace_once(
    JS,
    """// lang → dictionary | 'loading' | 'failed'\nconst LOADED_TRANSLATIONS = {};\n\nfunction translationBases(config) {\n  const custom = config && config.translations_path;\n  return custom ? [custom.replace(/\\/?$/, '/')] : TRANSLATION_PATHS;\n}\n\n// Fetches a language file once; calls onLoad when it becomes available.\nfunction loadTranslation(lang, config, onLoad) {\n  if (!lang || LOADED_TRANSLATIONS[lang]) return;\n  LOADED_TRANSLATIONS[lang] = 'loading';\n  const bases = translationBases(config);\n  const attempt = (i) => {\n    if (i >= bases.length) {\n      LOADED_TRANSLATIONS[lang] = 'failed';\n      return;\n    }\n    fetch(bases[i] + lang + '.json', { cache: 'no-cache' })\n      .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))\n      .then(dict => {\n        LOADED_TRANSLATIONS[lang] = dict;\n        if (onLoad) onLoad();\n      })\n      .catch(() => attempt(i + 1));\n  };\n  attempt(0);\n}\n""",
    """// lang → dictionary | 'loading' | 'failed'\nconst LOADED_TRANSLATIONS = {};\nconst TRANSLATION_WAITERS = {};\nconst TRANSLATION_FAILED_AT = {};\nconst TRANSLATION_RETRY_MS = 5 * 60e3;\n\nfunction translationBases(config) {\n  const custom = config && config.translations_path;\n  return custom ? [custom.replace(/\\/?$/, '/')] : TRANSLATION_PATHS;\n}\n\nfunction flushTranslationWaiters(lang) {\n  const waiters = TRANSLATION_WAITERS[lang] || [];\n  delete TRANSLATION_WAITERS[lang];\n  waiters.forEach(cb => { try { cb(); } catch (e) { /* rendering callback */ } });\n}\n\n// Fetch a language once, fan the result out to every card waiting for it, and\n// allow a later retry after a transient HTTP/network failure.\nfunction loadTranslation(lang, config, onLoad) {\n  if (!lang) return;\n  const state = LOADED_TRANSLATIONS[lang];\n  if (state && state !== 'loading' && state !== 'failed') {\n    if (onLoad) Promise.resolve().then(onLoad);\n    return;\n  }\n  if (state === 'failed' && Date.now() - (TRANSLATION_FAILED_AT[lang] || 0) < TRANSLATION_RETRY_MS) {\n    if (onLoad) Promise.resolve().then(onLoad); // built-in EN fallback is already usable\n    return;\n  }\n  if (onLoad) (TRANSLATION_WAITERS[lang] ||= []).push(onLoad);\n  if (state === 'loading') return;\n\n  LOADED_TRANSLATIONS[lang] = 'loading';\n  const bases = translationBases(config);\n  const attempt = (i) => {\n    if (i >= bases.length) {\n      LOADED_TRANSLATIONS[lang] = 'failed';\n      TRANSLATION_FAILED_AT[lang] = Date.now();\n      flushTranslationWaiters(lang);\n      return;\n    }\n    fetch(bases[i] + lang + '.json', { cache: 'no-cache' })\n      .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))\n      .then(dict => {\n        LOADED_TRANSLATIONS[lang] = dict;\n        delete TRANSLATION_FAILED_AT[lang];\n        flushTranslationWaiters(lang);\n      })\n      .catch(() => attempt(i + 1));\n  };\n  attempt(0);\n}\n""",
)

replace_once(JS, "const v = cond.startsWith('lightning') ? 2 : 0;", "const v = THUNDER_CONDITIONS.includes(cond) ? 2 : 0;")

replace_once(
    JS,
    """function supportsForecast(entity, type) {\n  const f = entity && entity.attributes && entity.attributes.supported_features;\n  if (typeof f !== 'number') return true; // unknown → try anyway\n  return type === 'daily' ? !!(f & FEATURE_FORECAST_DAILY) : !!(f & FEATURE_FORECAST_HOURLY);\n}\n\n// Drop from the highest value within the last `hours`""",
    """function supportsForecast(entity, type) {\n  const f = entity && entity.attributes && entity.attributes.supported_features;\n  if (typeof f !== 'number') return true; // unknown → try anyway\n  return type === 'daily' ? !!(f & FEATURE_FORECAST_DAILY) : !!(f & FEATURE_FORECAST_HOURLY);\n}\n\nfunction dateKeyInTimeZone(value, timeZone) {\n  const d = value instanceof Date ? value : new Date(value);\n  if (isNaN(d.getTime())) return null;\n  if (!timeZone) return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;\n  const parts = new Intl.DateTimeFormat('en-CA', {\n    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',\n  }).formatToParts(d);\n  const get = (type) => parts.find(p => p.type === type)?.value;\n  return `${get('year')}-${get('month')}-${get('day')}`;\n}\n\nfunction tomorrowDateKey(timeZone, nowMs) {\n  const today = dateKeyInTimeZone(nowMs == null ? Date.now() : nowMs, timeZone);\n  if (!today) return null;\n  const [y, m, d] = today.split('-').map(Number);\n  return new Date(Date.UTC(y, m - 1, d + 1)).toISOString().slice(0, 10);\n}\n\nfunction hourInTimeZone(value, timeZone) {\n  const d = value instanceof Date ? value : new Date(value);\n  if (isNaN(d.getTime())) return null;\n  if (!timeZone) return d.getHours();\n  const hour = new Intl.DateTimeFormat('en-US', { timeZone, hour: '2-digit', hourCycle: 'h23' })\n    .formatToParts(d).find(p => p.type === 'hour')?.value;\n  return hour == null ? null : Number(hour);\n}\n\n// Drop from the highest value within the last `hours`""",
)

replace_once(JS, "function thunderLevelFromHourly(forecast) {", "function thunderLevelFromHourly(forecast, timeZone) {")
replace_once(JS, "const todayStr = new Date().toDateString();", "const todayStr = dateKeyInTimeZone(Date.now(), timeZone);")
replace_once(JS, "if (new Date(f.datetime).toDateString() === todayStr) today = true;", "if (dateKeyInTimeZone(f.datetime, timeZone) === todayStr) today = true;")
replace_once(JS, "function tomorrowFromForecast(forecast, isHourly) {", "function tomorrowFromForecast(forecast, isHourly, timeZone) {")
replace_once(JS, "const tomorrow = new Date(Date.now() + 24 * 3600e3).toDateString();", "const tomorrow = tomorrowDateKey(timeZone);")
replace_once(JS, "return !isNaN(d.getTime()) && d.toDateString() === tomorrow;", "return !isNaN(d.getTime()) && dateKeyInTimeZone(d, timeZone) === tomorrow;")
replace_once(
    JS,
    """  const midday = entries.reduce((best, e) =>\n    Math.abs(new Date(e.datetime).getHours() - 13) <\n    Math.abs(new Date(best.datetime).getHours() - 13) ? e : best, entries[0]);""",
    """  const midday = entries.reduce((best, e) =>\n    Math.abs((hourInTimeZone(e.datetime, timeZone) ?? 13) - 13) <\n    Math.abs((hourInTimeZone(best.datetime, timeZone) ?? 13) - 13) ? e : best, entries[0]);""",
)

replace_once(JS, "function scoreTomorrow(d, windUnit, th) {", "function scoreTomorrow(d, windUnit, tempUnit, th) {")
replace_once(
    JS,
    """  const { temp_max: tmax, temp_min: tmin, uv, rain } = d;""",
    """  const { temp_max: rawMax, temp_min: rawMin, uv, rain } = d;\n  const tmax = tempToC(rawMax, tempUnit);\n  const tmin = tempToC(rawMin, tempUnit);""",
)

replace_once(
    JS,
    """  disconnectedCallback() {\n    this._hist = {};   // drop cached history so re-created cards don't accumulate\n    for (const k of Object.keys(this._fc)) {\n      const store = this._fc[k];\n      if (store && store.timer) clearTimeout(store.timer);\n      if (store && store.retry) clearTimeout(store.retry);\n      const u = store && store.unsub;\n      if (u) { try { u(); } catch (e) { /* connection already closed */ } }\n    }\n    this._fc = {};\n  }""",
    """  _clearDataCaches() {\n    this._hist = {};\n    for (const k of Object.keys(this._fc || {})) {\n      const store = this._fc[k];\n      if (store && store.timer) clearTimeout(store.timer);\n      if (store && store.retry) clearTimeout(store.retry);\n      const u = store && store.unsub;\n      if (u) { try { u(); } catch (e) { /* connection already closed */ } }\n    }\n    this._fc = {};\n  }\n\n  disconnectedCallback() {\n    this._clearDataCaches();\n  }""",
)

replace_once(JS, "entity_temperature_change: 'temperature_change',", "entity_temperature_change: 'migraine_temperature_change_6h',")

replace_once(
    JS,
    """  setConfig(config) {\n    // No required entities — card shows what's configured\n    this._config = { ...config };""",
    """  setConfig(config) {\n    // No required entities — card shows what's configured. If an editor change\n    // points the card at different data sources, dispose old forecast sockets\n    // and history so stale data cannot leak into the new configuration.\n    const previous = this._config;\n    const next = { ...config };\n    const sourceKeys = FACTOR_KEYS.map(k => FACTORS[k].configKey)\n      .concat(['entity_forecast', 'entity_risk_score', 'entity_risk_level']);\n    if (previous && sourceKeys.some(k => previous[k] !== next[k])) this._clearDataCaches();\n    this._config = next;""",
)

replace_once(
    JS,
    "s += ';' + (a.temperature ?? '') + ';' + (a.humidity ?? '') + ';' + (a.wind_speed ?? '') + ';' + (a.uv_index ?? '');",
    "s += ';' + (a.temperature ?? '') + ';' + (a.humidity ?? '') + ';' + (a.pressure ?? '') + ';' + (a.wind_speed ?? '') + ';' + (a.uv_index ?? '') + ';' + (a.temperature_unit ?? '') + ';' + (a.pressure_unit ?? '') + ';' + (a.wind_speed_unit ?? '') + ';' + (a.supported_features ?? '');",
)

replace_once(JS, "const level = thunderLevelFromHourly(fc);", "const level = thunderLevelFromHourly(fc, this._hass?.config?.time_zone);")

replace_once(
    JS,
    """        // series.ts is when the history was sampled; anchoring the window to it\n        // keeps the result stable between renders instead of drifting with the clock\n        const val = mode === 'pressure'""",
    """        if (series.noData || series.points.length === 0) {\n          return { score: null, display: null, unit, unavailable: true };\n        }\n        // series.ts is when the history was sampled; anchoring the window to it\n        // keeps the result stable between renders instead of drifting with the clock\n        const val = mode === 'pressure'""",
)
replace_once(
    JS,
    "if (val == null) return { score: null, display: null, unit, pending: true };",
    "if (val == null) return { score: null, display: null, unit, unavailable: true };",
)

replace_once(
    JS,
    "`history/period/${start}?end_time=${encodeURIComponent(end)}&filter_entity_id=${eid}`",
    "`history/period/${start}?end_time=${encodeURIComponent(end)}&filter_entity_id=${encodeURIComponent(eid)}&significant_changes_only=0`",
)
replace_once(JS, "const t = new Date(s.last_changed || s.last_updated).getTime();", "const t = new Date(s.last_updated || s.last_changed).getTime();")
replace_once(
    JS,
    "this._hist[key] = { ts: Date.now(), points, fetching: false };",
    "this._hist[key] = { ts: Date.now(), points, fetching: false, noData: points.length === 0 };",
)
replace_once(
    JS,
    """      this._hist[key] = {\n        ts: Date.now(),\n        points: cached ? cached.points : null,\n        fetching: false,\n        failed: !(cached && cached.points),\n      };""",
    """      const hasStale = !!(cached && cached.points && cached.points.length);\n      this._hist[key] = {\n        ts: Date.now(),\n        points: hasStale ? cached.points : null,\n        fetching: false,\n        failed: !hasStale,\n        noData: !hasStale,\n      };""",
)

replace_once(JS, "const resp = (res && (res.response || res.result)) || {};", "const resp = (res && (res.response || res.result)) || res || {};")

replace_once(
    JS,
    """    const entity = this._hass.states[fid];\n    if (!entity) return;""",
    """    const entity = this._hass.states[fid];\n    if (!entity) {\n      const existing = card.querySelector('.forecast');\n      if (existing) existing.remove();\n      return;\n    }""",
)

replace_once(
    JS,
    """    const eid = entity.entity_id;\n    let data = null;\n    let daily = null;""",
    """    const eid = entity.entity_id;\n    const timeZone = this._hass?.config?.time_zone;\n    let data = null;\n    let daily = null;""",
)
replace_once(JS, "data = tomorrowFromForecast(daily, false);", "data = tomorrowFromForecast(daily, false, timeZone);")
replace_once(JS, "data = tomorrowFromForecast(hourly, true);", "data = tomorrowFromForecast(hourly, true, timeZone);")
replace_once(
    JS,
    "const pts = scoreTomorrow(data, a.wind_speed_unit, resolveThresholds(this._hass, this._config));",
    "const pts = scoreTomorrow(data, a.wind_speed_unit, a.temperature_unit, resolveThresholds(this._hass, this._config));",
)

replace_once(
    JS,
    """    const titleEl = document.createElement('div');\n    titleEl.className = 'section-title';\n    titleEl.innerHTML = `<ha-icon icon=\"${icon}\"></ha-icon> ${title}`;\n    section.appendChild(titleEl);""",
    """    const titleEl = document.createElement('div');\n    titleEl.className = 'section-title';\n    const titleIcon = document.createElement('ha-icon');\n    titleIcon.setAttribute('icon', icon);\n    titleEl.appendChild(titleIcon);\n    titleEl.appendChild(document.createTextNode(' ' + title));\n    section.appendChild(titleEl);""",
)

replace_once(
    JS,
    """customElements.define('migraine-risk-card', MigraineRiskCard);\ncustomElements.define('migraine-risk-card-editor', MigraineRiskCardEditor);\n\nwindow.customCards = window.customCards || [];\nwindow.customCards.push({\n  type: 'migraine-risk-card',\n  name: 'Migraine Risk Card',\n  description: 'Science-backed migraine risk visualisation with real-time factor tracking and forecasting.',\n  preview: false,\n});""",
    """if (!customElements.get('migraine-risk-card')) {\n  customElements.define('migraine-risk-card', MigraineRiskCard);\n}\nif (!customElements.get('migraine-risk-card-editor')) {\n  customElements.define('migraine-risk-card-editor', MigraineRiskCardEditor);\n}\n\nwindow.customCards = window.customCards || [];\nif (!window.customCards.some(card => card.type === 'migraine-risk-card')) {\n  window.customCards.push({\n    type: 'migraine-risk-card',\n    name: 'Migraine Risk Card',\n    description: 'Science-backed migraine risk visualisation with real-time factor tracking and forecasting.',\n    preview: false,\n  });\n}""",
)

# dist is a release artifact and must stay byte-for-byte in sync with src.
write("dist/migraine-risk-card.js", read(JS))


# ---------------------------------------------------------------------------
# Compatibility sensor package. v3.x does not require this package; keep it
# correct for legacy/server-side users without making it a dependency.
# ---------------------------------------------------------------------------
PKG = "sensor-package/migraine_sensors.yaml"

replace_all_checked(PKG, "    min: 900\n    max: 1100", "    min: 300\n    max: 1100", 2)
replace_once(PKG, "    min: -20\n    max: 60", "    min: -60\n    max: 70")

replace_once(
    PKG,
    """          {% macro to_celsius(v, source_entity=None) %}\n            {% set f = v | float(0) %}\n            {% set unit = state_attr(source_entity, 'unit_of_measurement') if source_entity else None %}\n            {% if unit in ['°F','F','fahrenheit'] or (unit is none and f > 50) %}\n              {{ ((f - 32) * 5 / 9) | round(2) }}\n            {% else %}\n              {{ f }}\n            {% endif %}\n          {% endmacro %}""",
    """          {% macro to_celsius(v, source_entity=None) %}\n            {% set f = v | float(0) %}\n            {% set unit = state_attr(source_entity, 'unit_of_measurement') if source_entity else state_attr(weather_entity, 'temperature_unit') %}\n            {% set u = unit | string | lower if unit is not none else '' %}\n            {% if u in ['°f','f','fahrenheit'] %}\n              {{ ((f - 32) * 5 / 9) | round(2) }}\n            {% else %}\n              {{ f }}\n            {% endif %}\n          {% endmacro %}""",
)

replace_once(
    PKG,
    """      - name: \"Migraine Pressure (hPa)\"\n        unique_id: migraine_pressure_hpa\n        state: >""",
    """      - name: \"Migraine Pressure (hPa)\"\n        unique_id: migraine_pressure_hpa\n        availability: >\n          {% set weather_entity = states('input_text.migraine_source_weather') %}\n          {% set pres_entity = states('input_text.migraine_source_pressure') %}\n          {% set direct_ok = pres_entity not in ['not_configured','unknown','unavailable','',none]\n             and states(pres_entity) not in ['unknown','unavailable','',none]\n             and states(pres_entity) | float(none) is not none %}\n          {% set weather_ok = weather_entity not in ['not_configured','unknown','unavailable','',none]\n             and state_attr(weather_entity, 'pressure') is number %}\n          {{ direct_ok or weather_ok }}\n        state: >""",
)

replace_once(
    PKG,
    """          {% macro to_hpa(v) %}\n            {% set f = v | float(0) %}\n            {% if f >= 25 and f <= 33 %}\n              {{ (f * 33.8639) | round(2) }}\n            {% elif f >= 600 and f <= 825 %}\n              {{ (f * 1.33322) | round(2) }}\n            {% else %}\n              {{ f }}\n            {% endif %}\n          {% endmacro %}""",
    """          {% macro to_hpa(v, source_entity=None) %}\n            {% set f = v | float(0) %}\n            {% set unit = state_attr(source_entity, 'unit_of_measurement') if source_entity else state_attr(weather_entity, 'pressure_unit') %}\n            {% set u = unit | string | lower | replace(' ', '') if unit is not none else '' %}\n            {% if u in ['inhg'] %}\n              {{ (f * 33.8639) | round(2) }}\n            {% elif u in ['mmhg','ммрт.ст.','ммртст'] %}\n              {{ (f * 1.33322) | round(2) }}\n            {% elif u in ['kpa','кпа'] %}\n              {{ (f * 10) | round(2) }}\n            {% elif u == 'psi' %}\n              {{ (f * 68.9476) | round(2) }}\n            {% elif not u and f >= 25 and f <= 33 %}\n              {{ (f * 33.8639) | round(2) }}\n            {% elif not u and f >= 600 and f <= 825 %}\n              {{ (f * 1.33322) | round(2) }}\n            {% elif not u and f >= 80 and f <= 120 %}\n              {{ (f * 10) | round(2) }}\n            {% else %}\n              {{ f }}\n            {% endif %}\n          {% endmacro %}""",
)
replace_once(PKG, "{{ to_hpa(v) | trim }}", "{{ to_hpa(v, pres_entity) | trim }}")

# Add real rolling windows backed by Home Assistant's statistics integration.
replace_once(
    PKG,
    """###############################################################################\n# TEMPLATE SENSORS\n###############################################################################\n\ntemplate:""",
    """###############################################################################\n# ROLLING-WINDOW STATISTICS\n# v3.4 replaces the old 6h/24h reset automations with true max_age windows.\n# The statistics integration restores its buffer from Recorder on startup.\n###############################################################################\n\nsensor:\n  - platform: statistics\n    name: \"Migraine Pressure Peak 6h Rolling\"\n    unique_id: migraine_pressure_peak_6h_rolling\n    entity_id: sensor.migraine_pressure_hpa\n    state_characteristic: value_max\n    max_age:\n      hours: 6\n    precision: 2\n\n  - platform: statistics\n    name: \"Migraine Pressure Peak 24h Rolling\"\n    unique_id: migraine_pressure_peak_24h_rolling\n    entity_id: sensor.migraine_pressure_hpa\n    state_characteristic: value_max\n    max_age:\n      hours: 24\n    precision: 2\n\n  - platform: statistics\n    name: \"Migraine Temperature Change 6h Rolling\"\n    unique_id: migraine_temperature_change_6h_rolling\n    entity_id: sensor.migraine_temperature\n    state_characteristic: change\n    max_age:\n      hours: 6\n    precision: 2\n\n\n###############################################################################\n# TEMPLATE SENSORS\n###############################################################################\n\ntemplate:""",
)

# Pressure deltas: no pressure device_class (these are deltas, not absolute pressure).
replace_once(
    PKG,
    """      - name: Migraine Pressure Drop (6h)\n        unique_id: migraine_pressure_drop_6h\n        unit_of_measurement: \"hPa\"\n        device_class: pressure\n        state_class: measurement\n        availability: >\n          {{ states('sensor.migraine_pressure_hpa') not in ['unknown','unavailable','',none]\n             and states('sensor.migraine_pressure_hpa') | float(0) > 900 }}\n        state: >\n          {% set current = states('sensor.migraine_pressure_hpa') | float(0) %}\n          {% set peak_6h = states('input_number.pressure_6h_peak') | float(0) %}\n          {% set drop = peak_6h - current %}\n          {{ [drop, 0] | max | round(1) }}\n        icon: mdi:trending-down\n        attributes:\n          current_pressure: \"{{ states('sensor.migraine_pressure_hpa') }}\"\n          peak_pressure_6h: \"{{ states('input_number.pressure_6h_peak') }}\"""",
    """      - name: Migraine Pressure Drop (6h)\n        unique_id: migraine_pressure_drop_6h\n        unit_of_measurement: \"hPa\"\n        state_class: measurement\n        availability: >\n          {{ states('sensor.migraine_pressure_hpa') not in ['unknown','unavailable','',none]\n             and states('sensor.migraine_pressure_hpa') | float(0) > 300\n             and states('sensor.migraine_pressure_peak_6h_rolling') not in ['unknown','unavailable','',none] }}\n        state: >\n          {% set current = states('sensor.migraine_pressure_hpa') | float(0) %}\n          {% set peak_6h = states('sensor.migraine_pressure_peak_6h_rolling') | float(0) %}\n          {% set drop = peak_6h - current %}\n          {{ [drop, 0] | max | round(1) }}\n        icon: mdi:trending-down\n        attributes:\n          current_pressure: \"{{ states('sensor.migraine_pressure_hpa') }}\"\n          peak_pressure_6h: \"{{ states('sensor.migraine_pressure_peak_6h_rolling') }}\"""",
)

replace_once(
    PKG,
    """      - name: Migraine Pressure Drop (24h)\n        unique_id: migraine_pressure_drop_24h\n        unit_of_measurement: \"hPa\"\n        device_class: pressure\n        state_class: measurement\n        availability: >\n          {{ states('sensor.migraine_pressure_hpa') not in ['unknown','unavailable','',none]\n             and states('sensor.migraine_pressure_hpa') | float(0) > 900 }}\n        state: >\n          {% set current = states('sensor.migraine_pressure_hpa') | float(0) %}\n          {% set peak_24h = states('input_number.pressure_24h_peak') | float(0) %}\n          {% set drop = peak_24h - current %}\n          {{ [drop, 0] | max | round(1) }}\n        icon: mdi:trending-down\n        attributes:\n          current_pressure: \"{{ states('sensor.migraine_pressure_hpa') }}\"\n          peak_pressure_24h: \"{{ states('input_number.pressure_24h_peak') }}\"""",
    """      - name: Migraine Pressure Drop (24h)\n        unique_id: migraine_pressure_drop_24h\n        unit_of_measurement: \"hPa\"\n        state_class: measurement\n        availability: >\n          {{ states('sensor.migraine_pressure_hpa') not in ['unknown','unavailable','',none]\n             and states('sensor.migraine_pressure_hpa') | float(0) > 300\n             and states('sensor.migraine_pressure_peak_24h_rolling') not in ['unknown','unavailable','',none] }}\n        state: >\n          {% set current = states('sensor.migraine_pressure_hpa') | float(0) %}\n          {% set peak_24h = states('sensor.migraine_pressure_peak_24h_rolling') | float(0) %}\n          {% set drop = peak_24h - current %}\n          {{ [drop, 0] | max | round(1) }}\n        icon: mdi:trending-down\n        attributes:\n          current_pressure: \"{{ states('sensor.migraine_pressure_hpa') }}\"\n          peak_pressure_24h: \"{{ states('sensor.migraine_pressure_peak_24h_rolling') }}\"""",
)

replace_once(
    PKG,
    """      - name: \"Migraine Temperature Change (6h)\"\n        unique_id: migraine_temperature_change_6h\n        unit_of_measurement: \"°C\"\n        device_class: temperature\n        state_class: measurement\n        availability: >\n          {{ states('sensor.migraine_temperature') not in ['unknown','unavailable','',none]\n             and states('input_number.temperature_6h_reset_time') | int(0) != 0 }}\n        state: >\n          {% set current = states('sensor.migraine_temperature') | float(0) %}\n          {% set baseline = states('input_number.temperature_6h_baseline') | float(0) %}\n          {{ (current - baseline) | abs | round(1) }}\n        icon: mdi:thermometer-chevron-up\n        attributes:\n          current_temp: \"{{ states('sensor.migraine_temperature') }}\"\n          baseline_temp_6h: \"{{ states('input_number.temperature_6h_baseline') }}\"\n          direction: >\n            {% set current = states('sensor.migraine_temperature') | float(0) %}\n            {% set baseline = states('input_number.temperature_6h_baseline') | float(0) %}\n            {% if current > baseline + 0.5 %}\n              Rising\n            {% elif current < baseline - 0.5 %}\n              Falling\n            {% else %}\n              Stable\n            {% endif %}""",
    """      - name: \"Migraine Temperature Change (6h)\"\n        unique_id: migraine_temperature_change_6h\n        unit_of_measurement: \"°C\"\n        state_class: measurement\n        availability: >\n          {{ states('sensor.migraine_temperature') not in ['unknown','unavailable','',none]\n             and states('sensor.migraine_temperature_change_6h_rolling') not in ['unknown','unavailable','',none] }}\n        state: >\n          {{ states('sensor.migraine_temperature_change_6h_rolling') | float(0) | abs | round(1) }}\n        icon: mdi:thermometer-chevron-up\n        attributes:\n          current_temp: \"{{ states('sensor.migraine_temperature') }}\"\n          signed_change_6h: \"{{ states('sensor.migraine_temperature_change_6h_rolling') }}\"\n          direction: >\n            {% set change = states('sensor.migraine_temperature_change_6h_rolling') | float(0) %}\n            {% if change > 0.5 %}\n              Rising\n            {% elif change < -0.5 %}\n              Falling\n            {% else %}\n              Stable\n            {% endif %}""",
)

# Normalise tomorrow's forecast temperatures from the weather entity's declared units.
replace_once(
    PKG,
    """          # Wind normalised to km/h for scoring\n          tomorrow_wind_kmh: >""",
    """          # Temperatures normalised to °C for scoring and package attributes\n          tomorrow_temp_max_c: >\n            {% set v = tomorrow_entry.get('temperature') %}\n            {% set u = state_attr(weather_entity, 'temperature_unit') | default('°C', true) | lower %}\n            {% if v is none %}\n              {{ none }}\n            {% elif u in ['°f','f','fahrenheit'] %}\n              {{ (((v | float(0)) - 32) * 5 / 9) | round(2) }}\n            {% else %}\n              {{ v | float(0) }}\n            {% endif %}\n          tomorrow_temp_min_c: >\n            {% set v = tomorrow_entry.get('templow') %}\n            {% set u = state_attr(weather_entity, 'temperature_unit') | default('°C', true) | lower %}\n            {% if v is none %}\n              {{ none }}\n            {% elif u in ['°f','f','fahrenheit'] %}\n              {{ (((v | float(0)) - 32) * 5 / 9) | round(2) }}\n            {% else %}\n              {{ v | float(0) }}\n            {% endif %}\n          # Wind normalised to km/h for scoring\n          tomorrow_wind_kmh: >""",
)
replace_once(PKG, "temp_max: \"{{ tomorrow_entry.get('temperature') }}\"", "temp_max: \"{{ tomorrow_temp_max_c }}\"")
replace_once(PKG, "temp_min: \"{{ tomorrow_entry.get('templow') }}\"", "temp_min: \"{{ tomorrow_temp_min_c }}\"")
replace_once(PKG, "states('sensor.migraine_factor_thunderstorm_nearby') | int >= 2", "states('sensor.migraine_factor_thunderstorm_nearby') | int(0) >= 2")

# Remove obsolete tumbling-window automations. Deprecated helpers remain defined
# so existing legacy dashboards/automations do not fail immediately after upgrade.
text = read(PKG)
marker = "\n###############################################################################\n# AUTOMATIONS — Pressure & Temperature Baseline Tracking\n"
idx = text.find(marker)
if idx < 0:
    raise RuntimeError("Legacy tracking automation marker not found")
text = text[:idx] + """\n###############################################################################\n# v3.4 NOTE — legacy tracking helpers\n# pressure_*_peak/reset_time and temperature_6h_* helpers above are retained\n# for backward compatibility only. Rolling calculations now use Statistics\n# sensors and require no reset automation.\n###############################################################################\n"""
write(PKG, text)


# ---------------------------------------------------------------------------
# README / repository hygiene / CI
# ---------------------------------------------------------------------------
README = "README.md"
replace_once(README, "## What's New in 3.0", """## What's New in 3.4\n\n**3.4.0 is a quality/reliability release for the standalone v3.x card.** It fixes hidden edge cases without changing the scoring model:\n\n- Weather-entity pressure and temperature history now includes attribute-only Recorder updates and uses their real update timestamps.\n- Pressure-only `weather.*` updates trigger a card refresh instead of waiting for an unrelated state change.\n- Tomorrow scoring normalises °F to °C while keeping the source unit for display.\n- Forecast day selection follows the Home Assistant timezone rather than the browser timezone.\n- Missing/insufficient Recorder history is shown as unavailable instead of an endless loading indicator.\n- Translation loading, config-source changes, duplicate resource registration, and stale forecast UI paths are hardened.\n- The optional compatibility sensor package now uses true rolling Statistics windows and unit-aware pressure/temperature conversion.\n- Regression tests cover the pure scoring/conversion/date helpers and critical source-code invariants.\n\n## What's New in 3.0""")
replace_once(README, "`🧠 Migraine Risk Card v3.2.0`", "`🧠 Migraine Risk Card v3.4.0`")
replace_once(README, "`theme` | `auto` \\| `dark' \\| `light`", "`theme` | `auto` \\| `dark` \\| `light`")
replace_once(
    README,
    "If a change factor shows `…` forever, check your `recorder:` `exclude:` config.",
    "If a change factor shows `—`, check your `recorder:` `exclude:` config and make sure the source has enough recorded history.",
)
replace_once(
    README,
    "The bundled `sensor-package/migraine_sensors.yaml` reproduces the scoring **server-side** and adds things the card can't do on its own: notifications and automations, history you can graph, and WAQI air-quality sensors (AQI/PM2.5/PM10/ozone). It's entirely optional in 3.0.",
    "Starting with v3.0, the card does **not** use `sensor-package/migraine_sensors.yaml` as its backend. The package is retained as an optional compatibility/server-side layer for users migrating from 1.x/2.x installations and for users who explicitly want server-side score entities, automations, or WAQI-derived sensors. A normal standalone 3.x installation does not need it. In v3.4 its pressure/temperature windows were also changed to true rolling Statistics windows so legacy package users no longer get reset-boundary discontinuities.",
)

# New translation files under dist/ must be addable by contributors.
gitignore = read(".gitignore")
old = "# Nuxt.js build / generate output\n.nuxt\ndist\n"
if old not in gitignore:
    raise RuntimeError("Expected dist ignore rule not found")
write(".gitignore", gitignore.replace(old, "# Nuxt.js build / generate output\n.nuxt\n", 1))

validate = read(".github/workflows/validate.yml")
if "uses: hacs/action@main" not in validate:
    raise RuntimeError("Unpinned HACS action not found")
validate = validate.replace("uses: hacs/action@main", "uses: hacs/action@22.5.0", 1)
needle = """      - name: Syntax check\n        run: node --check dist/migraine-risk-card.js\n\n      - name: Validate translations"""
replacement = """      - name: Syntax check\n        run: node --check dist/migraine-risk-card.js\n\n      - name: Unit and regression tests\n        run: node tests/test-core.js\n\n      - name: Validate translations"""
if needle not in validate:
    raise RuntimeError("validate.yml syntax-check insertion point not found")
write(".github/workflows/validate.yml", validate.replace(needle, replacement, 1))

hacs_dup = ROOT / ".github/workflows/hacs.yml"
if not hacs_dup.exists():
    raise RuntimeError("Duplicate hacs.yml not found")
hacs_dup.unlink()


# ---------------------------------------------------------------------------
# Node-only tests: evaluate the pure-function prefix without DOM custom elements.
# ---------------------------------------------------------------------------
TEST = r'''const assert = require('node:assert/strict');
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
assert(source.includes("entity_temperature_change: 'migraine_temperature_change_6h'"), 'stub config must prefer the delta sensor');
assert(source.includes("if (!customElements.get('migraine-risk-card'))"), 'duplicate resource registration must be guarded');

console.log('All migraine-risk-card core tests passed.');
'''
write("tests/test-core.js", TEST)


RELEASE_NOTES = """# Migraine Risk Card 3.4.0 — Quality / Reliability\n\nThis release keeps the v3 scoring model unchanged and focuses on hidden correctness and lifecycle edge cases.\n\n## Standalone card\n\n- Fixed Recorder history for `weather.*` pressure/temperature attributes by requesting non-significant updates and timestamping them with `last_updated`.\n- Added pressure and weather-unit attributes to the render hash, so pressure-only updates repaint immediately.\n- Normalised Fahrenheit forecast temperatures before tomorrow scoring.\n- Made forecast day selection use the Home Assistant timezone.\n- Replaced endless history loading with a clear unavailable state when Recorder data is insufficient.\n- Hardened translation loading for multiple cards and transient failures.\n- Cleaned old history/forecast subscriptions when editor source entities change.\n- Removed stale forecast UI when a configured forecast entity disappears.\n- Recognised `storm` / `thunderstorm` current weather conditions.\n- Guarded duplicate custom-element/resource registration.\n- Removed translated editor HTML injection.\n\n## Optional compatibility sensor package\n\nThe package remains optional and is not used by the standalone v3.x card. For users who still rely on it:\n\n- Replaced reset-based pressure/temperature tracking with true rolling Statistics windows.\n- Added unit-aware °F/°C and kPa/mmHg/inHg/psi/hPa conversion.\n- Added support for lower station pressure at altitude.\n- Removed absolute pressure/temperature device classes from delta sensors.\n- Normalised tomorrow forecast temperatures to °C before scoring.\n\n## Project quality\n\n- Added Node regression tests for conversions, rolling calculations, forecast scoring, timezone handling and critical HA API invariants.\n- Stopped ignoring new `dist/` files in `.gitignore`.\n- Consolidated HACS validation into one pinned workflow.\n- Updated README version and compatibility wording.\n"""
write("RELEASE_NOTES_3.4.0.md", RELEASE_NOTES)

# The preparation machinery is intentionally absent from the resulting release tree.
for temp in [ROOT / "scripts/prepare_3_4_0.py", ROOT / ".github/workflows/prepare-3.4.0.yml"]:
    if temp.exists():
        temp.unlink()

print("3.4.0 tree prepared")
