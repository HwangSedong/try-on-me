type Props = { resultUrl?: string; error?: string }
export function ResultViewer({ resultUrl, error }: Props) {
  if (!resultUrl && !error) return <section className="result empty"><div className="result-placeholder"><span>아직 결과가 없습니다</span><small>왼쪽에서 사진과 아이템을 고른 뒤 만들어 주세요.</small></div></section>
  if (error) return <section className="result error"><h2>결과를 만들지 못했습니다</h2><p>{error}</p></section>
  return <section className="result result-ready"><div className="result-frame"><img src={resultUrl} alt="AI가 생성한 가상 피팅 결과"/></div></section>
}

