import type { Polygon } from "@workspace/api-client-react";

export type PendingLocation = {
  locationName: string;
  latitude: number;
  longitude: number;
  boundary?: Polygon;
};

const KEY = "fieldshift.pendingLocation";

export function savePending(loc: PendingLocation) {
  sessionStorage.setItem(KEY, JSON.stringify(loc));
}

export function readPending(): PendingLocation | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as PendingLocation) : null;
  } catch {
    return null;
  }
}

export function clearPending() {
  sessionStorage.removeItem(KEY);
}

export const irrigationLabel: Record<string, string> = {
  rainfed: "Rainfed",
  limited: "Limited irrigation",
  fully_irrigated: "Fully irrigated",
};

export const goalLabel: Record<string, string> = {
  conserve_water: "Conserve water",
  soil_health: "Improve soil health",
  productivity: "Raise productivity",
  reduce_risk: "Reduce risk",
};

export function fmtCoord(lat: number, lon: number) {
  return `${Math.abs(lat).toFixed(4)}°${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(4)}°${lon >= 0 ? "E" : "W"}`;
}

export function asset(path: string) {
  return `${import.meta.env.BASE_URL.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}
