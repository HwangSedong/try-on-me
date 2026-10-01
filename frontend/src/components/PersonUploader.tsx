import { useRef } from 'react'

type Props = { file?: File; onChange: (file?: File) => void }

export function PersonUploader({ file, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const preview = file ? URL.createObjectURL(file) : undefined
  return <section className="person-section">
    <div><p className="eyebrow">01 / YOUR LOOK</p><h2>사용자 전신사진</h2><p className="muted">전신이 잘 보이는 밝고 선명한 사진을 선택해 주세요.</p></div>
    <button type="button" className={`person-drop ${file ? 'filled' : ''}`} onClick={() => input.current?.click()}>
      {preview ? <img src={preview} alt="선택한 사용자 사진" /> : <><span className="plus">+</span><span>전신 사진 업로드</span><small>JPG, PNG, WEBP</small></>}
    </button>
    {file && <button className="text-button" type="button" onClick={() => onChange()}>사진 제거</button>}
    <input ref={input} className="sr-only" type="file" accept="image/*" onChange={(e) => onChange(e.target.files?.[0])} />
  </section>
}

