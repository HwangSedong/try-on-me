import { useEffect, useState } from 'react'
import type { GarmentCategory } from '../types/generation'

type Props = { person: File; garments: Partial<Record<GarmentCategory, File>>; stageIntervalMs?: number }

const stages = [
  { label: '입력 분석', detail: '인물과 아이템의 형태를 읽고 있어요.' },
  { label: '룩 합성', detail: '선택한 아이템을 자연스럽게 입히고 있어요.' },
  { label: '디테일 조정', detail: '소재, 주름, 빛과 그림자를 다듬고 있어요.' },
  { label: '결과 준비', detail: '완성 이미지를 정리하고 있어요. 곧 결과를 보여드릴게요.' },
]

const categoryLabels: Record<GarmentCategory, string> = { top: '상의', bottom: '하의', outer: '아우터', shoes: '신발', hat: '모자', accessory: '액세서리' }

function useObjectUrl(file?: File) {
  const [url, setUrl] = useState<string>()
  useEffect(() => {
    if (!file) return
    const nextUrl = URL.createObjectURL(file)
    setUrl(nextUrl)
    return () => URL.revokeObjectURL(nextUrl)
  }, [file])
  return url
}

function ReferenceCard({ category, file, active }: { category: GarmentCategory; file: File; active: boolean }) {
  const imageUrl = useObjectUrl(file)
  return <figure className={`generation-reference ${active ? 'is-active' : ''}`}>{imageUrl ? <img src={imageUrl} alt={`선택한 ${categoryLabels[category]}`} /> : null}<figcaption>{categoryLabels[category]}</figcaption></figure>
}

export function GenerationProgress({ person, garments, stageIntervalMs = 2600 }: Props) {
  const [stage, setStage] = useState(0)
  const personUrl = useObjectUrl(person)
  const references = (Object.entries(garments) as [GarmentCategory, File | undefined][]).filter((entry): entry is [GarmentCategory, File] => Boolean(entry[1]))
  useEffect(() => {
    const interval = window.setInterval(() => setStage((current) => Math.min(current + 1, stages.length - 1)), stageIntervalMs)
    return () => window.clearInterval(interval)
  }, [stageIntervalMs])
  return <section className="progress" aria-live="polite">
    <div className="generation-canvas" aria-hidden="true"><div className="canvas-orbit orbit-one" /><div className="canvas-orbit orbit-two" /><div className="generation-person">{personUrl ? <img src={personUrl} alt="" /> : null}<span className="scan-line" /></div><div className="generation-references">{references.slice(0, 3).map(([category, file], index) => <ReferenceCard key={category} category={category} file={file} active={index === Math.min(stage, Math.max(references.length - 1, 0))} />)}</div><div className="generation-spark spark-one" /><div className="generation-spark spark-two" /><div className="generation-spark spark-three" /></div>
    <div className="progress-copy"><div className="progress-label"><span className="live-dot" />AI STYLING IN PROGRESS</div><h2>{stages[stage].label}</h2><p>{stages[stage].detail}</p><div className="stage-track" aria-label={`생성 단계 ${stage + 1} / ${stages.length}`}>{stages.map((item, index) => <span key={item.label} className={index < stage ? 'is-complete' : index === stage ? 'is-current' : ''}><i />{item.label}</span>)}</div></div>
  </section>
}
