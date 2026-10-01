const steps = ['이미지를 정제하고 있습니다', '입력한 패션 아이템을 적용하고 있습니다', '안전성을 확인하고 있습니다', '착용 결과를 검증하고 있습니다']
export function GenerationProgress() { return <section className="progress"><p className="eyebrow">AI PIPELINE</p><h2>스타일을 만들고 있어요</h2><ol>{steps.map((step, index) => <li key={step} className={index === 1 ? 'active' : ''}><span>{String(index + 1).padStart(2, '0')}</span>{step}</li>)}</ol></section> }

