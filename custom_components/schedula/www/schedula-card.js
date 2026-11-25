/*
 * Schedula card – programmatore settimanale per Home Assistant
 * Interfaccia ispirata alle app dei cronotermostati: settimana a barre,
 * giorno con fasce orarie, editor intervallo e editor impostazioni.
 */
const SCHEDULA_CARD_VERSION = '1.1.1';

const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_SHORT = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'];
const DAY_LONG = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'];
const COLORS = [
  '#FDB48A', '#FF7A75', '#8FD8C0', '#5AB8FF', '#8E8CF8', '#FFD166',
  '#C792EA', '#F5F5F5', '#E53935', '#43A047', '#1E88E5', '#455A64',
];
const ICONS = [
  'mdi:home', 'mdi:fire', 'mdi:snowflake', 'mdi:leaf', 'mdi:weather-night', 'mdi:white-balance-sunny',
  'mdi:lightbulb-on', 'mdi:lightbulb-off', 'mdi:shield-lock', 'mdi:shield-off', 'mdi:shield-home', 'mdi:shield-moon',
  'mdi:power', 'mdi:power-off', 'mdi:fan', 'mdi:water', 'mdi:window-shutter', 'mdi:window-shutter-open',
  'mdi:lock', 'mdi:lock-open-variant', 'mdi:thermometer', 'mdi:briefcase', 'mdi:sofa', 'mdi:bed',
  'mdi:airplane', 'mdi:clock-outline',
];
const NUMBER_DOMAINS = ['climate', 'water_heater', 'input_number', 'number', 'cover'];
const OPTION_DOMAINS = ['input_select', 'select', 'alarm_control_panel', 'lock'];
// Opzioni fisse con etichetta per i domini che hanno stati predefiniti
const FIXED_OPTIONS = {
  alarm_control_panel: [
    ['armed_away', 'Inserito totale'], ['armed_home', 'Inserito in casa'], ['armed_night', 'Inserito notte'],
    ['armed_vacation', 'Inserito vacanza'], ['disarmed', 'Disinserito'],
  ],
  lock: [['locked', 'Chiusa'], ['unlocked', 'Aperta']],
};
const HVAC_LABELS = { '': 'Non modificare', heat: 'Caldo', cool: 'Freddo', heat_cool: 'Caldo/Freddo', auto: 'Auto', dry: 'Deumidifica', fan_only: 'Solo ventola', off: 'Spento' };
const IDLE_DEFAULT = 120; // secondi prima di tornare alla schermata principale

// Testo nero su colori chiari, bianco su colori scuri (alto contrasto)
function contrastColor(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim());
  if (!m) return '#fff';
  const n = parseInt(m[1], 16);
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const L = 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
  return L > 0.3 ? '#000' : '#fff';
}
const DOMAIN_ICONS = {
  climate: 'mdi:home-thermometer', alarm_control_panel: 'mdi:shield-home', lock: 'mdi:lock', water_heater: 'mdi:water-boiler', input_number: 'mdi:ray-vertex',
  number: 'mdi:numeric', cover: 'mdi:window-shutter', light: 'mdi:lightbulb', switch: 'mdi:toggle-switch',
  fan: 'mdi:fan', input_boolean: 'mdi:toggle-switch-outline', select: 'mdi:format-list-bulleted',
  input_select: 'mdi:format-list-bulleted', automation: 'mdi:robot', script: 'mdi:script-text',
};

const pad = (n) => String(n).padStart(2, '0');
const toMin = (s) => {
  if (!s) return 0;
  const [h, m] = String(s).split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
};
const toHHMM = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clone = (o) => JSON.parse(JSON.stringify(o));
const isSchedula = (st) => !!(st && st.attributes && st.attributes.schedule_id && st.attributes.week && st.attributes.presets);
const decimals = (step) => {
  const s = String(step);
  return s.includes('.') ? s.split('.')[1].length : 0;
};

function valueType(entityId) {
  const d = String(entityId || '').split('.')[0];
  if (NUMBER_DOMAINS.includes(d)) return 'number';
  if (OPTION_DOMAINS.includes(d)) return 'option';
  return 'onoff';
}

function slotsToArray(slots, fallback) {
  const arr = new Array(1440).fill(fallback);
  const list = [...(slots || [])].sort((a, b) => toMin(a.start) - toMin(b.start));
  list.forEach((s, i) => {
    const from = toMin(s.start);
    const to = i + 1 < list.length ? toMin(list[i + 1].start) : 1440;
    arr.fill(s.preset, from, to);
  });
  return arr;
}

function arrayToSlots(arr) {
  const out = [];
  for (let m = 0; m < 1440; m++) {
    if (m === 0 || arr[m] !== arr[m - 1]) out.push({ start: toHHMM(m), preset: arr[m] });
  }
  return out;
}

