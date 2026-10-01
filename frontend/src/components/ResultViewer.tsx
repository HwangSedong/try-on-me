type Props = { resultUrl?: string; retryCount?: number; error?: string }
export function ResultViewer({ resultUrl, retryCount, error }: Props) {
  if (!resultUrl && !error) return <section className="result empty"><p className="eyebrow">RESULT</p><div className="result-placeholder">생성된 스타일이<br/>여기에 나타납니다</div></section>
  if (error) return <section className="result error"><p className="eyebrow">UNABLE TO GENERATE</p><h2>결과를 만들지 못했어요</h2><p>{error}</p></section>
  return <section className="result"><p className="eyebrow">YOUR NEW LOOK</p><img src={resultUrl} alt="AI가 생성한 가상 피팅 결과"/><p className="result-note">검증 완료 · {retryCount ? `${retryCount}회 재시도 후 생성` : '첫 시도에서 생성'}</p></section>
}

