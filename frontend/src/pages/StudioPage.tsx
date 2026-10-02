import { useEffect, useRef, useState } from 'react'
import { BackgroundRemovalOption } from '../components/BackgroundRemovalOption'
import { GarmentUploader } from '../components/GarmentUploader'
import { GarmentPreparationDialog, type PendingGarment } from '../components/GarmentPreparationDialog'
import { GenerationProgress } from '../components/GenerationProgress'
import { PersonUploader } from '../components/PersonUploader'
import { ResultViewer } from '../components/ResultViewer'
import { prepareGarment, requestGeneration } from '../services/generationApi'
import type { GarmentCategory, GarmentSlot } from '../types/generation'

const slots: GarmentSlot[] = [
  { category: 'top', label: '상의', hint: '티셔츠, 셔츠, 니트' }, { category: 'bottom', label: '하의', hint: '팬츠, 스커트' },
  { category: 'outer', label: '아우터', hint: '재킷, 코트' }, { category: 'shoes', label: '신발', hint: '스니커즈, 부츠' },
  { category: 'hat', label: '모자', hint: '캡, 비니' }, { category: 'accessory', label: '액세서리', hint: '가방, 안경 등' },
]

const personAsset = { path: '/marketing/person.jpg', name: 'sample-person.jpg' }
const garmentAssets = {
  cardigan: { path: '/marketing/cardigan.jpg', name: 'sample-cardigan.jpg' },
  skirt: { path: '/marketing/skirt.jpg', name: 'sample-skirt.jpg' },
  denimCutout: { path: '/marketing/denim-jacket-cutout.png', name: 'sample-denim-jacket-cutout.png' },
  denimLifestyle: { path: '/marketing/denim-jacket.png', name: 'sample-denim-jacket.png' },
  trench: { path: '/marketing/trench.jpg', name: 'sample-trench.jpg' },
  sneakers: { path: '/marketing/sneakers.jpg', name: 'sample-sneakers.jpg' },
  boots: { path: '/marketing/boots.jpg', name: 'sample-boots.jpg' },
  cap: { path: '/marketing/cap.jpg', name: 'sample-cap.jpg' },
  bag: { path: '/marketing/bag.jpg', name: 'sample-bag.jpg' },
} as const
type GarmentAssetKey = keyof typeof garmentAssets
type TestCase = { id: string; label: string; garments: { category: GarmentCategory; asset: GarmentAssetKey }[] }

