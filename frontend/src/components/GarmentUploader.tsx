import { useRef } from 'react'
import type { GarmentSlot } from '../types/generation'

type Props = { slot: GarmentSlot; file?: File; onChange: (file?: File) => void; preparing?: boolean }

export function GarmentUploader({ slot, file, onChange, preparing = false }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const preview = file ? URL.createObjectURL(file) : undefined
  return <div className={`garment-card ${file ? 'selected' : ''}`}>
    <button type="button" onClick={() => input.current?.click()} aria-label={`${slot.label} 이미지 선택`} aria-busy={preparing} disabled={preparing}>
      {preparing ? <span className="garment-preparing"><span className="sr-only">분석 중</span><span className="preparing-wave" aria-hidden="true"><i /><i /><i /><i /></span></span> : preview ? <img src={preview} alt={`선택한 ${slot.label}`} /> : <span className="garment-icon">＋</span>}
    </button>
    <div><strong>{slot.label}</strong><span>{file ? file.name : slot.hint}</span></div>
    {file && <button className="remove" type="button" aria-label={`${slot.label} 제거`} onClick={() => onChange()}>×</button>}
    <input ref={input} className="sr-only" type="file" accept="image/*" onChange={(e) => onChange(e.target.files?.[0])} />
  </div>
}
