import type {
  AskResponse,
  Assumptions,
  CarInfo,
  ComponentDetail,
  ComponentSummary,
  DamageInput,
  HistoryItem,
  SimulateResponse,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const V1 = `${API_BASE}/api/v1`;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${V1}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Backend unreachable. Is the API running?");
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* not JSON */
    }
    const b = body as { detail?: { message?: string } | string; details?: { field: string; message: string }[] } | null;
    const msg =
      (typeof b?.detail === "object" && b.detail?.message) ||
      (typeof b?.detail === "string" && b.detail) ||
      (b?.details?.length ? b.details.map((d) => `${d.field}: ${d.message}`).join("; ") : "") ||
      `Request failed (${res.status})`;
    throw new ApiError(res.status, msg, body);
  }
  return (await res.json()) as T;
}

export interface VehicleStatePayload {
  damages: DamageInput[];
  assumptions: Assumptions;
}

export const api = {
  car: () => request<CarInfo>("/car"),
  components: () => request<ComponentSummary[]>("/components"),
  component: (id: string) => request<ComponentDetail>(`/components/${encodeURIComponent(id)}`),
  simulate: (
    body: VehicleStatePayload & { session_id: string; persist?: boolean; focus?: DamageInput | null; include_curves?: boolean; scenario_id?: string | null },
    signal?: AbortSignal,
  ) => request<SimulateResponse>("/damage/simulate", { method: "POST", body: JSON.stringify(body), signal }),
  ask: (body: VehicleStatePayload & { session_id: string; question: string; selected_component: string | null }) =>
    request<AskResponse>("/ai/ask", { method: "POST", body: JSON.stringify(body) }),
  history: (sessionId: string) => request<HistoryItem[]>(`/history?session_id=${encodeURIComponent(sessionId)}`),
  reportUrl: (reportId: string, format: "md" | "html" | "json") => `${V1}/reports/${reportId}?format=${format}`,
  async exportCsv(body: VehicleStatePayload): Promise<Blob> {
    const res = await fetch(`${V1}/performance/export.csv`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new ApiError(res.status, `CSV export failed (${res.status})`);
    return res.blob();
  },
};

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
