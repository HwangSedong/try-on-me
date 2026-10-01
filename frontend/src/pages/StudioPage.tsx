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
  return <main className="studio">
    <section className="page-head">
      <div><h1>새로운 룩을<br /><em>만들어보세요.</em></h1><p>전신 사진과 입어보고 싶은 아이템을 올려주세요.</p></div>
    </section>
    <div className="studio-grid">
      <div className="panel">
        <div className="panel-intro"><div><h2>전신 사진</h2><p>머리부터 발끝까지 보이는 사진이 가장 좋아요.</p></div><small>JPG 또는 PNG</small></div>
        <PersonUploader file={person} onChange={setPerson}/>
        <section className="garments">
          <div className="garment-heading"><div><h2>입어볼 아이템 <small>최소 1개</small></h2></div><span>최대 6개</span></div>
          <div className="garment-grid">{slots.map((slot) => <GarmentUploader key={slot.category} slot={slot} file={garments[slot.category]} onChange={(file) => setGarments((current) => ({ ...current, [slot.category]: file }))}/>)}</div>
        </section>
        <BackgroundRemovalOption checked={removeBackground} onChange={setRemoveBackground}/>
        <button className="generate" disabled={!canGenerate} onClick={generate}><span>{generating ? '룩을 만들고 있어요' : '이 룩 입어보기'}</span><b>↗</b></button>
        {!person || !hasGarment ? <p className="validation">전신 사진과 아이템 하나를 선택해 주세요.</p> : null}
      </div>
      <aside className="panel result-panel"><div className="result-topline"><span>피팅 결과</span><span>미리보기</span></div>{generating ? <GenerationProgress/> : <ResultViewer resultUrl={resultUrl} retryCount={retryCount} error={error}/>}</aside>
    </div>
    <footer>Try-On Me</footer>
  </main>
}

