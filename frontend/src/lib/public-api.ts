import type { PublicDashboardData } from "./types"

const API_BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://localhost:5055" : "")

export async function fetchDashboard(token: string): Promise<PublicDashboardData> {
  const res = await fetch(`${API_BASE}/api/public/dashboard/${token}`, {
    headers: { "Content-Type": "application/json" },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(body.error || "Failed to load dashboard")
  }
  return res.json()
}

export function downloadCsv(token: string): void {
  const url = `${API_BASE}/api/public/dashboard/${token}/csv`
  window.open(url, "_blank")
}