const CSS = `
:host {
  --sc-accent: var(--schedula-accent, #4F87FF);
  --sc-orange: var(--schedula-orange, #FF9A1F);
  --sc-fg: var(--primary-text-color, #fff);
  --sc-muted: var(--secondary-text-color, #9aa0aa);
  --sc-div: var(--divider-color, rgba(255,255,255,.08));
  --sc-surface: var(--schedula-surface, rgba(127,127,127,.14));
  --sc-track: var(--schedula-track, rgba(79,135,255,.16));
  display: block;
}
ha-card { overflow: hidden; position: relative; }
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; padding: 0; }
.wrap { color: var(--sc-fg); font-size: 15px; position: relative; }
.hdr { display: flex; align-items: center; gap: 8px; padding: 14px 10px 12px 12px; border-bottom: 1px solid var(--sc-div); position: relative; }
.icon-btn { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; flex: none; }
.icon-btn:hover { background: var(--sc-surface); }
.hdr-icon { width: 40px; height: 40px; display: grid; place-items: center; color: var(--sc-accent); flex: none; }
.hdr-t { flex: 1; min-width: 0; padding-left: 4px; }
.hdr-t.clickable { cursor: pointer; }
.title { font-size: 1.35em; font-weight: 700; display: flex; align-items: center; gap: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.title .chev { --mdc-icon-size: 22px; flex: none; }
.sub { font-size: .9em; color: var(--sc-accent); margin-top: 2px; }
.sub.off { color: var(--sc-muted); }
.menu { position: absolute; right: 10px; top: 58px; z-index: 5; min-width: 230px; background: var(--card-background-color, #1c1d22);
  border-radius: 12px; box-shadow: 0 8px 28px rgba(0,0,0,.45); padding: 6px 0; border: 1px solid var(--sc-div); }
.menu.left { left: 60px; right: auto; }
.mi { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; }
.mi:hover { background: var(--sc-surface); }
.mi ha-icon { --mdc-icon-size: 20px; color: var(--sc-muted); }
.mi.sel { color: var(--sc-accent); }
.mi.sel ha-icon { color: var(--sc-accent); }

/* settimana */
.day-row { padding: 14px 16px 16px; border-bottom: 1px solid var(--sc-div); cursor: pointer; }
.day-row:hover { background: rgba(127,127,127,.05); }
.day-name { font-weight: 600; font-size: 1.1em; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.today { font-size: .7em; font-weight: 600; color: var(--sc-accent); border: 1px solid var(--sc-accent); border-radius: 10px; padding: 1px 7px; }
.bar { position: relative; display: flex; height: 22px; border-radius: 11px; overflow: hidden; }
.bar.off { opacity: .4; }
.seg { height: 100%; }
.now { position: absolute; top: -2px; bottom: -2px; width: 3px; border-radius: 2px; background: var(--sc-fg); box-shadow: 0 0 0 1px rgba(0,0,0,.35); }
.hours { display: flex; justify-content: space-between; color: var(--sc-muted); font-size: .72em; margin-top: 4px; }
.status { padding: 12px 16px; display: flex; gap: 10px; align-items: center; color: var(--sc-muted); font-size: .9em; border-bottom: 1px solid var(--sc-div); flex-wrap: wrap; }
.status b { color: var(--sc-fg); font-weight: 600; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.link { display: flex; align-items: center; gap: 16px; color: var(--sc-orange); font-size: 1.1em; padding: 18px 16px; cursor: pointer; }
.link ha-icon { --mdc-icon-size: 26px; }
.err { margin: 10px 16px; padding: 10px 12px; border-radius: 10px; background: rgba(255,80,80,.12); color: #ff8a80; font-size: .85em; }

/* giorno */
.tabs { display: flex; margin: 14px 12px; background: var(--sc-surface); border-radius: 14px; padding: 0; overflow: hidden; }
.tab { flex: 1; text-align: center; padding: 11px 0; font-size: 1.05em; color: var(--sc-muted); border-radius: 14px; cursor: pointer; }
.tab.on { background: var(--sc-accent); color: #fff; }
.slot { display: flex; align-items: stretch; gap: 16px; padding: 16px 16px; border-top: 1px solid var(--sc-div); cursor: pointer; }
.slot:hover { background: rgba(127,127,127,.05); }
.slot-time { width: 58px; display: flex; flex-direction: column; align-items: center; gap: 4px; flex: none; }
.slot-time ha-icon { --mdc-icon-size: 28px; }
.slot.active .slot-time { color: var(--sc-accent); }
.vsep { width: 1px; background: var(--sc-div); flex: none; }
.slot-main { flex: 1; min-width: 0; }
.slot-top { display: flex; align-items: center; gap: 14px; }
.pname { font-size: 1.2em; font-weight: 600; }
.slot-bottom { display: flex; justify-content: space-between; margin-top: 6px; gap: 8px; }
.tname { color: var(--sc-fg); opacity: .85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pval { font-weight: 600; white-space: nowrap; }
.badge { font-size: .7em; font-weight: 600; color: var(--sc-accent); margin-left: auto; }
.circle { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; flex: none; }
.circle ha-icon { --mdc-icon-size: 22px; }
.list-pad { padding-bottom: 86px; position: relative; }
.fab { position: absolute; right: 16px; bottom: 16px; width: 64px; height: 64px; border-radius: 50%; background: var(--sc-accent); color: #fff;
  display: grid; place-items: center; box-shadow: 0 6px 18px rgba(0,0,0,.35); }
.fab ha-icon { --mdc-icon-size: 32px; }
.small-link { color: var(--sc-orange); padding: 18px 16px 0; display: flex; gap: 10px; align-items: center; cursor: pointer; font-size: .95em; }

/* form */
.sec { color: var(--sc-accent); font-size: 1.2em; font-weight: 500; padding: 22px 16px 14px; border-bottom: 1px solid var(--sc-div); }
.row { display: flex; align-items: center; justify-content: space-between; padding: 16px; border-bottom: 1px solid var(--sc-div); gap: 12px; }
.row label { font-size: 1.1em; }
.timebox { display: flex; align-items: center; gap: 8px; color: var(--sc-muted); }
input[type=time] { font: inherit; font-size: 1.05em; color: var(--sc-fg); background: var(--sc-surface); border: 0; border-radius: 8px; padding: 6px 8px; color-scheme: light dark; }
.hint { color: var(--sc-muted); font-size: .8em; padding: 6px 16px 0; }
.opt-row { display: flex; align-items: center; gap: 14px; padding: 13px 16px; border-bottom: 1px solid var(--sc-div); cursor: pointer; }
.radio { width: 28px; height: 28px; border-radius: 50%; border: 2px solid var(--sc-fg); display: grid; place-items: center; flex: none; opacity: .85; }
.radio.on { background: var(--sc-orange); border-color: var(--sc-orange); color: #fff; opacity: 1; }
.radio ha-icon { --mdc-icon-size: 18px; }
.opt-name { flex: 1; font-size: 1.1em; min-width: 0; }
.opt-name small { display: block; color: var(--sc-muted); font-size: .78em; margin-top: 2px; }
.pill { background: var(--sc-accent); color: #fff; border-radius: 10px; padding: 7px 14px; font-size: .95em; flex: none; }
.add { display: flex; align-items: center; gap: 18px; color: var(--sc-orange); padding: 18px 16px; font-size: 1.05em; cursor: pointer; border-bottom: 1px solid var(--sc-div); }
.add ha-icon { --mdc-icon-size: 30px; }
.cta { display: block; width: calc(100% - 32px); margin: 22px 16px 18px; background: var(--sc-accent); color: #fff; font-size: 1.15em; font-weight: 600;
  border-radius: 14px; padding: 16px; text-align: center; }
.cta[disabled] { opacity: .5; }
.name-row { display: flex; align-items: flex-end; gap: 18px; padding: 18px 16px 22px; border-bottom: 1px solid var(--sc-div); }
.field { flex: 1; display: flex; flex-direction: column; }
.field span { color: var(--sc-muted); font-size: .85em; }
.field input { font: inherit; font-size: 1.15em; color: var(--sc-fg); background: transparent; border: 0; border-bottom: 1px solid var(--sc-muted); padding: 6px 0; outline: none; }
.field input:focus { border-bottom-color: var(--sc-accent); }
.chips { display: flex; flex-wrap: wrap; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--sc-div); }
.chip { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; cursor: pointer; border: 2px solid transparent; }
.chip.on { border-color: var(--sc-fg); }
.chip.ic { background: var(--sc-surface); }
.chip ha-icon { --mdc-icon-size: 20px; }
.note { padding: 12px 16px 18px; font-size: 1em; line-height: 1.35; border-bottom: 1px solid var(--sc-div); }
.tgt { display: flex; align-items: center; gap: 18px; padding: 20px 16px 16px; }
.tgt ha-icon { --mdc-icon-size: 30px; }
.tgt .n { flex: 1; font-size: 1.15em; font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tgt .v { font-size: 1.15em; }
.slider { position: relative; height: 56px; margin: 4px 16px 0; border-radius: 16px; overflow: hidden;
  background: linear-gradient(90deg, var(--sc-accent) 0, var(--sc-accent) calc(var(--p) * (100% - 18px) + 18px), var(--sc-track) calc(var(--p) * (100% - 18px) + 18px), var(--sc-track) 100%); }
.slider.dis { opacity: .35; }
.ticks { position: absolute; inset: 0; display: flex; justify-content: space-evenly; align-items: center; pointer-events: none; }
.ticks i { width: 1px; height: 40%; background: rgba(255,255,255,.35); }
.slider input { -webkit-appearance: none; appearance: none; position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; background: transparent; cursor: pointer; }
.slider input::-webkit-slider-runnable-track { height: 56px; background: transparent; }
.slider input::-webkit-slider-thumb { -webkit-appearance: none; width: 10px; height: 34px; margin-top: 11px; margin-left: 4px; border-radius: 6px; background: rgba(255,255,255,.8); }
.slider input::-moz-range-track { background: transparent; height: 56px; }
.slider input::-moz-range-thumb { width: 10px; height: 34px; border-radius: 6px; background: rgba(255,255,255,.8); border: 0; }
.steppers { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px 6px; color: var(--sc-muted); font-size: .85em; }
.steppers div { display: flex; gap: 10px; }
.steppers button { width: 44px; height: 38px; border-radius: 10px; background: var(--sc-surface); font-size: 1.3em; color: var(--sc-fg); }
.seg2 { display: flex; gap: 10px; padding: 10px 16px; }
.seg2 button { flex: 1; padding: 16px 0; border-radius: 14px; background: var(--sc-surface); font-size: 1.05em; display: flex; justify-content: center; gap: 8px; align-items: center; }
.seg2 button.on { background: var(--sc-accent); color: #fff; }
.chk { display: flex; align-items: center; gap: 14px; padding: 14px 16px; cursor: pointer; }
.empty { padding: 28px 20px; color: var(--sc-muted); line-height: 1.5; }
.tf { display: flex; align-items: center; gap: 2px; background: var(--sc-surface); border-radius: 10px; padding: 2px 2px 2px 8px; position: relative; }
.tf.dis { opacity: .5; }
.tf input.hm { width: 2.1em; font: inherit; font-size: 1.15em; font-variant-numeric: tabular-nums; text-align: center; color: var(--sc-fg);
  background: transparent; border: 0; border-radius: 6px; padding: 6px 0; outline: none; }
.tf input.hm:focus { background: var(--sc-accent); color: #fff; }
.tf .colon { font-size: 1.15em; }
.tf .clk { width: 38px; height: 38px; display: grid; place-items: center; color: var(--sc-muted); }
.tf input.native { position: absolute; right: 0; bottom: 0; width: 1px; height: 1px; opacity: 0; pointer-events: none; border: 0; padding: 0; }
.range { color: var(--sc-muted); font-size: .8em; }
.modes { display: flex; flex-wrap: wrap; gap: 8px; padding: 6px 16px 14px; }
.modes button { padding: 9px 14px; border-radius: 10px; background: var(--sc-surface); font-size: .95em; }
.modes button.on { background: var(--sc-accent); color: #fff; }
.toast { position: absolute; left: 16px; right: 16px; bottom: 16px; background: #323232; color: #fff; padding: 12px 16px; border-radius: 10px;
  font-size: .9em; z-index: 10; box-shadow: 0 6px 18px rgba(0,0,0,.4); }
`;

class SchedulaCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._view = 'week';
    this._stack = [];
    this._day = (new Date().getDay() + 6) % 7;
    this._draft = null;
    this._sig = null;
    this._menu = null;
    this._rendered = false;
    this.shadowRoot.addEventListener('click', (e) => this._onClick(e));
    this.shadowRoot.addEventListener('input', (e) => this._onInput(e));
    this.shadowRoot.addEventListener('change', (e) => this._onInput(e));
    this.shadowRoot.addEventListener('focusin', (e) => {
      const el = e.composedPath()[0];
      if (el && el.classList && el.classList.contains('hm')) {
        el.select();
        setTimeout(() => el.select && el.select(), 0);
      }
    });
    this._lastActivity = Date.now();
    ['click', 'input', 'keydown', 'touchstart', 'pointerdown'].forEach((ev) =>
      this.shadowRoot.addEventListener(ev, () => (this._lastActivity = Date.now()), { passive: true, capture: true })
    );
  }

  static getStubConfig(hass) {
    const id = Object.keys(hass.states).find((e) => e.startsWith('sensor.') && isSchedula(hass.states[e]));
    return id ? { entity: id } : {};
  }

  setConfig(config) {
    this._config = config || {};
    this._sel = this._config.entity || null;
  }

  getCardSize() {
    return 9;
  }

  connectedCallback() {
    this._timer = setInterval(() => {
      if (this._hass && ['week', 'day'].includes(this._view) && !this._menu) this._render();
    }, 60000);
    // Dopo N secondi senza modifiche torna alla schermata principale della card
    this._idleTimer = setInterval(() => this._checkIdle(), 5000);
  }

  _checkIdle() {
    const idle = Number(this._config?.idle_timeout ?? IDLE_DEFAULT);
    if (!this._hass || !idle || idle <= 0) return;
    if (this._view === 'week' && !this._menu) return;
    if (Date.now() - this._lastActivity < idle * 1000) return;
    this._view = 'week';
    this._stack = [];
    this._menu = null;
    this._interval = null;
    this._presetEdit = null;
    this._loadDraft();
    this._render();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    clearInterval(this._idleTimer);
  }

  set hass(hass) {
    this._hass = hass;
    const list = this._schedules();
    if (!this._sel || !hass.states[this._sel]) this._sel = list[0] || null;
    const st = this._sel ? hass.states[this._sel] : null;
    const tgt = st ? hass.states[st.attributes.target_entity] : null;
    const sig = st
      ? JSON.stringify([st.state, st.attributes, list, tgt ? [tgt.attributes.friendly_name, tgt.attributes.min_temp, tgt.attributes.max_temp, tgt.attributes.min, tgt.attributes.max, tgt.attributes.options] : null])
      : 'none:' + list.join(',');
    if (sig === this._sig && this._rendered) return;
    this._sig = sig;
    if (!this._rendered || ['week', 'day'].includes(this._view)) {
      this._loadDraft();
      this._render();
    }
  }

  // ------------------------------------------------------------- dati
  _schedules() {
    if (!this._hass) return [];
    if (Array.isArray(this._config.entities) && this._config.entities.length) {
      return this._config.entities.filter((e) => isSchedula(this._hass.states[e]));
    }
    return Object.keys(this._hass.states).filter((e) => e.startsWith('sensor.') && isSchedula(this._hass.states[e])).sort();
  }

  _st() {
    return this._sel && this._hass ? this._hass.states[this._sel] : null;
  }

  _attr() {
    const st = this._st();
    return st ? st.attributes : {};
  }

  _targetId() {
    return this._attr().target_entity || '';
  }

  _target() {
    return this._hass ? this._hass.states[this._targetId()] : null;
  }

  _domain() {
    return this._targetId().split('.')[0];
  }

  _vt() {
    return valueType(this._targetId());
  }

  _isTemp() {
    return ['climate', 'water_heater'].includes(this._domain());
  }

  _loadDraft() {
    const a = this._attr();
    if (!a.week) {
      this._draft = null;
      return;
    }
    this._draft = { presets: clone(a.presets || []), week: clone(a.week || {}) };
    DAYS.forEach((d) => {
      if (!Array.isArray(this._draft.week[d])) this._draft.week[d] = [];
    });
  }

  _preset(id) {
    return (this._draft?.presets || []).find((p) => p.id === id);
  }

  _prevLast(d) {
    const prev = this._draft.week[DAYS[(d + 6) % 7]] || [];
    return prev.length ? prev[prev.length - 1].preset : null;
  }

  _dayArr(d) {
    const fallback = this._prevLast(d) ?? this._draft.presets[0]?.id;
    return slotsToArray(this._draft.week[DAYS[d]], fallback);
  }

  _bounds() {
    const a = this._target()?.attributes || {};
    const d = this._domain();
    if (d === 'climate') return { min: Number(a.min_temp ?? 7), max: Number(a.max_temp ?? 35), step: Number(a.target_temp_step ?? 0.5) };
    if (d === 'water_heater') return { min: Number(a.min_temp ?? 30), max: Number(a.max_temp ?? 70), step: Number(a.target_temp_step ?? 1) };
    if (d === 'cover') return { min: 0, max: 100, step: 1 };
    return { min: Number(a.min ?? 0), max: Number(a.max ?? 100), step: Number(a.step ?? 1) };
  }

  _fmtP(p) {
    if (!p) return '—';
    if (this._domain() === 'climate' && p.hvac_mode === 'off') return 'Spento';
    const base = this._fmt(p.value);
    if (this._domain() === 'climate' && p.hvac_mode && String(p.value).toLowerCase() !== 'off') return `${base} · ${HVAC_LABELS[p.hvac_mode] || p.hvac_mode}`;
    return base;
  }

  _fixedOptions() {
    return FIXED_OPTIONS[this._domain()] || null;
  }

  _fmt(v) {
    if (v === null || v === undefined || v === '') return '—';
    const vt = this._vt();
    const fixed = this._fixedOptions();
    if (fixed) {
      const f = fixed.find(([k]) => k === String(v));
      return f ? f[1] : String(v);
    }
    if (this._isTemp() && String(v).toLowerCase() === 'off') return 'Spento';
    if (vt === 'number') {
      const n = Number(v);
      if (Number.isNaN(n)) return String(v);
      const b = this._bounds();
      const dec = this._isTemp() ? Math.max(1, decimals(b.step)) : decimals(b.step);
      const d = this._domain();
      const unit = this._isTemp() ? '°' : d === 'cover' ? '%' : this._target()?.attributes?.unit_of_measurement ? ' ' + this._target().attributes.unit_of_measurement : '';
      return n.toFixed(dec) + unit;
    }
    if (vt === 'onoff') return String(v).toLowerCase() === 'on' ? 'Acceso' : 'Spento';
    return String(v);
  }

  _targetName() {
    const t = this._target();
    return t?.attributes?.friendly_name || this._targetId();
  }

  _targetIcon() {
    return this._target()?.attributes?.icon || DOMAIN_ICONS[this._domain()] || 'mdi:devices';
  }

  _settingsLabel(kind) {
    if (this._isTemp()) return kind === 'section' ? 'Impostazioni delle temperature' : 'Modifica le temperature';
    return kind === 'section' ? 'Impostazioni' : 'Modifica le impostazioni';
  }

  async _save() {
    const a = this._attr();
    try {
      await this._hass.callService('schedula', 'save', {
        schedule_id: a.schedule_id,
        presets: this._draft.presets,
        week: this._draft.week,
      });
    } catch (err) {
      this._toast('Errore nel salvataggio: ' + (err?.message || err));
      this._loadDraft();
      this._render();
    }
  }

  async _call(service, data) {
    try {
      await this._hass.callService('schedula', service, { schedule_id: this._attr().schedule_id, ...data });
    } catch (err) {
      this._toast('Errore: ' + (err?.message || err));
    }
  }

  // ------------------------------------------------------- navigazione
  _push(view) {
    this._stack.push(this._view);
    this._view = view;
    this._menu = null;
    this._render();
    this.scrollIntoView?.({ block: 'nearest' });
  }

  _pop() {
    this._view = this._stack.pop() || 'week';
    this._menu = null;
    this._render();
  }

  _toast(msg) {
    const card = this.shadowRoot.querySelector('ha-card');
    if (!card) return;
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    card.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  // ------------------------------------------------------------ eventi
  _onClick(e) {
    const el = e.target.closest('[data-action]');
    const action = el?.dataset.action;
    if (this._menu && !e.target.closest('.menu') && action !== 'menu' && action !== 'title-menu') {
      this._menu = null;
      this._render();
      return;
    }
    if (!action) return;
    e.stopPropagation();
    const ds = el.dataset;
    const draft = this._draft;

    switch (action) {
      case 'back':
        this._pop();
        break;
      case 'menu':
        this._menu = this._menu === 'main' ? null : 'main';
        this._render();
        break;
      case 'title-menu':
        if (this._schedules().length > 1) {
          this._menu = this._menu === 'schedules' ? null : 'schedules';
          this._render();
        }
        break;
      case 'select-schedule':
        this._sel = ds.entity;
        this._view = 'week';
        this._stack = [];
        this._menu = null;
        this._loadDraft();
        this._render();
        break;
      case 'toggle-enabled':
        this._menu = null;
        this._call('set_enabled', { enabled: !this._attr().enabled });
        this._render();
        break;
      case 'apply-now':
        this._menu = null;
        this._call('apply_now', {});
        this._toast('Impostazione corrente applicata');
        this._render();
        break;
      case 'open-day':
        this._day = Number(ds.day);
        this._push('day');
        break;
      case 'tab':
        this._day = Number(ds.day);
        this._render();
        break;
      case 'open-presets':
        this._push('presets');
        break;
      case 'add-interval': {
        // Inizio = fine dell'orario precedente all'ultimo (cioè inizio dell'ultimo), durata 1 ora
        const slots = draft.week[DAYS[this._day]] || [];
        const lastStart = slots.length ? toMin(slots[slots.length - 1].start) : 0;
        const start = lastStart > 0 ? lastStart : 8 * 60;
        const end = Math.min(start + 60, 1440);
        const last = slots[slots.length - 1];
        const other = draft.presets.find((p) => p.id !== last?.preset) || draft.presets[0];
        this._interval = { mode: 'add', start: toHHMM(start), end: toHHMM(end), preset: other?.id };
        this._push('interval');
        break;
      }
      case 'edit-slot': {
        const slots = draft.week[DAYS[this._day]];
        const idx = Number(ds.idx);
        const s = slots[idx];
        const os = toMin(s.start);
        const oe = idx + 1 < slots.length ? toMin(slots[idx + 1].start) : 1440;
        this._interval = { mode: 'edit', idx, count: slots.length, start: s.start, end: toHHMM(oe), preset: s.preset, os, oe };
        this._push('interval');
        break;
      }
      case 'pick-time': {
        const f = ds.field;
        const native = this.shadowRoot.querySelector(`input.native[data-field="${f}-native"]`);
        if (!native) break;
        const cur = this._interval[f] === '24:00' ? '00:00' : this._interval[f];
        native.value = cur;
        try {
          native.showPicker();
        } catch (err) {
          native.focus();
        }
        break;
      }
      case 'set-hvac':
        this._presetEdit.hvac_mode = ds.mode || undefined;
        if (ds.mode !== 'off' && String(this._presetEdit.value).toLowerCase() === 'off') {
          this._presetEdit.value = this._snap((this._bounds().min + this._bounds().max) / 2);
        }
        this._render();
        break;
      case 'pick-preset':
        this._interval.preset = ds.id;
        this._render();
        break;
      case 'save-interval':
        this._saveInterval();
        break;
      case 'delete-interval':
        this._deleteInterval();
        break;
      case 'edit-preset': {
        const p = this._preset(ds.id);
        if (!p) break;
        this._presetEdit = { ...clone(p), isNew: false };
        this._push('preset');
        break;
      }
      case 'new-preset': {
        const used = draft.presets.map((p) => p.color);
        const b = this._bounds();
        const vt = this._vt();
        const opts = this._target()?.attributes?.options || [];
        let value = 'on';
        if (vt === 'number') value = this._snap((b.min + b.max) / 2);
        if (vt === 'option') value = this._fixedOptions()?.[0]?.[0] ?? opts[0] ?? '';
        this._presetEdit = {
          isNew: true,
          id: 'p' + Date.now().toString(36),
          name: '',
          icon: ICONS[0],
          color: COLORS.find((c) => !used.includes(c)) || COLORS[4],
          value,
          fromInterval: this._view === 'interval',
        };
        this._push('preset');
        break;
      }
      case 'set-color':
        this._presetEdit.color = ds.color;
        this._render();
        break;
      case 'set-icon':
        this._presetEdit.icon = ds.icon;
        this._render();
        break;
      case 'set-val':
        this._presetEdit.value = ds.val;
        this._render();
        break;
      case 'step': {
        const b = this._bounds();
        const cur = Number(this._presetEdit.value);
        const base = Number.isNaN(cur) ? b.min : cur;
        this._presetEdit.value = this._snap(Math.min(b.max, Math.max(b.min, base + Number(ds.dir) * b.step)));
        this._render();
        break;
      }
      case 'temp-off-legacy': {
        const pe = this._presetEdit;
        if (String(pe.value).toLowerCase() === 'off') {
          pe.value = pe._lastNum ?? this._snap((this._bounds().min + this._bounds().max) / 2);
        } else {
          pe._lastNum = pe.value;
          pe.value = 'off';
        }
        this._render();
        break;
      }
      case 'save-preset':
        this._savePreset();
        break;
      case 'delete-preset':
        this._deletePreset();
        break;
      case 'copy-day':
        this._menu = null;
        this._copy = { from: this._day, to: [] };
        this._push('copy');
        break;
      case 'copy-toggle': {
        const d = Number(ds.day);
        const to = this._copy.to;
        this._copy.to = to.includes(d) ? to.filter((x) => x !== d) : [...to, d];
        this._render();
        break;
      }
      case 'copy-all':
        this._copy.to = [0, 1, 2, 3, 4, 5, 6].filter((d) => d !== this._copy.from);
        this._render();
        break;
      case 'copy-save':
        this._copy.to.forEach((d) => {
          draft.week[DAYS[d]] = clone(draft.week[DAYS[this._copy.from]]);
        });
        this._save();
        this._toast(`Copiato su ${this._copy.to.length} giorn${this._copy.to.length === 1 ? 'o' : 'i'}`);
        this._pop();
        break;
      default:
        break;
    }
  }

  _onInput(e) {
    const f = e.target.dataset?.field;
    if (!f) return;
    const v = e.target.value;
    const tm = /^(start|end)-(h|m|native)$/.exec(f);
    if (tm) {
      this._onTimeInput(e, tm[1], tm[2]);
      return;
    }
    if (f === 'preset-name') this._presetEdit.name = v;
    else if (f === 'preset-slider') {
      const n = this._snap(Number(v));
      this._presetEdit.value = n;
      const b = this._bounds();
      const wrap = e.target.closest('.slider');
      wrap.style.setProperty('--p', (n - b.min) / (b.max - b.min || 1));
      const out = this.shadowRoot.getElementById('pval');
      if (out) out.textContent = this._fmt(n);
    }
  }

  _onTimeInput(e, field, part) {
    const box = e.target.closest('.tf');
    const hEl = box.querySelector('input[data-field$="-h"]');
    const mEl = box.querySelector('input[data-field$="-m"]');
    if (part === 'native') {
      if (!e.target.value) return;
      const [h, m] = e.target.value.split(':');
      let val = `${h}:${m}`;
      if (field === 'end' && val === '00:00') val = '24:00';
      this._interval[field] = val;
      [hEl.value, mEl.value] = val.split(':');
      return;
    }
    // solo cifre
    e.target.value = e.target.value.replace(/\D/g, '').slice(0, 2);
    if (e.type === 'input' && part === 'h' && e.target.value.length === 2) {
      mEl.focus();
      mEl.select();
    }
    let h = parseInt(hEl.value || '0', 10);
    let m = parseInt(mEl.value || '0', 10);
    const maxH = field === 'end' ? 24 : 23;
    h = Math.min(Math.max(h, 0), maxH);
    m = Math.min(Math.max(m, 0), 59);
    if (h === 24) m = 0;
    this._interval[field] = `${pad(h)}:${pad(m)}`;
    if (e.type === 'change') {
      hEl.value = pad(h);
      mEl.value = pad(m);
    }
  }

  _timeField(field, value, disabled) {
    const [h, m] = String(value || '00:00').split(':');
    const dis = disabled ? 'disabled' : '';
    return `<div class="tf ${disabled ? 'dis' : ''}">
      <input class="hm" data-field="${field}-h" inputmode="numeric" pattern="[0-9]*" maxlength="2" value="${esc(h)}" aria-label="Ore" ${dis}>
      <span class="colon">:</span>
      <input class="hm" data-field="${field}-m" inputmode="numeric" pattern="[0-9]*" maxlength="2" value="${esc(m)}" aria-label="Minuti" ${dis}>
      ${disabled ? '<span style="width:6px"></span>' : `<button class="clk" data-action="pick-time" data-field="${field}" aria-label="Scegli ora"><ha-icon icon="mdi:clock-outline"></ha-icon></button>`}
      <input type="time" class="native" data-field="${field}-native" tabindex="-1">
    </div>`;
  }

  _snap(v) {
    const b = this._bounds();
    const n = Math.round((v - b.min) / b.step) * b.step + b.min;
    return Number(n.toFixed(Math.max(decimals(b.step), 0)));
  }

  // ---------------------------------------------------------- modifiche
  _saveInterval() {
    const it = this._interval;
    if (!it.start || !it.end) return this._toast('Imposta inizio e fine');
    let s = toMin(it.start);
    let e = toMin(it.end);
    if (e === 0) e = 1440;
    if (it.mode === 'edit') {
      if (it.os === 0) s = 0; // il primo orario parte sempre da 00:00
      if (it.oe === 1440) e = 1440; // l'ultimo finisce sempre a 24:00
    }
    if (e <= s) return this._toast("L'ora di fine deve essere successiva all'inizio");
    if (!this._preset(it.preset)) return this._toast("Scegli un'impostazione");
    const d = this._day;
    const arr = this._dayArr(d);
    if (it.mode === 'edit') {
      // Orari collegati: spostando l'inizio si sposta la fine del precedente,
      // spostando la fine si sposta l'inizio del successivo.
      const prevP = it.os > 0 ? arr[it.os - 1] : null;
      const nextP = it.oe < 1440 ? arr[it.oe] : null;
      if (s > it.os && prevP) arr.fill(prevP, it.os, s);
      if (e < it.oe && nextP) arr.fill(nextP, e, it.oe);
    }
    arr.fill(it.preset, s, e);
    this._draft.week[DAYS[d]] = arrayToSlots(arr);
    this._save();
    this._pop();
  }

  _deleteInterval() {
    const it = this._interval;
    if (!confirm('Eliminare questo intervallo orario?')) return;
    const d = this._day;
    const arr = this._dayArr(d);
    // il precedente si allunga fino alla fine; se è il primo, il successivo parte da 00:00
    const base = it.os > 0 ? arr[it.os - 1] : it.oe < 1440 ? arr[it.oe] : arr[it.os];
    arr.fill(base, it.os, it.oe);
    this._draft.week[DAYS[d]] = arrayToSlots(arr);
    this._save();
    this._pop();
  }

  _savePreset() {
    const pe = this._presetEdit;
    const name = (pe.name || '').trim();
    if (!name) return this._toast('Inserisci un nome');
    const preset = { id: pe.id, name, icon: pe.icon, color: pe.color, value: pe.value };
    if (this._domain() === 'climate' && pe.hvac_mode) preset.hvac_mode = pe.hvac_mode;
    const list = this._draft.presets;
    const idx = list.findIndex((p) => p.id === pe.id);
    if (idx >= 0) list[idx] = preset;
    else list.push(preset);
    this._save();
    const fromInterval = pe.isNew && pe.fromInterval;
    this._pop();
    if (fromInterval && this._interval) {
      this._interval.preset = preset.id;
      this._render();
    }
  }

  _deletePreset() {
    const pe = this._presetEdit;
    const list = this._draft.presets;
    if (list.length <= 1) return this._toast("Serve almeno un'impostazione");
    const used = DAYS.reduce((n, d) => n + this._draft.week[d].filter((s) => s.preset === pe.id).length, 0);
    if (used) return this._toast(`Impostazione usata in ${used} intervall${used === 1 ? 'o' : 'i'}: sostituiscila prima di eliminarla`);
    if (!confirm(`Eliminare "${pe.name}"?`)) return;
    this._draft.presets = list.filter((p) => p.id !== pe.id);
    this._save();
    if (this._interval?.preset === pe.id) this._interval.preset = this._draft.presets[0].id;
    this._pop();
  }

  // ------------------------------------------------------------ render
  _circle(p, size) {
    const s = size ? `width:${size}px;height:${size}px;` : '';
    const bg = p?.color || '#888888';
    return `<span class="circle" style="background:${esc(bg)};color:${contrastColor(bg)};${s}"><ha-icon icon="${esc(p?.icon || 'mdi:help')}"></ha-icon></span>`;
  }

  _header({ title, sub, subOff, back, trash, menu, titleMenu }) {
    const many = titleMenu && this._schedules().length > 1;
    let html = `<div class="hdr">
      ${back ? `<button class="icon-btn" data-action="back" aria-label="Indietro"><ha-icon icon="mdi:arrow-left"></ha-icon></button>` : `<div class="hdr-icon"><ha-icon icon="mdi:calendar-clock"></ha-icon></div>`}
      <div class="hdr-t ${many ? 'clickable' : ''}" ${many ? 'data-action="title-menu"' : ''}>
        <div class="title"><span style="overflow:hidden;text-overflow:ellipsis">${esc(title)}</span>${many ? '<ha-icon class="chev" icon="mdi:chevron-down"></ha-icon>' : ''}</div>
        ${sub ? `<div class="sub ${subOff ? 'off' : ''}">${sub}</div>` : ''}
      </div>
      ${trash ? `<button class="icon-btn" data-action="${trash}" aria-label="Elimina"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>` : ''}
      ${menu ? `<button class="icon-btn" data-action="menu" aria-label="Menu"><ha-icon icon="mdi:dots-vertical"></ha-icon></button>` : ''}
    </div>`;
    const a = this._attr();
    if (this._menu === 'main') {
      html += `<div class="menu">
        <div class="mi" data-action="toggle-enabled"><ha-icon icon="${a.enabled ? 'mdi:pause-circle-outline' : 'mdi:play-circle-outline'}"></ha-icon>${a.enabled ? 'Disattiva' : 'Attiva'} schedulazione</div>
        <div class="mi" data-action="apply-now"><ha-icon icon="mdi:sync"></ha-icon>Applica ora</div>
        ${this._view === 'day' ? `<div class="mi" data-action="copy-day"><ha-icon icon="mdi:content-copy"></ha-icon>Copia ${DAY_LONG[this._day]} su…</div>` : ''}
        <div class="mi" data-action="open-presets"><ha-icon icon="mdi:tune-variant"></ha-icon>${this._settingsLabel('link')}</div>
      </div>`;
    }
    if (this._menu === 'schedules') {
      html += `<div class="menu left">${this._schedules()
        .map((id) => {
          const st = this._hass.states[id];
          const sel = id === this._sel;
          return `<div class="mi ${sel ? 'sel' : ''}" data-action="select-schedule" data-entity="${esc(id)}"><ha-icon icon="${sel ? 'mdi:check' : 'mdi:calendar-clock'}"></ha-icon>${esc(st.attributes.friendly_name || id)}</div>`;
        })
        .join('')}</div>`;
    }
    return html;
  }

  _mainHeader(back) {
    const a = this._attr();
    const st = this._st();
    return this._header({
      title: this._config.title || st?.attributes?.friendly_name || 'Schedulazione',
      sub: a.enabled ? 'Attiva' : 'Disattivata',
      subOff: !a.enabled,
      back,
      menu: true,
      titleMenu: true,
    });
  }

  _bar(d) {
    const slots = this._draft.week[DAYS[d]] || [];
    const segs = slots
      .map((s, i) => {
        const from = toMin(s.start);
        const to = i + 1 < slots.length ? toMin(slots[i + 1].start) : 1440;
        const p = this._preset(s.preset);
        return `<div class="seg" style="width:${((to - from) / 14.4).toFixed(3)}%;background:${esc(p?.color || '#555')}" title="${esc(s.start)} ${esc(p?.name || '')}"></div>`;
      })
      .join('');
    const now = new Date();
    const today = (now.getDay() + 6) % 7;
    const marker = d === today ? `<div class="now" style="left:calc(${(((now.getHours() * 60 + now.getMinutes()) / 1440) * 100).toFixed(2)}% - 1px)"></div>` : '';
    return `<div class="bar ${this._attr().enabled ? '' : 'off'}">${segs}${marker}</div>`;
  }

  _viewWeek() {
    const a = this._attr();
    const today = (new Date().getDay() + 6) % 7;
    const cur = this._preset(a.current_preset);
    const nxt = this._preset(a.next_preset);
    let nextTxt = '';
    if (a.next_change && nxt) {
      const dt = new Date(a.next_change);
      const dd = (dt.getDay() + 6) % 7;
      nextTxt = ` · poi <span class="dot" style="background:${esc(nxt.color)}"></span> <b>${esc(nxt.name)}</b> ${dd === today ? 'alle' : DAY_SHORT[dd].toLowerCase() + ' alle'} ${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
    }
    const status = cur
      ? `<div class="status">Ora: <span class="dot" style="background:${esc(cur.color)}"></span><b>${esc(cur.name)}</b> ${esc(this._fmtP(cur))}${nextTxt}</div>`
      : '';
    const rows = DAYS.map(
      (k, i) => `<div class="day-row" data-action="open-day" data-day="${i}">
        <div class="day-name">${DAY_LONG[i]}${i === today ? '<span class="today">oggi</span>' : ''}</div>
        ${this._bar(i)}
      </div>`
    ).join('');
    const err = a.last_error ? `<div class="err">Ultimo errore: ${esc(a.last_error)}</div>` : '';
    return `${this._mainHeader(false)}${status}${err}${rows}
      <div class="link" data-action="open-presets"><ha-icon icon="${this._isTemp() ? 'mdi:thermometer' : 'mdi:tune-variant'}"></ha-icon><span>${this._settingsLabel('link')}</span></div>`;
  }

  _viewDay() {
    const slots = this._draft.week[DAYS[this._day]] || [];
    const now = new Date();
    const isToday = (now.getDay() + 6) % 7 === this._day;
    const nowMin = now.getHours() * 60 + now.getMinutes();
    const tabs = DAY_SHORT.map((n, i) => `<div class="tab ${i === this._day ? 'on' : ''}" data-action="tab" data-day="${i}">${n}</div>`).join('');
    const rows = slots
      .map((s, i) => {
        const p = this._preset(s.preset);
        const from = toMin(s.start);
        const to = i + 1 < slots.length ? toMin(slots[i + 1].start) : 1440;
        const active = isToday && nowMin >= from && nowMin < to && this._attr().enabled;
        return `<div class="slot ${active ? 'active' : ''}" data-action="edit-slot" data-idx="${i}">
          <div class="slot-time"><ha-icon icon="mdi:clock-outline"></ha-icon><span>${esc(s.start)}</span><span class="range">${toHHMM(to)}</span></div>
          <div class="vsep"></div>
          <div class="slot-main">
            <div class="slot-top">${this._circle(p)}<span class="pname">${esc(p?.name || s.preset)}</span>${active ? '<span class="badge">IN CORSO</span>' : ''}</div>
            <div class="slot-bottom"><span class="tname">${esc(this._targetName())}</span><span class="pval">${esc(this._fmtP(p))}</span></div>
          </div>
        </div>`;
      })
      .join('');
    return `${this._mainHeader(true)}
      <div class="tabs">${tabs}</div>
      <div class="list-pad">${rows}
        <div class="small-link" data-action="copy-day"><ha-icon icon="mdi:content-copy"></ha-icon>Copia ${DAY_LONG[this._day]} su altri giorni</div>
        <button class="fab" data-action="add-interval" aria-label="Aggiungi intervallo"><ha-icon icon="mdi:plus"></ha-icon></button>
      </div>`;
  }

  _presetRows(selectable) {
    const it = this._interval;
    return this._draft.presets
      .map((p) => {
        const sel = selectable && it && it.preset === p.id;
        return `<div class="opt-row" ${selectable ? `data-action="pick-preset" data-id="${esc(p.id)}"` : `data-action="edit-preset" data-id="${esc(p.id)}"`}>
          ${selectable ? `<span class="radio ${sel ? 'on' : ''}">${sel ? '<ha-icon icon="mdi:check-bold"></ha-icon>' : ''}</span>` : ''}
          ${this._circle(p)}
          <span class="opt-name">${esc(p.name)}<small>${esc(this._fmtP(p))}</small></span>
          <button class="pill" data-action="edit-preset" data-id="${esc(p.id)}">Modifica</button>
        </div>`;
      })
      .join('');
  }

  _viewInterval() {
    const it = this._interval;
    const day = DAY_LONG[this._day];
    const canDelete = it.mode === 'edit' && it.count > 1;
    const lockStart = it.mode === 'edit' && it.os === 0;
    const lockEnd = it.mode === 'edit' && it.oe === 1440;
    return `${this._header({
      title: it.mode === 'add' ? 'Aggiungi un intervallo orario' : 'Modifica intervallo orario',
      back: true,
      trash: canDelete ? 'delete-interval' : null,
    })}
      <div class="sec">Intervallo orario</div>
      <div class="row"><label>Inizio</label><div class="timebox">${day}${this._timeField('start', lockStart ? '00:00' : it.start, lockStart)}</div></div>
      <div class="row"><label>Fine</label><div class="timebox">${day}${this._timeField('end', lockEnd ? '24:00' : it.end, lockEnd)}</div></div>
      <div class="hint">${it.mode === 'edit'
        ? "Tocca le cifre per scriverle a mano. Cambiando l'inizio si sposta la fine dell'orario precedente; cambiando la fine si sposta l'inizio del successivo."
        : "Tocca le cifre per scriverle a mano. Il nuovo orario sostituisce quello che c'era in quella fascia."}</div>
      <div class="sec">${this._settingsLabel('section')}</div>
      ${this._presetRows(true)}
      <div class="add" data-action="new-preset"><ha-icon icon="mdi:plus"></ha-icon><span>${this._isTemp() ? 'Aggiungi un nuovo set di temperature personalizzate' : 'Aggiungi una nuova impostazione'}</span></div>
      <button class="cta" data-action="save-interval">Salva</button>`;
  }

  _viewPresets() {
    return `${this._header({ title: this._settingsLabel('section'), back: true })}
      <div class="note">Le modifiche sono applicate a tutti gli intervalli orari dove queste impostazioni vengono usate.</div>
      ${this._presetRows(false)}
      <div class="add" data-action="new-preset"><ha-icon icon="mdi:plus"></ha-icon><span>${this._isTemp() ? 'Aggiungi un nuovo set di temperature personalizzate' : 'Aggiungi una nuova impostazione'}</span></div>`;
  }

  _valueControl() {
    const pe = this._presetEdit;
    const vt = this._vt();
    if (vt === 'number') {
      const b = this._bounds();
      const off = this._isTemp() && (String(pe.value).toLowerCase() === 'off' || pe.hvac_mode === 'off');
      const n = off ? b.min : Number(pe.value);
      const p = Math.min(1, Math.max(0, (n - b.min) / (b.max - b.min || 1)));
      const ticks = '<i></i>'.repeat(12);
      let html = `<div class="slider ${off ? 'dis' : ''}" style="--p:${p}">
          <div class="ticks">${ticks}</div>
          <input type="range" min="${b.min}" max="${b.max}" step="${b.step}" value="${n}" data-field="preset-slider" ${off ? 'disabled' : ''}>
        </div>
        <div class="steppers"><span>${esc(this._fmt(b.min))} – ${esc(this._fmt(b.max))}</span>
          <div><button data-action="step" data-dir="-1" ${off ? 'disabled' : ''}>−</button><button data-action="step" data-dir="1" ${off ? 'disabled' : ''}>+</button></div></div>`;
      if (this._domain() === 'climate') {
        const avail = this._target()?.attributes?.hvac_modes || ['heat', 'cool', 'auto', 'off'];
        const modes = ['', ...Object.keys(HVAC_LABELS).filter((k) => k && avail.includes(k))];
        const cur = pe.hvac_mode || (String(pe.value).toLowerCase() === 'off' ? 'off' : '');
        html = `<div class="sec" style="border:0;padding-top:4px;padding-bottom:8px;font-size:1em">Modalità</div>
          <div class="modes">${modes.map((m) => `<button class="${m === cur ? 'on' : ''}" data-action="set-hvac" data-mode="${m}">${HVAC_LABELS[m]}</button>`).join('')}</div>` + html;
      } else if (this._isTemp()) {
        html += `<div class="chk" data-action="temp-off-legacy"><span class="radio ${off ? 'on' : ''}">${off ? '<ha-icon icon="mdi:check-bold"></ha-icon>' : ''}</span>Spegni l'apparecchio in questa fascia</div>`;
      }
      return html;
    }
    if (vt === 'onoff') {
      const on = String(pe.value).toLowerCase() === 'on';
      return `<div class="seg2">
        <button class="${on ? 'on' : ''}" data-action="set-val" data-val="on"><ha-icon icon="mdi:power"></ha-icon>Acceso</button>
        <button class="${!on ? 'on' : ''}" data-action="set-val" data-val="off"><ha-icon icon="mdi:power-off"></ha-icon>Spento</button>
      </div>`;
    }
    const fixed = this._fixedOptions();
    let list = fixed || (this._target()?.attributes?.options || []).map((o) => [o, o]);
    if (pe.value && !list.some(([k]) => String(k) === String(pe.value))) list = [[pe.value, pe.value], ...list];
    return list
      .map(([k, label]) => {
        const sel = String(k) === String(pe.value);
        return `<div class="opt-row" data-action="set-val" data-val="${esc(k)}"><span class="radio ${sel ? 'on' : ''}">${sel ? '<ha-icon icon="mdi:check-bold"></ha-icon>' : ''}</span><span class="opt-name">${esc(label)}</span></div>`;
      })
      .join('');
  }

  _viewPreset() {
    const pe = this._presetEdit;
    const colors = COLORS.map((c) => `<span class="chip ${c === pe.color ? 'on' : ''}" style="background:${c}" data-action="set-color" data-color="${c}"></span>`).join('');
    const icons = ICONS.map((i) => `<span class="chip ic ${i === pe.icon ? 'on' : ''}" style="${i === pe.icon ? `background:${esc(pe.color)};color:${contrastColor(pe.color)}` : ''}" data-action="set-icon" data-icon="${i}"><ha-icon icon="${i}"></ha-icon></span>`).join('');
    return `${this._header({ title: pe.isNew ? 'Nuova impostazione' : 'Modifica le impostazioni', back: true, trash: pe.isNew ? null : 'delete-preset' })}
      <div class="name-row">${this._circle(pe, 44)}
        <label class="field"><span>Nome</span><input type="text" maxlength="40" data-field="preset-name" value="${esc(pe.name)}" placeholder="Nome"></label>
      </div>
      <div class="chips">${colors}</div>
      <div class="chips">${icons}</div>
      <div class="sec" style="border:0;padding-bottom:4px">${this._isTemp() ? 'Temperature della stanza' : 'Valore'}</div>
      <div class="note">Le modifiche sono applicate a tutti gli intervalli orari dove queste impostazioni vengono usate.</div>
      <div class="tgt"><ha-icon icon="${esc(this._targetIcon())}"></ha-icon><span class="n">${esc(this._targetName())}</span><span class="v" id="pval">${esc(this._fmt(pe.value))}</span></div>
      ${this._valueControl()}
      <button class="cta" data-action="save-preset">Salva</button>`;
  }

  _viewCopy() {
    const c = this._copy;
    const rows = DAY_LONG.map((n, i) => {
      if (i === c.from) return '';
      const on = c.to.includes(i);
      return `<div class="opt-row" data-action="copy-toggle" data-day="${i}"><span class="radio ${on ? 'on' : ''}">${on ? '<ha-icon icon="mdi:check-bold"></ha-icon>' : ''}</span><span class="opt-name">${n}</span></div>`;
    }).join('');
    return `${this._header({ title: `Copia ${DAY_LONG[c.from]}`, back: true })}
      <div class="sec">Copia il programma su</div>
      ${rows}
      <div class="add" data-action="copy-all"><ha-icon icon="mdi:checkbox-multiple-marked-outline"></ha-icon><span>Seleziona tutti</span></div>
      <button class="cta" data-action="copy-save" ${c.to.length ? '' : 'disabled'}>Salva</button>`;
  }

  _render() {
    if (!this._hass) return;
    this._rendered = true;
    let body;
    if (!this._sel || !this._draft) {
      body = `${this._header({ title: this._config.title || 'Schedula' })}<div class="empty">Nessuna schedulazione trovata.<br>Aggiungi l'integrazione <b>Schedula</b> da Impostazioni → Dispositivi e servizi, poi torna qui.</div>`;
    } else {
      switch (this._view) {
        case 'day':
          body = this._viewDay();
          break;
        case 'interval':
          body = this._viewInterval();
          break;
        case 'presets':
          body = this._viewPresets();
          break;
        case 'preset':
          body = this._viewPreset();
          break;
        case 'copy':
          body = this._viewCopy();
          break;
        default:
          this._view = 'week';
          body = this._viewWeek();
      }
    }
    this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card><div class="wrap">${body}</div></ha-card>`;
  }
}

if (!customElements.get('schedula-card')) {
  customElements.define('schedula-card', SchedulaCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'schedula-card',
    name: 'Schedula',
    description: 'Programmatore settimanale con fasce orarie e impostazioni (stile cronotermostato).',
    preview: false,
  });
  console.info(`%c SCHEDULA-CARD %c v${SCHEDULA_CARD_VERSION} `, 'background:#4F87FF;color:#fff;border-radius:3px 0 0 3px', 'background:#222;color:#fff;border-radius:0 3px 3px 0');
}
