export function HomePage() {
  return (
    <main className="home">
      <section className="tryon-showcase">
        <div className="showcase-intro">
          <div className="showcase-copy">
            <h1>Try it on.</h1>
            <p>내 사진에 원하는 옷을 바로 입혀보세요.</p>
          </div>
          <a className="showcase-start" href="/fit">가상 피팅 시작하기 <span aria-hidden="true">→</span></a>
        </div>
        <div className="showcase-flow">
          <figure className="showcase-photo">
            <img src="/marketing/person.jpg" alt="가상 피팅에 사용할 전신 사진 예시" />
            <figcaption><span>01</span>YOUR PHOTO</figcaption>
          </figure>
          <section className="showcase-item" aria-label="입어볼 아이템 예시">
            <img className="showcase-garment" src="/marketing/denim-jacket-cutout.png" alt="진청색 데님 재킷" />
            <div className="showcase-item-copy"><span>02</span><small>SELECTED ITEM</small><strong>Denim Jacket</strong><p>Outerwear&nbsp;&nbsp;·&nbsp;&nbsp;Denim</p></div>
            <div className="item-options" aria-label="다른 아이템 예시">
              <img className="active" src="/marketing/denim-jacket-cutout.png" alt="선택된 데님 재킷" />
              <img src="/marketing/trench.jpg" alt="트렌치코트" />
              <img src="/marketing/cardigan.jpg" alt="카디건" />
              <img src="/marketing/bag.jpg" alt="검은 가방" />
            </div>
          </section>
          <figure className="showcase-result">
            <img src="/marketing/look-preserved.png" alt="같은 인물이 데님 재킷을 입은 가상 피팅 결과 예시" />
            <figcaption><span>03</span>RESULT</figcaption>
          </figure>
        </div>
      </section>
    </main>
  )
}

function Spark() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 13.4 9 19 10.4 13.4 11.8 12 17.6 10.6 11.8 5 10.4 10.6 9Z" /><path d="M18 14.2 18.7 16.5 21 17.2 18.7 17.9 18 20.2 17.3 17.9 15 17.2 17.3 16.5Z" /></svg>
}
