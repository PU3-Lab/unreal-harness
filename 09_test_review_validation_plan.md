# 09. 테스트 / 리뷰 / 검증 자동화 작업 계획

## 목표

UE5 자동화 하네스의 중심으로, Build → Asset Validation → Automation Test → Review Report → Human Final Check 흐름을 만든다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| 빌드 테스트 | CLI 빌드 래핑 | 1 |
| Asset Validation | 각 후보 리포트 통합 | 1 |
| Automation Test 실행 | UE Automation Framework | 1 |
| 로그 분석 | 에러 / 경고 분류 | 1 |
| 변경 파일 리뷰 | Git diff 기반 | 1 |
| 위험 변경 감지 | `.uasset`, `.umap`, Config 변경 탐지 | 1 |
| PIE Smoke Test | Editor Command 기반 | 2 |

## 전체 파이프라인

```text
Git Diff
  ↓
Build
  ↓
Asset Validation
  ↓
Automation Test
  ↓
Log Analyzer
  ↓
Review Report
  ↓
Human Final Check
```

## 산출물

| 파일 | 설명 |
|---|---|
| `Saved/AutomationReports/review.summary.md` | 통합 리뷰 리포트 |
| `Saved/AutomationReports/review.summary.json` | Codex용 구조화 결과 |
| `Saved/Logs/build.log` | 빌드 로그 |
| `Saved/Logs/automation_test.log` | 테스트 로그 |
| `Saved/AutomationReports/risk.diff.md` | 변경 위험도 리포트 |

## 작업 단계

### 1단계. Git 변경 파일 분석

```bash
ue-auto review diff \
  --base main \
  --out Saved/AutomationReports/risk.diff.md
```

분류 기준:

| 변경 유형 | 위험도 |
|---|---|
| `.cpp`, `.h` | 중간 |
| `.Build.cs` | 중간~높음 |
| `.uasset` | 높음 |
| `.umap` | 높음 |
| `Config/*.ini` | 높음 |
| `DefaultGameplayTags.ini` | 높음 |

### 2단계. 빌드 실행

```bash
ue-auto build editor \
  --project ./MyProject.uproject \
  --configuration Development \
  --out-log Saved/Logs/build.log
```

### 3단계. 로그 분석

```bash
ue-auto logs analyze \
  --log Saved/Logs/build.log \
  --out Saved/AutomationReports/build.errors.md
```

분석 항목:

- UHT Error
- Compile Error
- Link Error
- Missing Module
- Deprecated API Warning
- Asset Load Warning

### 4단계. Asset Validation 통합 실행

```bash
ue-auto validate all \
  --project ./MyProject.uproject \
  --out-dir Saved/AutomationReports
```

포함 대상:

- Asset Naming / Path
- Blueprint
- Animation
- StateTree / BT
- DataTable
- GameplayTag
- UI

### 5단계. UE Automation Test 실행

```bash
ue-auto test automation \
  --project ./MyProject.uproject \
  --filter Project \
  --out-log Saved/Logs/automation_test.log
```

### 6단계. 통합 리뷰 리포트 생성

```bash
ue-auto review summarize \
  --reports Saved/AutomationReports \
  --logs Saved/Logs \
  --out Saved/AutomationReports/review.summary.md
```

리포트 구성:

- 전체 상태: PASS / WARN / FAIL
- 빌드 결과
- 테스트 결과
- 에셋 검증 결과
- 위험 변경 파일
- 수동 확인 체크리스트
- 다음 추천 명령

## Codex 역할

- 실패 원인 요약
- 수정 우선순위 정렬
- 빌드 오류 패치 제안
- 위험 변경 리뷰 코멘트 작성
- 다음 자동화 명령 선택

## 테스트 기준

- 실패 시 non-zero exit code 반환
- Markdown / JSON 결과 모두 생성
- 같은 입력 리포트에 대해 요약 결과가 안정적
- 심각 오류는 최상단에 표시
- 수동 확인 항목은 별도 섹션으로 분리

## 리스크

| 리스크 | 대응 |
|---|---|
| UE 로그가 너무 김 | 에러 패턴 우선 추출 |
| 경고가 많아 노이즈 발생 | Warning allowlist |
| Automation Test 실행 시간 길어짐 | Smoke / Full 분리 |
| uasset diff 해석 어려움 | 스냅샷 기반 비교 |

## 1차 MVP

- Git 변경 위험도 리포트
- Editor Build 래퍼
- 로그 분석
- Asset Validation 통합 리포트
- Codex용 review.summary.md 생성
