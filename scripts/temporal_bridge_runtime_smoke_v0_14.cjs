const fs = require('fs');
const vm = require('vm');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'output', 'temporal_bridge_candidate', 'temporal_bridge.html'), 'utf8');
function block(id) {
  const match = html.match(new RegExp(`<script id="${id}" type="application/json">([\\s\\S]*?)<\\/script>`));
  if (!match) throw new Error(`missing ${id}`);
  return match[1];
}
const logicMatches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if (!logicMatches.length) throw new Error('missing runtime script');
const logic = logicMatches[logicMatches.length - 1][1];

const noop = () => {};
const gradient = { addColorStop: noop };
const context2d = new Proxy({
  setTransform: noop, clearRect: noop, fillRect: noop, beginPath: noop, arc: noop,
  ellipse: noop, fill: noop, stroke: noop, moveTo: noop, lineTo: noop,
  save: noop, restore: noop, translate: noop, rotate: noop, scale: noop,
  closePath: noop, setLineDash: noop, fillText: noop,
  createRadialGradient: () => gradient, createLinearGradient: () => gradient,
}, { get: (target, key) => key in target ? target[key] : 0, set: (target, key, value) => { target[key] = value; return true; } });

class Element {
  constructor(id) {
    this.id = id;
    this.value = id === 'speedSelect' ? '1' : '';
    this.checked = id === 'autoAdvance';
    this.textContent = '';
    this.dataset = {};
    this.children = [];
    this.classList = { toggle: noop };
    this.listeners = {};
  }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  setAttribute(name, value) { this[name] = value; }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { width: 960, height: 720 }; }
  getContext() { return context2d; }
  set innerHTML(value) { this._innerHTML = value; }
  get innerHTML() { return this._innerHTML || ''; }
}

const elements = new Map();
const getElement = id => {
  if (id === 'axmStoryboard') return { textContent: block('axmStoryboard') };
  if (id === 'axmImportReceipt') return { textContent: block('axmImportReceipt') };
  if (!elements.has(id)) elements.set(id, new Element(id));
  return elements.get(id);
};
let rafId = 0;
const raf = new Map();
const requestAnimationFrame = fn => { const id = ++rafId; raf.set(id, fn); return id; };
const cancelAnimationFrame = id => raf.delete(id);
const windowObject = { devicePixelRatio: 1, matchMedia: () => ({ matches: false }), addEventListener: noop };
const documentObject = { hidden: false, getElementById: getElement, addEventListener: noop };
const sandbox = {
  console, JSON, Math, Number, String, Object, Array, Map, Set,
  window: windowObject, document: documentObject,
  requestAnimationFrame, cancelAnimationFrame,
};
vm.createContext(sandbox);
vm.runInContext(logic, sandbox, { filename: 'temporal_bridge_v0_14.inline.js' });

const checks = [];
const check = (name, pass, detail = null) => checks.push({ name, pass: Boolean(pass), detail });
const state = () => windowObject.__axmMainBridge;
const control = windowObject.__axmMainBridgeControl;
const board = JSON.parse(block('axmStoryboard'));
check('runtime control exported', Boolean(control));
check('initial state exported', Boolean(state()));
check('initially paused', state().playing === false);
check('initial authority presentation only', state().authority === 'presentation_state_only');
check('cannot advance mission time', state().mayAdvanceMissionTime === false);
check('cannot append event', state().mayAppendEvent === false);
check('cannot change truth labels', state().mayChangeTruthLabels === false);
check('cannot retarget recorded event', state().mayRetargetEvent === false);
check('cannot modify runtime resources', state().mayModifyRuntimeResources === false);
check('four cues embedded', board.cues.length === 4);
check('source mission clock preserved', state().missionTimeHours === 3);
check('replay display clock starts at zero', state().displaySeconds === 0);
check('first receipt range reconstructed', state().cueMissionStartHours === 0 && state().cueMissionEndHours === 1);
check('age remains unknown without timestamp', state().wallClockAgeStatus === 'UNKNOWN_NO_TIMESTAMP');
check('no-future status is not a prediction', state().futureReceiptStatus === 'NONE_IN_IMPORTED_LEDGER_NOT_A_PREDICTION');
check('state-change receipt is valid', state().stateChangeReceiptStatus === 'STATE_CHANGES_VALID');
check('recorded event deltas are exposed', state().eventDeltaCount === 4, state().eventDeltaCount);

