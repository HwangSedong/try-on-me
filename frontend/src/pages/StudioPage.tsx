import { useEffect, useRef, useState } from 'react'
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

const sampleAssets = {
  person: { path: '/marketing/person.jpg', name: 'sample-person.jpg' },
  top: { path: '/marketing/cardigan.jpg', name: 'sample-cardigan.jpg' },
  bottom: { path: '/marketing/skirt.jpg', name: 'sample-skirt.jpg' },
  outer: { path: '/marketing/denim-jacket-cutout.png', name: 'sample-denim-jacket.png' },
} as const
const sampleResultUrl = '/marketing/result.jpg'
const mockPreviewMs = 4000
const resultFadeMs = 320

async function loadSampleFile({ path, name }: { path: string; name: string }) {
  const response = await fetch(path)
  if (!response.ok) throw new Error('샘플 이미지를 불러오지 못했습니다.')
  const image = await response.blob()
  return new File([image], name, { type: image.type })
}

export function StudioPage() {
  const [person, setPerson] = useState<File>()
  const [garments, setGarments] = useState<Partial<Record<GarmentCategory, File>>>({})
  const [removeBackground, setRemoveBackground] = useState(true)
  const [resultUrl, setResultUrl] = useState<string>()
  const [error, setError] = useState<string>()
  const [generating, setGenerating] = useState(false)
  const [showMoreItems, setShowMoreItems] = useState(false)
  const [mobileView, setMobileView] = useState<'form' | 'result'>('form')
  const [sampleLoading, setSampleLoading] = useState(false)
  const [mockPreview, setMockPreview] = useState(false)
  const [progressHold, setProgressHold] = useState(false)
  const runToken = useRef(0)
  const showProgress = Boolean(person && (generating || progressHold))
  const hasGarment = Object.values(garments).some(Boolean)
  const canGenerate = Boolean(person && hasGarment && !generating)

  useEffect(() => {
    if (generating) {
      setProgressHold(true)
      return
    }
    if (!progressHold) return
    const timer = window.setTimeout(() => setProgressHold(false), resultFadeMs)
    return () => window.clearTimeout(timer)
  }, [generating, progressHold])

  async function generate() {
    if (!person || !hasGarment) return
    runToken.current += 1
    setMockPreview(false)
    setGenerating(true); setError(undefined); setResultUrl(undefined); setMobileView('result')
    try { const response = await requestGeneration(person, garments, removeBackground); setResultUrl(response.result_url) }
    catch (reason) { setError(reason instanceof Error ? reason.message : '생성 중 오류가 발생했습니다.') }
    finally { setGenerating(false) }
  }

  async function loadSample() {
    runToken.current += 1
    setMockPreview(false)
    setGenerating(false)
    setProgressHold(false)
    setSampleLoading(true)
    setError(undefined)
    try {
      const [samplePerson, sampleTop, sampleBottom, sampleOuter] = await Promise.all([
        loadSampleFile(sampleAssets.person), loadSampleFile(sampleAssets.top), loadSampleFile(sampleAssets.bottom), loadSampleFile(sampleAssets.outer),
      ])
      setPerson(samplePerson)
      setGarments({ top: sampleTop, bottom: sampleBottom, outer: sampleOuter })
      setShowMoreItems(false)
      setResultUrl(undefined)
      setMobileView('form')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '샘플 이미지를 불러오지 못했습니다.')
    } finally {
      setSampleLoading(false)
    }
  }

  async function runMock() {
    const token = ++runToken.current
    setError(undefined)
    setResultUrl(undefined)
    setMobileView('result')
    setSampleLoading(true)
    try {
      const [samplePerson, sampleTop, sampleBottom, sampleOuter] = await Promise.all([
        loadSampleFile(sampleAssets.person), loadSampleFile(sampleAssets.top), loadSampleFile(sampleAssets.bottom), loadSampleFile(sampleAssets.outer),
      ])
      if (runToken.current !== token) return
      setPerson(samplePerson)
      setGarments({ top: sampleTop, bottom: sampleBottom, outer: sampleOuter })
      setShowMoreItems(false)
      setSampleLoading(false)
      setMockPreview(true)
      setGenerating(true)
      await new Promise((resolve) => window.setTimeout(resolve, mockPreviewMs))
      if (runToken.current !== token) return
      setResultUrl(sampleResultUrl)
    } catch (reason) {
      if (runToken.current !== token) return
      setError(reason instanceof Error ? reason.message : '샘플 이미지를 불러오지 못했습니다.')
    } finally {
      if (runToken.current === token) {
        setGenerating(false)
        setMockPreview(false)
        setSampleLoading(false)
      }
    }
  }

  function resetStudio() {
    runToken.current += 1
    setGenerating(false)
    setMockPreview(false)
    setProgressHold(false)
    setPerson(undefined)
    setGarments({})
    setResultUrl(undefined)
    setError(undefined)
    setShowMoreItems(false)
    setMobileView('form')
  }

  return <main className="studio">
    <section className="page-head">
      <div><div className="page-head-title"><h1>새로운 룩 <em>만들기</em></h1><div className="studio-actions"><button type="button" className="sample-button" onClick={loadSample} disabled={sampleLoading || generating}>{sampleLoading ? '샘플 불러오는 중' : '샘플 추가'}</button><button type="button" className="reset-button" onClick={resetStudio} disabled={sampleLoading || generating}>초기화</button><button type="button" className="mock-button" onClick={runMock} disabled={sampleLoading || generating}>목업</button></div></div><p>전신 사진과 입어보고 싶은 아이템을 올려주세요.</p></div>
    </section>
    <div className="mobile-view-switch" role="tablist" aria-label="가상 피팅 화면">
      <button type="button" role="tab" aria-selected={mobileView === 'form'} onClick={() => setMobileView('form')}>사진과 아이템</button>
      <button type="button" role="tab" aria-selected={mobileView === 'result'} onClick={() => setMobileView('result')}>피팅 결과</button>
    </div>
    <div className={`studio-grid mobile-${mobileView}`}>
      <div className="panel form-panel">
        <div className="panel-intro"><div><h2>전신 사진</h2><p>머리부터 발끝까지 보이는 사진이 가장 좋아요.</p></div><small>JPG 또는 PNG</small></div>
        <PersonUploader file={person} onChange={setPerson}/>
        <section className="garments">
          <div className="garment-heading"><div><h2>입어볼 아이템 <small>최소 1개</small></h2></div><span>상의부터 골라보세요</span></div>
          <div className="garment-scroll">
            <div className="garment-grid">{slots.slice(0, showMoreItems ? slots.length : 3).map((slot) => <GarmentUploader key={slot.category} slot={slot} file={garments[slot.category]} onChange={(file) => setGarments((current) => ({ ...current, [slot.category]: file }))}/>)}</div>
            {!showMoreItems ? <button type="button" className="add-items" onClick={() => setShowMoreItems(true)}>+ 신발, 모자, 액세서리 추가</button> : null}
          </div>
        </section>
        <div className="form-actions">
          <BackgroundRemovalOption checked={removeBackground} onChange={setRemoveBackground}/>
          <button className="generate" disabled={!canGenerate} onClick={generate}><span>{generating ? '룩을 만들고 있어요' : '이 룩 입어보기'}</span><b>↗</b></button>
          {!person || !hasGarment ? <p className="validation">전신 사진과 아이템 최소 하나를 선택해 주세요.</p> : null}
        </div>
      </div>
      <aside className="panel result-panel"><div className="result-topline"><span>피팅 결과</span><span>미리보기</span></div><div className="result-stage">{showProgress ? <div className={`result-layer${generating ? '' : ' is-leaving'}`}><GenerationProgress person={person!} garments={garments} stageIntervalMs={mockPreview ? mockPreviewMs / 4 : undefined}/></div> : null}{generating ? null : <div className={`result-layer${showProgress ? ' is-entering' : ''}`}><ResultViewer resultUrl={resultUrl} error={error}/></div>}</div></aside>
    </div>
    <footer>Try-On Me</footer>
  </main>
}
