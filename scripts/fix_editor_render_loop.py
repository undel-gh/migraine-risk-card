from pathlib import Path

SRC = Path('src/migraine-risk-card.js')
text = SRC.read_text()
old = '''  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._rendered = false;
  }

  set hass(hass) {
    const firstHass = !this._hass;
    this._hass = hass;
    if (this._rendered) {
      if (firstHass) {
        // Language comes from hass — re-render once it is known
        this._render();
      } else {
        this.shadowRoot.querySelectorAll('ha-entity-picker').forEach(p => {
          p.hass = hass;
        });
      }
    }
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  _t(path, fallback) {
    const lang = resolveLang(this._hass, this._config);
    loadTranslation(lang, this._config, () => { if (this._rendered) this._render(); });
    return tr(lang, path, fallback);
  }
'''
new = '''  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._rendered = false;
    this._translationRequestKey = null;
  }

  set hass(hass) {
    const firstHass = !this._hass;
    this._hass = hass;
    this._requestTranslation();
    if (this._rendered) {
      if (firstHass) {
        // Language comes from hass — re-render once it is known
        this._render();
      } else {
        this.shadowRoot.querySelectorAll('ha-entity-picker').forEach(p => {
          p.hass = hass;
        });
      }
    }
  }

  setConfig(config) {
    this._config = { ...config };
    this._requestTranslation();
    this._render();
  }

  _requestTranslation() {
    const lang = resolveLang(this._hass, this._config);
    const key = lang + '|' + (this._config.translations_path || '');
    if (this._translationRequestKey === key) return;
    this._translationRequestKey = key;
    loadTranslation(lang, this._config, () => {
      // Translation loading is asynchronous, but rendering itself must stay
      // side-effect-free. In particular, _t() is called dozens of times per
      // render; scheduling another render from there creates an infinite
      // microtask loop once a dictionary is already cached.
      if (this._translationRequestKey === key && this._rendered) this._render();
    });
  }

  _t(path, fallback) {
    return tr(resolveLang(this._hass, this._config), path, fallback);
  }
'''
if old not in text:
    raise SystemExit('editor lifecycle block not found')
text = text.replace(old, new, 1)
SRC.write_text(text)
Path('dist/migraine-risk-card.js').write_text(text)

TEST = Path('tests/test-core.js')
t = TEST.read_text()
needle = '''assert(source.includes("if (!customElements.get('migraine-risk-card'))"), 'duplicate resource registration must be guarded');
'''
addition = needle + '''const editorStart = source.indexOf('class MigraineRiskCardEditor');
const editorTranslation = source.slice(editorStart, source.indexOf('  _render() {', editorStart));
const editorLookup = editorTranslation.slice(editorTranslation.indexOf('  _t(path, fallback)'));
assert(!editorLookup.includes('loadTranslation('), 'editor translation lookup must be side-effect free');
assert(editorTranslation.includes('_requestTranslation()'), 'editor must request translations outside render lookups');
'''
if needle not in t:
    raise SystemExit('test insertion point not found')
t = t.replace(needle, addition, 1)
TEST.write_text(t)

NOTES = Path('RELEASE_NOTES_3.4.0.md')
n = NOTES.read_text()
needle2 = '- Hardened translation loading for multiple cards and transient failures.\n'
replace2 = needle2 + '- Fixed a visual-editor render loop caused by translation callbacks being scheduled from every translated label lookup.\n'
if needle2 not in n:
    raise SystemExit('release notes insertion point not found')
NOTES.write_text(n.replace(needle2, replace2, 1))

print('editor render-loop hotfix applied')
