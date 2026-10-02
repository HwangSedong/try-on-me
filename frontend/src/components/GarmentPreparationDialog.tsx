import { useEffect, useRef, useState, type PointerEvent } from 'react'
import type { GarmentCategory, GarmentPreparationResponse } from '../types/generation'

const labels: Record<GarmentCategory, string> = { top: '상의', bottom: '하의', outer: '아우터', shoes: '신발', hat: '모자', accessory: '액세서리' }

type Crop = { x: number; y: number; width: number; height: number }

export type PendingGarment = {
  requestedCategory: GarmentCategory
  destinationCategory: GarmentCategory
  preparation: GarmentPreparationResponse
  file: File
  moveResolved?: boolean
  replacementConfirmed?: boolean
}

type Props = {
  pending: PendingGarment
  existingFile?: File
  onMove: () => void
  onKeep: () => void
  onReplace: () => void
  onCancel: () => void
  onUse: (file: File) => void
}

function useObjectUrl(file: File) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const next = URL.createObjectURL(file)
    setUrl(next)
    return () => URL.revokeObjectURL(next)
  }, [file])
  return url
}

function CropEditor({ file, onApply, onBack }: { file: File; onApply: (file: File) => void; onBack: () => void }) {
  const url = useObjectUrl(file)
  const [crop, setCrop] = useState<Crop>({ x: 0.06, y: 0.06, width: 0.88, height: 0.88 })
  const start = useRef<{ x: number; y: number } | null>(null)

  function point(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    return {
      x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
    }
  }

  function begin(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId)
    start.current = point(event)
    setCrop({ x: start.current.x, y: start.current.y, width: 0, height: 0 })
  }

  function draw(event: PointerEvent<HTMLDivElement>) {
    if (!start.current) return
    const end = point(event)
    setCrop({ x: Math.min(start.current.x, end.x), y: Math.min(start.current.y, end.y), width: Math.abs(end.x - start.current.x), height: Math.abs(end.y - start.current.y) })
  }

  function applyCrop() {
    if (crop.width < 0.03 || crop.height < 0.03) return
    const image = new Image()
    image.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.round(image.naturalWidth * crop.width))
      canvas.height = Math.max(1, Math.round(image.naturalHeight * crop.height))
      const context = canvas.getContext('2d')
      if (!context) return
      context.drawImage(image, image.naturalWidth * crop.x, image.naturalHeight * crop.y, canvas.width, canvas.height, 0, 0, canvas.width, canvas.height)
      canvas.toBlob((blob) => { if (blob) onApply(new File([blob], 'garment-crop.png', { type: 'image/png' })) }, 'image/png')
    }
    image.src = url
  }

  return <>
    <div className="crop-instructions"><strong>남길 영역을 드래그해 주세요.</strong><span>배경이나 다른 사람을 제외하고 의류만 감싸면 됩니다.</span></div>
    <div className="crop-editor" onPointerDown={begin} onPointerMove={draw} onPointerUp={() => { start.current = null }} onPointerCancel={() => { start.current = null }}>
      <img src={url} alt="영역을 지정할 의류 컷아웃" draggable={false} />
      <div className="crop-shade crop-top" style={{ height: `${crop.y * 100}%` }} />
      <div className="crop-shade crop-bottom" style={{ top: `${(crop.y + crop.height) * 100}%` }} />
      <div className="crop-shade crop-left" style={{ top: `${crop.y * 100}%`, height: `${crop.height * 100}%`, width: `${crop.x * 100}%` }} />
      <div className="crop-shade crop-right" style={{ top: `${crop.y * 100}%`, left: `${(crop.x + crop.width) * 100}%`, height: `${crop.height * 100}%` }} />
      <div className="crop-selection" style={{ left: `${crop.x * 100}%`, top: `${crop.y * 100}%`, width: `${crop.width * 100}%`, height: `${crop.height * 100}%` }} />
    </div>
    <div className="dialog-actions"><button type="button" className="dialog-primary" onClick={applyCrop} disabled={crop.width < 0.03 || crop.height < 0.03}>이 영역 사용</button><button type="button" onClick={onBack}>컷아웃으로 돌아가기</button></div>
  </>
}

