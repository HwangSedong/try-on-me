import { useRef } from 'react'

type Props = { file?: File; onChange: (file?: File) => void }

export function PersonUploader({ file, onChange }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const preview = file ? URL.createObjectURL(file) : undefined
  return <section className="person-section">
    <button type="button" className={`person-drop ${file ? 'filled' : ''}`} onClick={() => input.current?.click()}>
      {preview ? <img src={preview} alt="선택한 사용자 사진" /> : <><span className="plus">+</span><span>사진 추가</span><small>JPG, PNG</small></>}
    </button>
    <div><h2>전신 사진</h2><p className="muted">머리부터 발끝까지 보이는 사진을 올려 주세요.</p>{file && <button className="text-button" type="button" onClick={() => onChange()}>사진 제거</button>}</div>
    <input ref={input} className="sr-only" type="file" accept="image/*" onChange={(e) => onChange(e.target.files?.[0])} />
  </section>
}

