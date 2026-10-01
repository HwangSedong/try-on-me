import type { GarmentCategory, GenerateResponse } from '../types/generation'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function requestGeneration(person: File, garments: Partial<Record<GarmentCategory, File>>, removeBackground: boolean): Promise<GenerateResponse> {
  const data = new FormData()
  data.append('person', person)
  Object.entries(garments).forEach(([category, file]) => { if (file) data.append(category, file) })
  data.append('remove_background', String(removeBackground))
  const response = await fetch(`${API_BASE}/api/generate`, { method: 'POST', body: data })
  if (!response.ok) {
    const body: { detail?: string } = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? '생성 요청을 처리하지 못했습니다.')
  }
  const payload = await response.json() as GenerateResponse
  return { ...payload, result_url: `${API_BASE}${payload.result_url}` }
}

