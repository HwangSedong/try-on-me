export type GarmentCategory = 'top' | 'bottom' | 'outer' | 'shoes' | 'hat' | 'accessory'

export type GarmentSlot = { category: GarmentCategory; label: string; hint: string }

export type GenerateResponse = { status: 'completed'; result_url: string; retry_count: number }

export type GarmentPreparationResponse = {
  detected_category: GarmentCategory
  confidence: number
  quality: 'good' | 'warning' | 'poor'
  issues: string[]
  cutout_url: string
}