const highDifficultyCases: TestCase[] = [
  { id: 'full-layered', label: '01 · 6개 아이템 풀 레이어드', garments: [{ category: 'top', asset: 'cardigan' }, { category: 'bottom', asset: 'skirt' }, { category: 'outer', asset: 'denimCutout' }, { category: 'shoes', asset: 'sneakers' }, { category: 'hat', asset: 'cap' }, { category: 'accessory', asset: 'bag' }] },
  { id: 'street-layered', label: '02 · 재킷·부츠·모자·가방 레이어', garments: [{ category: 'top', asset: 'cardigan' }, { category: 'outer', asset: 'denimLifestyle' }, { category: 'shoes', asset: 'boots' }, { category: 'hat', asset: 'cap' }, { category: 'accessory', asset: 'bag' }] },
  { id: 'outer-over-top', label: '03 · 상의 위 아우터 겹침', garments: [{ category: 'top', asset: 'cardigan' }, { category: 'outer', asset: 'trench' }] },
  { id: 'lower-body-perspective', label: '04 · 하의·부츠 원근 처리', garments: [{ category: 'bottom', asset: 'skirt' }, { category: 'shoes', asset: 'boots' }, { category: 'accessory', asset: 'bag' }] },
  { id: 'accessory-placement', label: '05 · 모자·가방 위치 정확도', garments: [{ category: 'hat', asset: 'cap' }, { category: 'accessory', asset: 'bag' }] },
  { id: 'outer-only', label: '06 · 아우터만 교체 · 원본 보존', garments: [{ category: 'outer', asset: 'trench' }] },
  { id: 'three-piece', label: '07 · 상의·하의·신발 3종 합성', garments: [{ category: 'top', asset: 'cardigan' }, { category: 'bottom', asset: 'skirt' }, { category: 'shoes', asset: 'sneakers' }] },
  { id: 'bottom-only', label: '08 · 하의만 교체 · 원본 보존', garments: [{ category: 'bottom', asset: 'skirt' }] },
  { id: 'shoes-only', label: '09 · 신발만 교체 · 발 원근', garments: [{ category: 'shoes', asset: 'boots' }] },
  { id: 'lifestyle-reference', label: '10 · 배경 있는 재킷 참조', garments: [{ category: 'top', asset: 'cardigan' }, { category: 'outer', asset: 'denimLifestyle' }, { category: 'accessory', asset: 'bag' }] },
]
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
  const [selectedTestCase, setSelectedTestCase] = useState('')
  const [preparingCategories, setPreparingCategories] = useState<GarmentCategory[]>([])
  const [pendingQueue, setPendingQueue] = useState<PendingGarment[]>([])
  const prepareEpoch = useRef(0)
  const prepareTokens = useRef<Partial<Record<GarmentCategory, number>>>({})
  const runToken = useRef(0)
  const activePending = pendingQueue[0]
  const showProgress = Boolean(person && (generating || progressHold))
  const hasGarment = Object.values(garments).some(Boolean)
  const preparing = preparingCategories.length > 0
  const canGenerate = Boolean(person && hasGarment && !generating && !preparing)

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
    if (!person || !hasGarment || preparingCategories.length > 0) return
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
    stopPreparations()
    try {
      const [samplePerson, sampleTop, sampleBottom, sampleOuter] = await Promise.all([
        loadSampleFile(personAsset), loadSampleFile(garmentAssets.cardigan), loadSampleFile(garmentAssets.skirt), loadSampleFile(garmentAssets.denimCutout),
      ])
      setPerson(samplePerson)
      setGarments({ top: sampleTop, bottom: sampleBottom, outer: sampleOuter })
      setShowMoreItems(false)
      setResultUrl(undefined)
      setMobileView('form')
      setSelectedTestCase('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '샘플 이미지를 불러오지 못했습니다.')
    } finally {
      setSampleLoading(false)
    }
  }

  async function loadTestCase(testCaseId: string) {
    setSelectedTestCase(testCaseId)
    const testCase = highDifficultyCases.find((item) => item.id === testCaseId)
    if (!testCase) return
    runToken.current += 1
    setMockPreview(false)
    setGenerating(false)
    setProgressHold(false)
    setSampleLoading(true)
    setError(undefined)
    stopPreparations()
    try {
      const [testPerson, loadedGarments] = await Promise.all([
        loadSampleFile(personAsset),
        Promise.all(testCase.garments.map(async ({ category, asset }) => [category, await loadSampleFile(garmentAssets[asset])] as const)),
      ])
      setPerson(testPerson)
      setGarments(Object.fromEntries(loadedGarments) as Partial<Record<GarmentCategory, File>>)
      setShowMoreItems(testCase.garments.some(({ category }) => ['shoes', 'hat', 'accessory'].includes(category)))
      setResultUrl(undefined)
      setMobileView('form')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '테스트 케이스 이미지를 불러오지 못했습니다.')
    } finally {
      setSampleLoading(false)
    }
  }

  function stopPreparations() {
    prepareEpoch.current += 1
    setPreparingCategories([])
    setPendingQueue([])
  }

  function markPreparing(category: GarmentCategory, active: boolean) {
    setPreparingCategories((current) => {
      const listed = current.includes(category)
      if (active) return listed ? current : [...current, category]
      return listed ? current.filter((item) => item !== category) : current
    })
  }

  function patchPending(patch: Partial<PendingGarment>) {
    setPendingQueue((current) => current.length === 0 ? current : [{ ...current[0], ...patch }, ...current.slice(1)])
  }

  function dismissPending() {
    setPendingQueue((current) => current.slice(1))
  }

  async function handleGarmentUpload(category: GarmentCategory, file?: File) {
    const epoch = prepareEpoch.current
    const token = (prepareTokens.current[category] ?? 0) + 1
    prepareTokens.current[category] = token
    const currentRequest = () => prepareEpoch.current === epoch && prepareTokens.current[category] === token
    if (!file) {
      markPreparing(category, false)
      setPendingQueue((current) => current.filter((item) => item.requestedCategory !== category && item.destinationCategory !== category))
      setGarments((current) => ({ ...current, [category]: undefined }))
      return
    }
    markPreparing(category, true)
    setError(undefined)
    try {
      const { preparation, cutout } = await prepareGarment(file, category)
      if (!currentRequest()) return
      setPendingQueue((current) => [...current.filter((item) => item.requestedCategory !== category), { requestedCategory: category, destinationCategory: category, preparation, file: cutout }])
    } catch (reason) {
      if (!currentRequest()) return
      setError(reason instanceof Error ? reason.message : '의류 이미지를 분석하지 못했습니다.')
    } finally {
      if (currentRequest()) markPreparing(category, false)
    }
  }

  function usePreparedGarment(file: File) {
    if (!activePending) return
    setGarments((current) => ({ ...current, [activePending.destinationCategory]: file }))
    dismissPending()
  }

  async function runMock() {
    const token = ++runToken.current
    setError(undefined)
    setResultUrl(undefined)
    setMobileView('result')
    setSampleLoading(true)
    stopPreparations()
    try {
      const [samplePerson, sampleTop, sampleBottom, sampleOuter] = await Promise.all([
        loadSampleFile(personAsset), loadSampleFile(garmentAssets.cardigan), loadSampleFile(garmentAssets.skirt), loadSampleFile(garmentAssets.denimCutout),
      ])
      if (runToken.current !== token) return
      setPerson(samplePerson)
      setGarments({ top: sampleTop, bottom: sampleBottom, outer: sampleOuter })
      setShowMoreItems(false)
      setSelectedTestCase('')
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
    setSelectedTestCase('')
    stopPreparations()
  }

  return <main className="studio">
    <section className="page-head">
      <div><div className="page-head-title"><h1>새로운 룩 <em>만들기</em></h1><div className="studio-actions"><button type="button" className="sample-button" onClick={loadSample} disabled={sampleLoading || generating}>{sampleLoading ? '샘플 불러오는 중' : '샘플 추가'}</button><button type="button" className="reset-button" onClick={resetStudio} disabled={sampleLoading || generating}>초기화</button><button type="button" className="mock-button" onClick={runMock} disabled={sampleLoading || generating}>목업</button><label className="test-case-select"><span className="sr-only">고난도 테스트 케이스</span><select value={selectedTestCase} onChange={(event) => loadTestCase(event.target.value)} disabled={sampleLoading || generating}><option value="">고난도 테스트 10종</option>{highDifficultyCases.map((testCase) => <option key={testCase.id} value={testCase.id}>{testCase.label}</option>)}</select></label></div></div><p>전신 사진과 입어보고 싶은 아이템을 올려주세요.</p></div>
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
            <div className="garment-grid">{slots.slice(0, showMoreItems ? slots.length : 3).map((slot) => <GarmentUploader key={slot.category} slot={slot} file={garments[slot.category]} onChange={(file) => handleGarmentUpload(slot.category, file)} preparing={preparingCategories.includes(slot.category)}/>)}</div>
            {!showMoreItems ? <button type="button" className="add-items" onClick={() => setShowMoreItems(true)}>+ 신발, 모자, 액세서리 추가</button> : null}
          </div>
        </section>
        <div className="form-actions">
          <BackgroundRemovalOption checked={removeBackground} onChange={setRemoveBackground}/>
          <button className="generate" disabled={!canGenerate} onClick={generate}><span>{generating ? '룩을 만들고 있어요' : '이 룩 입어보기'}</span><b>↗</b></button>
          {preparing ? <p className="validation">의류 분석이 끝나면 입어볼 수 있어요.</p> : !person || !hasGarment ? <p className="validation">전신 사진과 아이템 최소 하나를 선택해 주세요.</p> : null}
        </div>
      </div>
      <aside className="panel result-panel"><div className="result-topline"><span>피팅 결과</span><span>미리보기</span></div><div className="result-stage">{showProgress ? <div className={`result-layer${generating ? '' : ' is-leaving'}`}><GenerationProgress person={person!} garments={garments} stageIntervalMs={mockPreview ? mockPreviewMs / 4 : undefined}/></div> : null}{generating ? null : <div className={`result-layer${showProgress ? ' is-entering' : ''}`}><ResultViewer resultUrl={resultUrl} error={error}/></div>}</div></aside>
    </div>
    {activePending ? <GarmentPreparationDialog key={activePending.requestedCategory} pending={activePending} existingFile={garments[activePending.destinationCategory]} onMove={() => patchPending({ destinationCategory: activePending.preparation.detected_category, moveResolved: true })} onKeep={() => patchPending({ destinationCategory: activePending.requestedCategory, moveResolved: true })} onReplace={() => patchPending({ replacementConfirmed: true })} onCancel={dismissPending} onUse={usePreparedGarment} /> : null}
    <footer>Try-On Me</footer>
  </main>
}