function ReplaceConfirm({ current, next, category, onReplace, onCancel }: { current: File; next: File; category: GarmentCategory; onReplace: () => void; onCancel: () => void }) {
  const currentUrl = useObjectUrl(current)
  const nextUrl = useObjectUrl(next)
  return <div className="garment-dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="replace-title"><section className="garment-dialog"><h2 id="replace-title">{labels[category]}에 이미 사진이 있어요.</h2><p>새로 만든 컷아웃으로 교체할까요? 기존 사진은 복구할 수 없으니 확인 후 진행해 주세요.</p><div className="replace-compare"><figure><img src={currentUrl} alt="현재 있는 사진" /><figcaption>현재 사진</figcaption></figure><span className="replace-arrow" aria-hidden="true">→</span><figure><img src={nextUrl} alt="바꿀 사진" /><figcaption>바꿀 사진</figcaption></figure></div><div className="dialog-actions"><button type="button" className="dialog-primary" onClick={onReplace}>기존 사진 교체</button><button type="button" onClick={onCancel}>취소</button></div></section></div>
}

export function GarmentPreparationDialog({ pending, existingFile, onMove, onKeep, onReplace, onCancel, onUse }: Props) {
  const initialStep = () => !pending.moveResolved && pending.preparation.detected_category !== pending.requestedCategory ? 'move' : existingFile && !pending.replacementConfirmed ? 'replace' : 'preview'
  const [step, setStep] = useState(initialStep)
  const [file, setFile] = useState(pending.file)
  const [editing, setEditing] = useState(false)
  const imageUrl = useObjectUrl(file)
  const qualityWarning = pending.preparation.quality !== 'good'

  useEffect(() => {
    setFile(pending.file)
    setEditing(false)
    setStep(initialStep())
  }, [pending, existingFile])

  if (step === 'move') return <div className="garment-dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="move-title"><section className="garment-dialog"><h2 id="move-title">이 사진은 <em>{labels[pending.preparation.detected_category]}</em>로 인식됐어요.</h2><p>{labels[pending.preparation.detected_category]} 칸으로 이동할까요? 현재 칸에 유지하면 원래 선택한 위치에 그대로 사용합니다.</p><div className="dialog-actions"><button type="button" className="dialog-primary" onClick={onMove}>{labels[pending.preparation.detected_category]}로 이동</button><button type="button" onClick={onKeep}>현재 칸에 유지</button></div></section></div>

  if (step === 'replace' && existingFile) return <ReplaceConfirm current={existingFile} next={file} category={pending.destinationCategory} onReplace={onReplace} onCancel={onCancel} />

  return <div className="garment-dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="preview-title"><section className="garment-dialog garment-preview-dialog"><div className="dialog-heading"><h2 id="preview-title">{labels[pending.destinationCategory]} 컷아웃 준비 완료</h2><span className={`quality-badge ${pending.preparation.quality}`}>{pending.preparation.quality === 'good' ? '품질 양호' : '확인 필요'}</span></div>{editing ? <CropEditor file={file} onApply={(cropped) => { setFile(cropped); setEditing(false) }} onBack={() => setEditing(false)} /> : <><div className="cutout-preview"><img src={imageUrl} alt="자동 추출된 의류 컷아웃" /></div>{qualityWarning ? <div className="cutout-warning"><strong>상품 단독 사진을 권장해요.</strong><span>{pending.preparation.issues.join(' ') || '가려진 부분이나 복잡한 배경 때문에 디테일이 달라질 수 있습니다.'}</span></div> : null}<p className="manual-note">다른 사람이나 배경이 남았다면 영역을 직접 지정해 필요한 부분만 남길 수 있어요.</p><div className="dialog-actions"><button type="button" className="dialog-primary" onClick={() => onUse(file)}>이 컷아웃 사용</button><button type="button" onClick={() => setEditing(true)}>영역 직접 지정</button><button type="button" onClick={onCancel}>다른 사진 선택</button></div></>}</section></div>
}
