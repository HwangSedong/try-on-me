type Props = { resultUrl?: string; retryCount?: number; error?: string }
export function ResultViewer({ resultUrl, retryCount, error }: Props) {
  if (!resultUrl && !error) return <section className="result empty"><h2>결과</h2><div className="result-placeholder"><span>아직 결과가 없습니다</span><small>왼쪽에서 사진과 아이템을 고른 뒤 만들어 주세요.</small></div></section>
  if (error) return <section className="result error"><h2>결과를 만들지 못했습니다</h2><p>{error}</p></section>
  return <section className="result"><h2>결과</h2><img src={resultUrl} alt="AI가 생성한 가상 피팅 결과"/><p className="result-note">{retryCount ? `${retryCount}번 다시 만든 결과입니다.` : '한 번에 만든 결과입니다.'}</p></section>
}

