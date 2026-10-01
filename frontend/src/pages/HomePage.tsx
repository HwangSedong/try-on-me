export function HomePage() {
  return (
    <main className="home campaign-home">
      <section className="campaign">
        <figure className="campaign-image">
          <img src="/marketing/result.jpg" alt="크림색 카디건과 검정 스커트를 입은 가상 피팅 예시" />
          <figcaption><span>가상 피팅 예시</span><span>전신 사진 + 의류 이미지</span></figcaption>
        </figure>
        <div className="campaign-copy">
          <div><h1>어울리는지<br />생각하지 말고,<br /><em>먼저 입어봐.</em></h1></div>
          <p className="campaign-description">내 사진과 마음에 드는 옷을 올리면<br />AI가 당신만의 새로운 룩을 완성합니다.</p>
          <ul className="fit-requirements" aria-label="가상 피팅 준비물">
            <li><b>전신 사진</b><span>JPG 또는 PNG</span></li>
            <li><b>의류 이미지</b><span>입어보고 싶은 아이템</span></li>
            <li><b>피팅 결과</b><span>새로운 룩을 바로 확인</span></li>
          </ul>
          <a className="campaign-cta" href="/fit"><span>START A NEW LOOK</span><b>가상 피팅 시작하기</b><i aria-hidden="true">→</i></a>
          <p className="campaign-note">계정 없이 바로 시작할 수 있어요.</p>
        </div>
      </section>
    </main>
  )
}

function Spark() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 13.4 9 19 10.4 13.4 11.8 12 17.6 10.6 11.8 5 10.4 10.6 9Z" /><path d="M18 14.2 18.7 16.5 21 17.2 18.7 17.9 18 20.2 17.3 17.9 15 17.2 17.3 16.5Z" /></svg>
}
