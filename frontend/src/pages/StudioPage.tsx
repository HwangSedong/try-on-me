import { useState } from 'react'
import { BackgroundRemovalOption } from '../components/BackgroundRemovalOption'
import { GarmentUploader } from '../components/GarmentUploader'
import { GenerationProgress } from '../components/GenerationProgress'
import { PersonUploader } from '../components/PersonUploader'
import { ResultViewer } from '../components/ResultViewer'
import { requestGeneration } from '../services/generationApi'
import type { GarmentCategory, GarmentSlot } from '../types/generation'

const slots: GarmentSlot[] = [
  { category: 'top', label: '상의', hint: '티셔츠, 셔츠, 니트' }, { category: 'bottom', label: '하의', hint: '팬츠, 스커트' },
  { category: 'outer', label: '아우터', hint: '재킷, 코트' }, { category: 'shoes', label: '신발', hint: '스니커즈, 부츠' },
  { category: 'hat', label: '모자', hint: '캡, 비니' }, { category: 'accessory', label: '액세서리', hint: '가방, 안경 등' },
]

export function StudioPage() {
  const [person, setPerson] = useState<File>()
  const [garments, setGarments] = useState<Partial<Record<GarmentCategory, File>>>({})
  const [removeBackground, setRemoveBackground] = useState(true)
  const [resultUrl, setResultUrl] = useState<string>()
  const [retryCount, setRetryCount] = useState<number>()
  const [error, setError] = useState<string>()
  const [generating, setGenerating] = useState(false)
  const hasGarment = Object.values(garments).some(Boolean)
  const canGenerate = Boolean(person && hasGarment && !generating)

  async function generate() {
    if (!person || !hasGarment) return
    setGenerating(true); setError(undefined); setResultUrl(undefined)
    try { const response = await requestGeneration(person, garments, removeBackground); setResultUrl(response.result_url); setRetryCount(response.retry_count) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '생성 중 오류가 발생했습니다.') }
    finally { setGenerating(false) }
  }
  return <main>
    <header><a className="brand" href="/">TRY-ON<span>ME</span></a><span className="header-note">AI VIRTUAL STYLING STUDIO</span></header>
    <section className="hero"><p className="eyebrow">MULTI-GARMENT · MULTIMODAL AI</p><h1>당신의 다음 룩을<br/><em>먼저 만나보세요.</em></h1><p>사진 속 당신을 그대로 유지한 채, 원하는 패션 아이템을 자연스럽게 입혀드립니다.</p></section>
    <div className="studio-grid"><div className="controls"><PersonUploader file={person} onChange={setPerson}/><section className="garments"><p className="eyebrow">02 / STYLE PIECES</p><h2>착용할 아이템 <small>최소 1개 선택</small></h2><div className="garment-grid">{slots.map((slot) => <GarmentUploader key={slot.category} slot={slot} file={garments[slot.category]} onChange={(file) => setGarments((current) => ({ ...current, [slot.category]: file }))}/>)}</div></section><BackgroundRemovalOption checked={removeBackground} onChange={setRemoveBackground}/><button className="generate" disabled={!canGenerate} onClick={generate}>{generating ? 'LOOK 생성 중...' : 'GENERATE LOOK'}<span>↗</span></button>{!person || !hasGarment ? <p className="validation">전신 사진과 한 가지 이상의 아이템을 선택해 주세요.</p> : null}</div><aside>{generating ? <GenerationProgress/> : <ResultViewer resultUrl={resultUrl} retryCount={retryCount} error={error}/>}</aside></div>
    <footer>Try-On-Me v2 · AI-assisted virtual styling. Results are for creative preview only.</footer>
  </main>
}

