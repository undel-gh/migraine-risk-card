from pathlib import Path

SRC = Path('src/migraine-risk-card.js')
text = SRC.read_text()

old_header = """ * Works two ways:\n *   1. With the Migraine Risk custom integration (auto-detected)\n *   2. Standalone — point it at any weather entities and the card\n *      computes the risk score internally.\n *\n * All factor entities are optional. The card only shows what you configure.\n"""
new_header = """ * Standalone by default — point it at the weather/sensor entities you choose\n * and the card computes the risk score internally. Pre-computed package or\n * integration entities remain available as an explicit opt-in.\n *\n * All factor entities are optional. The card only shows what you configure.\n"""
if old_header not in text:
    raise SystemExit('header block not found')
text = text.replace(old_header, new_header, 1)

start = text.index('  static getStubConfig(')
end = text.index('\n\n  setConfig(config) {', start)
new_stub = """  static getStubConfig() {\n    // v3.x is standalone-first. Do not guess a user's weather provider,\n    // location, sensor choice, or legacy-package mode from existing entities.\n    // Integration/package entities remain available through explicit editor\n    // configuration, preserving existing cards without silently opting new\n    // cards into a legacy backend.\n    return { type: 'custom:migraine-risk-card' };\n  }"""
text = text[:start] + new_stub + text[end:]
SRC.write_text(text)
Path('dist/migraine-risk-card.js').write_text(text)

TEST = Path('tests/test-core.js')
t = TEST.read_text()
old = """assert(source.includes(\"'sensor.migraine_temperature_change_6h', ['_rolling']\"), 'stub config must prefer the public delta sensor over the rolling helper');\n"""
new = """const stubStart = source.indexOf('  static getStubConfig(');\nconst stubEnd = source.indexOf('\\n\\n  setConfig(config) {', stubStart);\nconst stubConfig = source.slice(stubStart, stubEnd);\nassert(stubConfig.includes(\"return { type: 'custom:migraine-risk-card' };\"), 'new cards must start with an explicit-source stub');\nassert(!stubConfig.includes('Object.keys('), 'stub config must not enumerate Home Assistant entities');\nassert(!stubConfig.includes('const find ='), 'stub config must not guess source entities');\nassert(!stubConfig.includes('sensor.migraine_'), 'stub config must not silently opt into legacy package entities');\n"""
if old not in t:
    raise SystemExit('old stub regression assertion not found')
t = t.replace(old, new, 1)
TEST.write_text(t)

README = Path('README.md')
r = README.read_text()
needle = """Starting with v3.0, the card does **not** use `sensor-package/migraine_sensors.yaml` as its backend. The package is retained as an optional compatibility/server-side layer for users migrating from 1.x/2.x installations and for users who explicitly want server-side score entities, automations, or WAQI-derived sensors. A normal standalone 3.x installation does not need it. In v3.4 its pressure/temperature windows were also changed to true rolling Statistics windows so legacy package users no longer get reset-boundary discontinuities.\n"""
addition = needle + """\nWhen adding a new v3.x card, source entities are intentionally **not auto-selected**. Choose the weather provider and/or sensors you actually want in the visual editor. This also prevents entities left behind by a 1.x/2.x sensor-package installation from silently switching a new card into package/integration mode.\n"""
if needle not in r:
    raise SystemExit('README standalone/package paragraph not found')
r = r.replace(needle, addition, 1)
README.write_text(r)

NOTES = Path('RELEASE_NOTES_3.4.0.md')
n = NOTES.read_text()
needle = '- Kept cached translation lookups render-neutral so normal Home Assistant state updates still use the card state-hash short-circuit.\n'
addition = needle + '- New cards no longer auto-detect source or legacy sensor-package entities; source selection and package/integration mode are now explicit user choices.\n'
if needle not in n:
    raise SystemExit('release-note insertion point not found')
NOTES.write_text(n.replace(needle, addition, 1))

print('Explicit-source stub fix applied')
