import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function fmt(v: number | undefined | null, digits = 1): string {
  if (v === undefined || v === null || Number.isNaN(v)) return "-";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signed(v: number, digits = 1): string {
  const s = fmt(Math.abs(v), digits);
  if (Math.abs(v) < 0.5 * 10 ** -digits) return `±${fmt(0, digits)}`;
  return `${v > 0 ? "+" : "−"}${s}`;
}

export function getSessionId(): string {
  const KEY = "apexvision.session";
  try {
    const existing = localStorage.getItem(KEY);
    if (existing && /^[A-Za-z0-9_-]{6,64}$/.test(existing)) return existing;
    const id = `s-${crypto.randomUUID().replace(/-/g, "").slice(0, 20)}`;
    localStorage.setItem(KEY, id);
    return id;
  } catch {
    return `s-${Math.random().toString(36).slice(2, 14)}`;
  }
}
