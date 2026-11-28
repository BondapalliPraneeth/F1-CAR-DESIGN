import { create } from "zustand";
import { api, ApiError } from "./lib/api";
import type { Assumptions, CarInfo, ComponentSummary, DamageInput, HistoryItem, SimulationResult } from "./lib/types";
import { getSessionId } from "./lib/utils";

export type CameraPreset = "iso" | "front" | "rear" | "left" | "right" | "top";
export type BottomTab = "dashboard" | "assumptions" | "history";

export interface DamageEntry {
  damage_type: string;
  severity: number;
}

interface State {
  sessionId: string;
  car: CarInfo | null;
  components: ComponentSummary[];
  bootError: string | null;

  selectedId: string | null;
  hoveredId: string | null;
  hidden: Record<string, boolean>;
  isolatedId: string | null;
  explode: number;
  xray: boolean;
  autoRotate: boolean;
  followCursor: boolean;
  camera: { preset: CameraPreset; nonce: number };
  screenshotNonce: number;
  bottomTab: BottomTab;
  chatOpen: boolean;

  damage: Record<string, DamageEntry>;
  assumptions: Assumptions;
  scenarioId: string | null;

  result: SimulationResult | null;
  baseline: SimulationResult | null;
  simulating: boolean;
  simError: string | null;
  saving: boolean;
  saved: { simulation_id: string; report_id: string | null } | null;
  saveError: string | null;
  history: HistoryItem[];

  boot: () => Promise<void>;
  select: (id: string | null) => void;
  hover: (id: string | null) => void;
  toggleHidden: (id: string) => void;
  showAll: () => void;
  isolate: (id: string | null) => void;
  setExplode: (v: number) => void;
  setXray: (v: boolean) => void;
  setAutoRotate: (v: boolean) => void;
  setFollowCursor: (v: boolean) => void;
  resetView: () => void;
  setCamera: (p: CameraPreset) => void;
  takeScreenshot: () => void;
  setBottomTab: (t: BottomTab) => void;
  setChatOpen: (open: boolean) => void;

  setDamage: (componentId: string, entry: DamageEntry | null) => void;
  setSeverity: (componentId: string, severity: number) => void;
  applyScenario: (id: string) => void;
  resetDamage: () => void;
  setAssumption: (key: string, value: number | boolean) => void;
  resetAssumptions: () => void;

  simulate: () => void;
  save: () => Promise<void>;
  loadHistory: () => Promise<void>;
}

export function damageList(damage: Record<string, DamageEntry>): DamageInput[] {
  return Object.entries(damage)
    .filter(([, e]) => e.severity > 0)
    .map(([component_id, e]) => ({ component_id, damage_type: e.damage_type, severity: e.severity }));
}

/** Only send assumptions that differ from the defaults. */
export function assumptionOverrides(car: CarInfo | null, a: Assumptions): Assumptions {
  if (!car) return {};
  const out: Assumptions = {};
  for (const m of car.assumptions) if (a[m.key] !== undefined && a[m.key] !== m.default) out[m.key] = a[m.key];
  return out;
}

function defaults(car: CarInfo): Assumptions {
  return Object.fromEntries(car.assumptions.map((m) => [m.key, m.default]));
}

let timer: ReturnType<typeof setTimeout> | undefined;
let controller: AbortController | undefined;
let baselineKey = "";
let baselineController: AbortController | undefined;

