from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, text):
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path, old, new):
    text = read(path)
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


JS = "src/migraine-risk-card.js"

replace_once(JS, "const FORECAST_RETRY_MS = 60000;   // a failed forecast is retried, not abandoned\nconst FORECAST_MAX_TRIES = 5;",
             "const FORECAST_RETRY_MS = 60000;   // quick retries for transient failures\nconst FORECAST_RECOVERY_MS = 15 * 60e3; // keep self-healing after the quick retry budget\nconst FORECAST_MAX_TRIES = 5;")
replace_once(JS, "case 'kn': case 'knots': return v * 1.852;", "case 'kn': case 'kt': case 'knots': return v * 1.852;")

replace_once(JS,
"""    if (entity && key === 'thunderstorm' && entity.entity_id.startsWith('weather.')) {\n      const fc = this._ensureForecast(entity.entity_id, 'hourly');\n      if (fc && fc.length) {\n        const level = thunderLevelFromHourly(fc, this._hass?.config?.time_zone);\n        return { score: level, display: level, unit: '' };\n      }\n      // No forecast (yet) — fall through to current-condition detection\n    }""",
"""    if (entity && key === 'thunderstorm' && entity.entity_id.startsWith('weather.')) {\n      if (supportsForecast(entity, 'hourly')) {\n        const fc = this._ensureForecast(entity.entity_id, 'hourly');\n        if (fc && fc.length) {\n          const level = thunderLevelFromHourly(fc, this._hass?.config?.time_zone);\n          return { score: level, display: level, unit: '' };\n        }\n      }\n      // No usable hourly forecast (yet) — fall through to current-condition detection\n    }""")

replace_once(JS,
"""  // Live forecast via weather/subscribe_forecast (how the built-in weather\n  // card works), with a one-shot weather.get_forecasts fallback.\n  // Returns the current forecast array or null while pending.\n  // Live forecast via weather/subscribe_forecast (how the built-in weather\n  // card works). If the subscription fails or stays silent, fall back to a\n  // one-shot execute_script call and keep retrying on a timer instead of\n  // giving up after a single miss.\n  // Returns the forecast array, or null while pending.""",
"""  // Live forecast via weather/subscribe_forecast (how the built-in weather\n  // card works). If the subscription fails or stays silent, fall back to a\n  // one-shot weather.get_forecasts service call and keep retrying.\n  // Returns the forecast array, or null while pending.""")

replace_once(JS,
"""  // Fallback: execute_script is the supported way for the frontend to call a\n  // service and read its response (a raw call_service with return_response is\n  // rejected by the server).\n  // One-shot read of the current forecast. `opportunistic` means a live\n  // subscription is also in flight, so a failure here is not fatal — it just\n  // means we keep waiting for the subscription's first push.""",
"""  // One-shot read of the current forecast. Home Assistant's websocket\n  // call_service command has supported response-returning services since before\n  // our minimum HA 2024.6, and unlike execute_script it is not admin-only.\n  // `opportunistic` means a live subscription is also in flight, so a failure\n  // here is not fatal — it just means we keep waiting for its first push.""")

replace_once(JS,
"""    conn.sendMessagePromise({\n      type: 'execute_script',\n      sequence: [{\n        service: 'weather.get_forecasts',\n        data: { type },\n        target: { entity_id: eid },\n        response_variable: 'result',\n      }, {\n        stop: 'done',\n        response_variable: 'result',\n      }],\n    }).then(res => {\n      const s = this._fc[key];\n      if (s) s.fetching = false;\n      // execute_script wraps the service response; shapes differ across HA\n      // versions, so accept the documented one and the plain variants.\n      const resp = (res && (res.response || res.result)) || res || {};\n      const holder = resp[eid] || (resp.result && resp.result[eid]) || resp;""",
"""    conn.sendMessagePromise({\n      type: 'call_service',\n      domain: 'weather',\n      service: 'get_forecasts',\n      service_data: { type },\n      target: { entity_id: eid },\n      return_response: true,\n    }).then(res => {\n      const s = this._fc[key];\n      if (s) s.fetching = false;\n      const resp = (res && res.response) || {};\n      const holder = resp[eid] || resp;""")

replace_once(JS,
"""    // Retry rather than staying stuck until the page is reloaded\n    if ((store.tries || 0) < FORECAST_MAX_TRIES && !store.retry) {\n      store.retry = setTimeout(() => {\n        const s = this._fc[key];\n        if (!s) return;\n        s.retry = null;\n        s.fetched = false;\n        s.fetching = false;\n        if (s.unsub) { try { s.unsub(); } catch (e) { /* already closed */ } s.unsub = null; }\n        this._forecastAttempt(eid, type);\n      }, FORECAST_RETRY_MS);\n    }""",
"""    // Retry quickly a few times, then keep a low-frequency recovery loop so\n    // transient HA/provider outages can self-heal without a browser refresh.\n    if (!store.retry) {\n      const exhausted = (store.tries || 0) >= FORECAST_MAX_TRIES;\n      store.retry = setTimeout(() => {\n        const s = this._fc[key];\n        if (!s) return;\n        s.retry = null;\n        s.fetched = false;\n        s.fetching = false;\n        if (exhausted) s.tries = 0;\n        if (s.unsub) { try { s.unsub(); } catch (e) { /* already closed */ } s.unsub = null; }\n        this._forecastAttempt(eid, type);\n      }, exhausted ? FORECAST_RECOVERY_MS : FORECAST_RETRY_MS);\n    }""")

