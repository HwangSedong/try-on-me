# 백엔드 결과 저장소 벤치마크

이 벤치마크는 **백엔드의 요청 처리와 결과 이미지 저장 방식**을 측정합니다. 이미지 생성 모델의 품질이나 OpenAI 응답 지연은 측정하지 않습니다. 외부 API를 호출하지 않으므로 비용이 들지 않습니다.

## 구성

| 파일 | 역할 |
|---|---|
| `bench_server.py` | 지정한 `backend/` 디렉터리의 실제 FastAPI 앱을 불러와 실행합니다. 이미지 생성 Provider와 의류 준비기만 **고정 크기 바이트를 돌려주는 가짜 구현**으로 바꾸고, 메모리·저장소 상태를 보여주는 `/__bench/stats`를 추가합니다. 나머지 요청 경로(업로드 검증, 파이프라인, 결과 저장, 라우트)는 측정 대상 버전의 코드를 그대로 씁니다. |
| `run_benchmark.py` | 서버를 새 프로세스로 띄우고 고정된 작업을 재생합니다. 결과는 `results/<label>.json`(요약)과 `results/<label>.csv`(요청 단위)로 저장합니다. |
| `compare.py` | 여러 결과 JSON을 받아 비교표 `results/comparison.md`를 만듭니다. |
| `Dockerfile` | Python 3.10 + `requirements-prod.txt` 런타임입니다. `--mode docker`에서 사용합니다. |

## 작업 정의

1회 반복은 스튜디오 화면의 실제 흐름과 같습니다.

```
POST /api/garments/prepare → GET /api/cutouts/{id} → POST /api/generate → GET /api/results/{id}
```

- 가짜 Provider가 돌려주는 크기: 결과 2 MiB, 컷아웃 1.5 MiB (`--result-bytes`, `--cutout-bytes`)
  - 근거: 저장소의 실제 생성 예시 `frontend/public/marketing/look-*.png`(1086×1448)는 1.6~2.0 MB입니다. 1254×1254 투명 컷아웃 예시는 2.0 MB이므로, 1024×1024 컷아웃은 약 1.4 MB로 추정했습니다.
  - 매 호출마다 새 버퍼를 만듭니다. 실제 Provider가 base64를 디코딩해 새 `bytes`를 만드는 동작과 같습니다.
- 업로드 이미지: 64×96 인물 PNG와 48×48 의류 PNG (고정)
- 순차 100회 (10, 50, 100회 시점에 스냅숏) → 3초 유휴 → 동시성 8로 100회 추가
- 같은 조건으로 서버를 새로 띄워 3회 반복합니다.

## 실행

```bash
git worktree add ../try-on-me-baseline 119bfff
```
```bash
python benchmarks/run_benchmark.py --mode local --label baseline --backend-dir ../try-on-me-baseline/backend
```
```bash
python benchmarks/run_benchmark.py --mode local --label after --backend-dir backend
```
```bash
python benchmarks/run_benchmark.py --mode local --label after-log-warning --backend-dir backend --log-level WARNING
```
```bash
python benchmarks/compare.py benchmarks/results/baseline.json benchmarks/results/after.json benchmarks/results/after-log-warning.json
```

클라이언트에는 `httpx`, `Pillow`, `psutil`이 필요합니다. 로컬 모드에서는 서버도 같은 인터프리터로 실행합니다.

### `--mode docker` (이번 측정에서는 실행하지 않음)

이 모드는 운영 systemd 설정과 같은 `--memory 384m --memory-swap 384m --cpus 0.4` 컨테이너에서 Python 3.10으로 서버를 실행합니다. 서버가 OOM으로 종료되면 그 시점과 `OOMKilled` 여부를 기록합니다. 이번 작업 환경에서는 Docker Desktop과 Podman VM이 모두 기동에 실패해서 **이 모드는 실행·검증하지 못했습니다.** 측정치는 모두 `--mode local` 결과입니다.

## 해석할 때 주의할 점

- 로컬 모드는 Windows에서 실행되므로 RSS는 Working Set 값이고, 384 MiB 한도를 커널이 강제하지 않습니다. 운영 한도와 비교하는 값은 "그 시점에 운영 환경이었다면 한도를 넘었을 것"이라는 의미입니다.
- Windows 힙과 Linux glibc malloc은 해제된 메모리를 OS에 돌려주는 방식이 다릅니다. 저장소에서 축출한 바이트가 RSS 감소로 이어지는 정도는 Linux에서 다를 수 있습니다.
- 결과 이미지를 저장하는 데이터 증가는 **무제한 보관(unbounded retention)** 문제입니다. 참조를 잃어버린 객체가 회수되지 않는 메모리 누수와는 다른 문제입니다.
- 기존 버전은 관측 로그 핸들러가 없어서 INFO 로그를 실제로 출력하지 않았습니다. 그래서 응답시간은 로그 출력을 끈 `after-log-warning`과 비교해야 공정합니다.
