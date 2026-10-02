import type { GarmentCategory, GarmentPreparationResponse, GenerateResponse } from '../types/generation'

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

export async function prepareGarment(image: File, requestedCategory: GarmentCategory): Promise<{ preparation: GarmentPreparationResponse; cutout: File }> {
  const data = new FormData()
  data.append('image', image)
  data.append('requested_category', requestedCategory)
  const response = await fetch(`${API_BASE}/api/garments/prepare`, { method: 'POST', body: data })
  if (!response.ok) {
    const body: { detail?: string } = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? '의류 이미지를 분석하지 못했습니다.')
  }
  const preparation = await response.json() as GarmentPreparationResponse
  const cutoutResponse = await fetch(`${API_BASE}${preparation.cutout_url}`)
  if (!cutoutResponse.ok) throw new Error('의류 컷아웃을 불러오지 못했습니다.')
  const blob = await cutoutResponse.blob()
  return { preparation, cutout: new File([blob], `${requestedCategory}-cutout.png`, { type: 'image/png' }) }
}