export const useStore = create<State>((set, get) => ({
  sessionId: getSessionId(),
  car: null,
  components: [],
  bootError: null,

  selectedId: null,
  hoveredId: null,
  hidden: {},
  isolatedId: null,
  explode: 0,
  xray: false,
  autoRotate: false,
  followCursor: !(typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches),
  camera: { preset: "iso", nonce: 0 },
  screenshotNonce: 0,
  bottomTab: "dashboard",
  chatOpen: false,

  damage: {},
  assumptions: {},
  scenarioId: null,

  result: null,
  baseline: null,
  simulating: false,
  simError: null,
  saving: false,
  saved: null,
  saveError: null,
  history: [],

  async boot() {
    try {
      const [car, components] = await Promise.all([api.car(), api.components()]);
      set({ car, components, assumptions: defaults(car), bootError: null });
      get().simulate();
      void get().loadHistory();
    } catch (e) {
      set({ bootError: e instanceof ApiError ? e.message : String(e) });
    }
  },

  select(id) {
    const prev = get().selectedId;
    set({ selectedId: id });
    if (id && id !== prev && (get().damage[id]?.severity ?? 0) > 0) get().simulate();
  },
  hover: (id) => set({ hoveredId: id }),
  toggleHidden: (id) => set((s) => ({ hidden: { ...s.hidden, [id]: !s.hidden[id] } })),
  showAll: () => set({ hidden: {}, isolatedId: null }),
  isolate: (id) => set({ isolatedId: id, selectedId: id ?? get().selectedId }),
  setExplode: (v) => set({ explode: v }),
  setXray: (v) => set({ xray: v }),
  setAutoRotate: (v) => set({ autoRotate: v }),
  setFollowCursor: (v) => set({ followCursor: v }),
  resetView: () => set((s) => ({ explode: 0, xray: false, hidden: {}, isolatedId: null, camera: { preset: "iso", nonce: s.camera.nonce + 1 } })),
  setCamera: (p) => set((s) => ({ camera: { preset: p, nonce: s.camera.nonce + 1 } })),
  takeScreenshot: () => set((s) => ({ screenshotNonce: s.screenshotNonce + 1 })),
  setBottomTab: (t) => set({ bottomTab: t }),
  setChatOpen: (open) => set({ chatOpen: open }),

  setDamage(componentId, entry) {
    set((s) => {
      const damage = { ...s.damage };
      if (entry) damage[componentId] = entry;
      else delete damage[componentId];
      return { damage, scenarioId: null, saved: null };
    });
    get().simulate();
  },
  setSeverity(componentId, severity) {
    const comp = get().components.find((c) => c.id === componentId);
    const current = get().damage[componentId];
    const damage_type = current?.damage_type ?? comp?.damage_types[0]?.id;
    if (!damage_type) return;
    get().setDamage(componentId, { damage_type, severity });
  },
  applyScenario(id) {
    const sc = get().car?.scenarios.find((s) => s.id === id);
    if (!sc) return;
    const damage: Record<string, DamageEntry> = {};
    for (const d of sc.damages) damage[d.component_id] = { damage_type: d.damage_type, severity: d.severity };
    set({ damage, scenarioId: id, saved: null, selectedId: sc.damages[0]?.component_id ?? get().selectedId });
    get().simulate();
  },
  resetDamage() {
    set({ damage: {}, scenarioId: null, saved: null });
    get().simulate();
  },
  setAssumption(key, value) {
    set((s) => ({ assumptions: { ...s.assumptions, [key]: value }, saved: null }));
    get().simulate();
  },
  resetAssumptions() {
    const car = get().car;
    if (!car) return;
    set({ assumptions: defaults(car), saved: null });
    get().simulate();
  },

  simulate() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(async () => {
      const s = get();
      if (!s.car) return;
      controller?.abort();
      controller = new AbortController();
      const damages = damageList(s.damage);
      const assumptions = assumptionOverrides(s.car, s.assumptions);
      const sel = s.selectedId ? s.damage[s.selectedId] : undefined;
      const focus = s.selectedId && sel && sel.severity > 0 ? { component_id: s.selectedId, damage_type: sel.damage_type, severity: sel.severity } : (damages[0] ?? null);
      set({ simulating: true });

      // Baseline (healthy car under the same assumptions) for panel comparisons.
      const key = JSON.stringify(assumptions);
      if (key !== baselineKey || !s.baseline) {
        baselineKey = key;
        baselineController?.abort();
        baselineController = new AbortController();
        api
          .simulate({ damages: [], assumptions, session_id: s.sessionId, include_curves: false }, baselineController.signal)
          .then((r) => set({ baseline: r.result }))
          .catch(() => undefined);
      }

      try {
        const r = await api.simulate(
          { damages, assumptions, session_id: s.sessionId, focus, include_curves: true, scenario_id: s.scenarioId },
          controller.signal,
        );
        set({ result: r.result, simError: null, simulating: false });
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        set({ simError: e instanceof ApiError ? e.message : String(e), simulating: false });
      }
    }, 220);
  },

  async save() {
    const s = get();
    if (!s.car) return;
    set({ saving: true, saveError: null });
    try {
      const r = await api.simulate({
        damages: damageList(s.damage),
        assumptions: assumptionOverrides(s.car, s.assumptions),
        session_id: s.sessionId,
        persist: true,
        include_curves: false,
        scenario_id: s.scenarioId,
      });
      if (!r.persisted || !r.simulation_id) {
        set({ saving: false, saveError: "The server could not store this simulation (database unavailable)." });
        return;
      }
      set({ saving: false, saved: { simulation_id: r.simulation_id, report_id: r.report_id } });
      void get().loadHistory();
    } catch (e) {
      set({ saving: false, saveError: e instanceof ApiError ? e.message : String(e) });
    }
  },

  async loadHistory() {
    try {
      const history = await api.history(get().sessionId);
      set({ history });
    } catch {
      /* history is optional; ignore when the backend has no DB */
    }
  },
}));