function frame(timestamp) {
  const pending = [...raf.entries()];
  raf.clear();
  for (const [, callback] of pending) callback(timestamp);
}

check('target camera selectable', control.setCamera('target_focus') === 'target_focus');
check('camera state exported', state().cameraPreset === 'target_focus');
check('signal camera selectable', control.setCamera('signal_lane') === 'signal_lane');
check('unknown camera falls back safely', control.setCamera('unregistered') === 'overview');
check('all-label mode selectable', control.setLabels('all') === 'all' && state().labelMode === 'all');
check('unknown label mode falls back safely', control.setLabels('unregistered') === 'focus');
check('inspect-only planet selectable', control.setInspector(board.planets[1].planet_id) === board.planets[1].planet_id);
check('inspector state exported', state().inspectedPlanetId === board.planets[1].planet_id && state().inspectorFollowsEvent === false);
check('inspector does not retarget event', state().sourceEventHash === board.cues[0].source_event_hash && state().mayRetargetEvent === false);
check('unknown inspector falls back to event target', control.setInspector('unregistered') === '' && state().inspectorFollowsEvent === true);
check('scrubber reaches third receipt', control.scrubTo(16.5) === 16.5 && state().cueIndex === 2 && state().scrubberSeconds === 16.5);
check('scrubber cannot advance source mission time', state().missionTimeHours === 3 && state().mayAdvanceMissionTime === false);
control.reset();
check('play starts', control.setPlaying(true) === true);
for (let i = 0; i < 38; i++) frame(i * 100);
check('frames advance', state().frameCount >= 35, state().frameCount);
check('display clock advances independently', state().displaySeconds > 3, state().displaySeconds);
check('source mission clock remains fixed', state().missionTimeHours === 3, state().missionTimeHours);
check('observation segment reached', state().segment === 'observation_window', state().segment);
check('cue phase bounded', state().cuePhase >= 0 && state().cuePhase <= 1, state().cuePhase);
for (let i = 38; i < 70; i++) frame(i * 100);
check('telemetry return reached', state().segment === 'telemetry_return', state().segment);
for (let i = 70; i < 90; i++) frame(i * 100);
check('auto advance reaches next cue', state().cueIndex === 1, state().cueIndex);
check('source event hash remains attached', typeof state().sourceEventHash === 'string' && state().sourceEventHash.length === 64);

control.setPlaying(false);
check('pause stops', state().playing === false);
const stoppedFrames = state().frameCount;
frame(10000);
check('paused frame count stable', state().frameCount === stoppedFrames);
control.selectCue(3);
check('manual cue selection reaches ledger head', state().cueIndex === 3 && state().temporalRelation === 'ledger_head');
check('ledger head ends at source mission clock', state().cueMissionEndHours === state().missionTimeHours);
check('ledger head delta is zero', state().cueDeltaToCurrentHours === 0);
control.setReducedMotion(true);
check('reduced motion blocks play', control.setPlaying(true) === false);
check('reduced motion remains paused', state().playing === false);
control.setReducedMotion(false);
control.reset();
check('reset returns first cue', state().cueIndex === 0, state().cueIndex);
check('reset clears frames', state().frameCount === 0, state().frameCount);
check('reset clears replay display time', state().displaySeconds === 0, state().displaySeconds);
check('reset does not clear source mission time', state().missionTimeHours === 3, state().missionTimeHours);

const failed = checks.filter(row => !row.pass);
process.stdout.write(JSON.stringify({
  schema: 'axm.temporal-evidence-bridge-runtime-smoke.v1',
  version: '0.14.0',
  status: failed.length ? 'failed' : 'passed',
  checks_passed: checks.length - failed.length,
  checks_total: checks.length,
  checks,
  failures: failed,
  visual_scope: 'bounded_dom_canvas_runtime_contract_not_pixel_or_cadence_verification',
}, null, 2));
process.exitCode = failed.length ? 1 : 0;