write("dist/migraine-risk-card.js", read(JS))

# Compatibility package: finish unit/error handling without changing standalone behavior.
PKG = "sensor-package/migraine_sensors.yaml"
replace_once(PKG,
"""          {% set helper_tmax = states(tmax_entity) | float(none) if tmax_entity not in ['not_configured','unknown','unavailable','',none] else none %}\n          {% set helper_tmin = states(tmin_entity) | float(none) if tmin_entity not in ['not_configured','unknown','unavailable','',none] else none %}""",
"""          {% set helper_tmax_raw = states(tmax_entity) | float(none) if tmax_entity not in ['not_configured','unknown','unavailable','',none] else none %}\n          {% set helper_tmin_raw = states(tmin_entity) | float(none) if tmin_entity not in ['not_configured','unknown','unavailable','',none] else none %}\n          {% set tmax_unit = state_attr(tmax_entity, 'unit_of_measurement') | lower if tmax_entity not in ['not_configured','unknown','unavailable','',none] and state_attr(tmax_entity, 'unit_of_measurement') is not none else '' %}\n          {% set tmin_unit = state_attr(tmin_entity, 'unit_of_measurement') | lower if tmin_entity not in ['not_configured','unknown','unavailable','',none] and state_attr(tmin_entity, 'unit_of_measurement') is not none else '' %}\n          {% set helper_tmax = ((helper_tmax_raw - 32) * 5 / 9) if helper_tmax_raw is not none and tmax_unit in ['°f','f','fahrenheit'] else helper_tmax_raw %}\n          {% set helper_tmin = ((helper_tmin_raw - 32) * 5 / 9) if helper_tmin_raw is not none and tmin_unit in ['°f','f','fahrenheit'] else helper_tmin_raw %}""")
replace_once(PKG,
"""              {% elif 'mph' in u %}\n                {{ (v | float(0)) * 1.60934 }}\n              {% else %}""",
"""              {% elif 'mph' in u %}\n                {{ (v | float(0)) * 1.60934 }}\n              {% elif u in ['kn','kt','knots'] %}\n                {{ (v | float(0)) * 1.852 }}\n              {% else %}""")
replace_once(PKG,
"""        availability: >\n          {{ states('sensor.migraine_pressure_hpa') not in ['unknown','unavailable','',none] }}\n        state: >""",
"""        availability: >\n          {{ states('sensor.migraine_pressure_hpa') not in ['unknown','unavailable','',none]\n             and states('sensor.migraine_pressure_drop_6h') not in ['unknown','unavailable','',none]\n             and states('sensor.migraine_pressure_drop_24h') not in ['unknown','unavailable','',none] }}\n        state: >""",)
replace_once(PKG,
"""      - name: Migraine Risk Level\n        unique_id: migraine_risk_level\n        state: >""",
"""      - name: Migraine Risk Level\n        unique_id: migraine_risk_level\n        availability: >\n          {{ states('sensor.migraine_risk_score') not in ['unknown','unavailable','',none] }}\n        state: >""")
replace_once(PKG,
"""      - name: Migraine Risk Warning\n        unique_id: migraine_risk_warning\n        device_class: problem\n        state: \"{{ states('sensor.migraine_risk_score') | int >= 8 }}\"""",
"""      - name: Migraine Risk Warning\n        unique_id: migraine_risk_warning\n        device_class: problem\n        availability: \"{{ states('sensor.migraine_risk_score') not in ['unknown','unavailable','',none] }}\"\n        state: \"{{ states('sensor.migraine_risk_score') | int(0) >= 8 }}\"""")

# Tests: lock in non-admin-compatible forecast fallback and knot conversion.
TEST = "tests/test-core.js"
replace_once(TEST, "close(m.windToKmh(10, 'm/s'), 36);", "close(m.windToKmh(10, 'm/s'), 36);\nclose(m.windToKmh(10, 'kt'), 18.52);")
replace_once(TEST,
"""assert(source.includes(\"if (!customElements.get('migraine-risk-card'))\"), 'duplicate resource registration must be guarded');""",
"""assert(source.includes(\"if (!customElements.get('migraine-risk-card'))\"), 'duplicate resource registration must be guarded');\nassert(source.includes(\"type: 'call_service'\"), 'forecast fallback must use non-admin websocket call_service');\nassert(!source.includes(\"type: 'execute_script'\"), 'forecast fallback must not require admin-only execute_script');\nassert(source.includes('FORECAST_RECOVERY_MS'), 'forecast failures must retain a long-term recovery path');""")

NOTES = "RELEASE_NOTES_3.4.0.md"
replace_once(NOTES,
"- Hardened translation loading for multiple cards and transient failures.\n",
"- Hardened translation loading for multiple cards and transient failures.\n- Switched the one-shot forecast fallback from admin-only `execute_script` to response-capable `call_service` (supported by the minimum HA 2024.6) and added long-term recovery retries.\n")
replace_once(NOTES,
"- Normalised tomorrow forecast temperatures to °C before scoring.\n",
"- Normalised tomorrow forecast temperatures to °C before scoring, including legacy helper-sensor inputs.\n- Propagated pressure/risk unavailability instead of presenting a false `Low` state when required pressure data is missing.\n")

print('final reliability patch applied')
