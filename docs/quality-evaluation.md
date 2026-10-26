# 이미지 품질 수동 평가 기준

> 상태: **평가 양식만 마련되어 있으며, 아직 실제 생성 이미지로 평가하지 않았습니다.**
> 현재 백엔드의 `MockModerationProvider`와 `MockVisionValidationProvider`는 모든 결과를 통과시키는 개발용 구현입니다. 이 서비스는 안전성과 품질을 **자동으로 검증하지 않습니다.**

## 1. 목적

`OutfitPipeline`은 품질 검사 결과를 재시도 근거로 쓰도록 설계되어 있습니다. 하지만 지금은 Vision 검증기가 Mock이라 실제 품질 판단이 없습니다. 이 문서는 실제 Vision 검증기를 붙이기 전에, 사람이 같은 기준으로 결과를 기록하는 방법을 정합니다. 이렇게 모은 기록은 나중에 자동 검증기의 정답 데이터와 비교 기준으로 씁니다.

## 2. 평가 시나리오

`frontend/src/pages/StudioPage.tsx`의 `highDifficultyCases` 10개를 그대로 씁니다. 스튜디오의 "테스트 케이스" 선택기로 같은 인물 사진(`/marketing/person.jpg`)과 의류 조합을 불러올 수 있습니다.

| ID | 시나리오 | 의류 (카테고리: 샘플 파일) | 집중해서 볼 실패 유형 |
|---|---|---|---|
| full-layered | 01 · 6개 아이템 풀 레이어드 | top: cardigan, bottom: skirt, outer: denim-jacket-cutout, shoes: sneakers, hat: cap, accessory: bag | 일부 아이템 누락, 레이어 순서 |
| street-layered | 02 · 재킷·부츠·모자·가방 | top: cardigan, outer: denim-jacket(배경 있음), shoes: boots, hat: cap, accessory: bag | 배경 포함 참조의 반영 |
| outer-over-top | 03 · 상의 위 아우터 겹침 | top: cardigan, outer: trench | 겹침과 가림 처리 |
| lower-body-perspective | 04 · 하의·부츠 원근 | bottom: skirt, shoes: boots, accessory: bag | 다리·발 원근, 비율 |
| accessory-placement | 05 · 모자·가방 위치 | hat: cap, accessory: bag | 착용 위치 |
| outer-only | 06 · 아우터만 교체 | outer: trench | 요청하지 않은 의류 보존 |
| three-piece | 07 · 상의·하의·신발 | top: cardigan, bottom: skirt, shoes: sneakers | 상하의 경계 |
| bottom-only | 08 · 하의만 교체 | bottom: skirt | 상의·신발 보존 |
| shoes-only | 09 · 신발만 교체 | shoes: boots | 발 원근, 나머지 보존 |
| lifestyle-reference | 10 · 배경 있는 재킷 참조 | top: cardigan, outer: denim-jacket(배경 있음), accessory: bag | 참조 배경의 결과 유입 |

## 3. 평가 항목과 점수

각 항목을 0, 1, 2점으로 매깁니다. 기준은 `OutfitGenerator`의 프롬프트와 `QualityResult` 필드에 맞췄습니다.

| 항목 | 2 (통과) | 1 (부분) | 0 (실패) | 대응 필드 |
|---|---|---|---|---|
| A. 인물 보존 | 얼굴, 헤어, 피부톤, 체형, 포즈가 원본과 같은 사람 | 미세한 얼굴·체형 변화 | 다른 사람처럼 보임 | `person_preserved` |
| B. 요청 카테고리 반영 | 요청한 모든 카테고리가 맞는 위치에 있음 | 1개 누락 또는 위치 오류 | 2개 이상 누락 | `garments[*].present` |
| C. 색상·디테일 보존 | 색, 패턴, 소재, 실루엣, 로고, 단추가 참조와 일치 | 일부 디테일 변형 | 다른 옷으로 보임 | `garments[*].match` |
| D. 미요청 의류 보존 | 참조가 없는 카테고리가 원본 그대로 | 경미한 변화 | 다른 옷으로 바뀜 | (프롬프트 규칙) |
| E. 자연스러운 합성 | 주름, 그림자, 조명, 손발이 자연스러움 | 국소 왜곡 | 해부학적 오류 (손가락, 다리 등) | `anatomy_valid` |
| F. 다중 의류 겹침 | 레이어 순서와 가림이 맞음 | 경계 일부 어색함 | 레이어가 뒤섞임 | (해당 시나리오만) |

**합격 기준:** A와 B가 모두 2점이고, 나머지 항목에 0점이 없어야 합니다. 안전성(노출, 부적절한 결과)은 점수와 별도로 실패 시 즉시 불합격으로 표시합니다.

## 4. 실행 조건

- 같은 `.env` 설정: `IMAGE_GENERATION_MODEL`, `IMAGE_GENERATION_QUALITY`, `IMAGE_GENERATION_FORMAT`을 기록합니다.
- 배경 제거 옵션은 현재 Mock이라 결과에 영향을 주지 않습니다. 그래도 켜짐/꺼짐 여부는 기록합니다.
- 시나리오마다 최소 1회, 가능하면 3회 생성합니다. 생성 모델은 같은 입력에도 결과가 달라집니다.
- 백엔드 로그의 `request_id`, 재시도 횟수, OpenAI 토큰 사용량(실제로 반환된 값만)을 함께 기록합니다.
- **실제 OpenAI API 호출은 비용이 듭니다.** 10개 시나리오를 3회씩 실행하면 이미지 편집 요청이 최소 30회 발생합니다. 의류 컷아웃 준비까지 포함하면 호출 수가 더 늘어납니다.

## 5. 기록 양식

`docs/quality-evaluation-log.csv`에 한 줄씩 추가합니다. 생성 이미지 원본은 저장소에 커밋하지 않고, 별도의 비공개 위치에 `request_id` 이름으로 보관합니다.

```csv
date,scenario_id,run,request_id,model,quality,retry_count,A_person,B_categories,C_details,D_unrequested,E_composite,F_layering,safety_fail,pass,notes
```

## 6. 다음 단계

1. 이 양식으로 시나리오 10개를 최소 1회씩 수동 평가합니다. (비용 승인 필요)
2. 실패 사례를 유형별로 묶어 `retry_context` 문구에 반영합니다.
3. Vision 모델 기반 `VisionValidationProvider`를 붙이고, 수동 평가 결과와 일치율을 측정합니다. 이 일치율을 확인하기 전까지는 자동 품질 검증이 동작한다고 표시하지 않습니다.
