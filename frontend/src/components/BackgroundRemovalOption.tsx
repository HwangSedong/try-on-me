type Props = { checked: boolean; onChange: (checked: boolean) => void }

export function BackgroundRemovalOption({ checked, onChange }: Props) {
  return <label className="background-option"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /><span><strong>배경 제거 후 생성</strong><small>배경이 복잡한 사진의 경우 인물과 의류를 분리하면 더 정확한 결과를 얻을 수 있습니다.</small></span></label>
}

