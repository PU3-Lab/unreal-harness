# 03. StateTree 자동화 작업 계획

## 목표

UE5 StateTree를 **읽기 전용 스냅샷 → 구조 리포트 → 검증 → 제한적 생성** 흐름으로 자동화한다.

핵심 방향은 `.uasset`을 직접 수정하는 방식이 아니라, **UE Editor Plugin / Commandlet을 중간 브릿지로 두고 명령화**하는 것이다.

---

## 기본 원칙

- 처음부터 완성된 트리를 한 번에 만들지 않는다.
- **빈 StateTree에서 하나씩 추가 → 검증 → 리포트 → 승인** 흐름으로 간다.
- Codex는 판단 / 스펙 작성 / 명령 생성 / 리포트 해석을 담당한다.
- UE Editor Plugin 또는 Commandlet은 실제 UE API 접근을 담당한다.
- Shell은 Codex와 UE Plugin 사이의 얇은 브릿지 역할만 한다.
- 1차 MVP에서는 읽기 / 검증 / 리포트 중심으로 시작한다.
- `.uasset` 직접 바이너리 수정은 금지한다.

---

## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| StateTree Snapshot Export | State / Task / Transition 구조 덤프 | 1 |
| State 리포트 | 사람이 읽기 쉬운 Markdown 생성 | 1 |
| Task 리포트 | Task Class / Parameter / Binding 확인 | 1 |
| Transition 리포트 | 조건 / Target / 우선순위 확인 | 1 |
| Dead State 탐지 | Root에서 도달 불가능한 State 탐지 | 1 |
| Transition Target 검증 | 삭제 / 누락 State 참조 방지 | 1 |
| Context Data 검증 | Runtime 누락 오류 예방 | 2 |
| Parameter 타입 검증 | Task / Condition 입력 타입 검증 | 2 |
| Evaluator 검증 | Evaluator 존재 / 참조 / 타입 확인 | 2 |
| 빈 StateTree 생성 | Plugin Command 기반 생성 | 3 |
| State 추가 | 제한적 명령으로 추가 | 3 |
| Task 추가 | 검증 가능한 단위로 추가 | 3 |
| Transition 추가 | 조건 / Target 명시 후 추가 | 3 |

---

## 전체 구조

```text
Codex
  ↓ 스펙 작성 / 명령 판단 / 리포트 해석
Shell Bridge
  ↓ ue-auto 명령 실행
UE Editor Plugin or Commandlet
  ↓ UE API 접근
StateTree Asset
  ↓
Snapshot / Validation / Markdown Report
```

---

## 추천 명령 체계

```bash
ue-auto ai statetree snapshot
ue-auto ai statetree report
ue-auto ai statetree validate
ue-auto ai statetree create
ue-auto ai statetree add-state
ue-auto ai statetree add-task
ue-auto ai statetree add-transition
ue-auto ai statetree compile
```

초기에는 `snapshot`, `report`, `validate`만 먼저 구현한다.

---

## 산출물 구조

| 파일 | 설명 |
|---|---|
| `Docs/ai/statetree.spec.yaml` | 목표 StateTree 구조 스펙 |
| `Docs/ai/statetree.policy.yaml` | 검증 규칙 |
| `Saved/AutomationReports/statetree.snapshot.json` | StateTree 구조 덤프 |
| `Saved/AutomationReports/statetree.report.md` | 사람이 보는 구조 리포트 |
| `Saved/AutomationReports/statetree.validation.json` | Codex가 읽는 검증 결과 |
| `Saved/AutomationReports/statetree.validation.md` | 사람이 보는 검증 리포트 |

---

## 작업 단계

### 1단계. StateTree Snapshot Export

읽기 전용부터 시작한다.

```bash
ue-auto ai statetree snapshot \
  --asset /Game/AI/StateTrees/ST_Enemy \
  --out Saved/AutomationReports/statetree.snapshot.json
```

수집 필드:

- Asset Path
- StateTree 이름
- State 목록
- Parent / Child 관계
- State 별 Tasks
- State 별 Enter Conditions
- State 별 Transitions
- Transition Target
- Transition Condition
- Context Data
- Evaluators
- Parameters
- External Data Handles

완료 기준:

- 지정한 StateTree Asset을 열 수 있다.
- 모든 State 이름과 계층 구조가 JSON에 기록된다.
- Task / Transition / Condition이 누락 없이 기록된다.
- 실패 시 에러 코드와 원인이 리포트된다.

---

### 2단계. Markdown 리포트 생성

Snapshot JSON을 사람이 읽기 쉬운 Markdown으로 변환한다.

```bash
ue-auto ai statetree report \
  --snapshot Saved/AutomationReports/statetree.snapshot.json \
  --out Saved/AutomationReports/statetree.report.md
```

리포트 예시:

```md
# ST_Enemy 구조 리포트

## State Tree Summary

- Asset: /Game/AI/StateTrees/ST_Enemy
- Total States: 4
- Total Tasks: 7
- Total Transitions: 5

## State: Patrol

Tasks:
- FindPatrolPointTask
- MoveToTask

Transitions:
- Patrol -> Chase: HasTarget == true

Warnings:
- 없음
```

완료 기준:

- Codex가 읽기 쉬운 구조여야 한다.
- 사람이 리뷰할 때 State / Task / Transition 관계가 바로 보여야 한다.
- Warning / Error / Info를 구분해서 표시한다.

---

### 3단계. StateTree 구조 검증

```bash
ue-auto ai statetree validate \
  --snapshot Saved/AutomationReports/statetree.snapshot.json \
  --policy Docs/ai/statetree.policy.yaml \
  --out-json Saved/AutomationReports/statetree.validation.json \
  --out-md Saved/AutomationReports/statetree.validation.md
```

검증 규칙:

| 검증 항목 | 목적 |
|---|---|
| Dead State 탐지 | Root에서 도달 불가능한 State 탐지 |
| Missing Target 검사 | Transition Target이 실제 존재하는지 확인 |
| Task Class 로드 확인 | 삭제 / 이동된 Task Class 참조 탐지 |
| Context Data 확인 | Task / Condition에서 필요한 Context 누락 탐지 |
| Parameter 타입 확인 | Bool / Float / Object 등 타입 불일치 탐지 |
| Exit Transition 확인 | 종료 불가능 State 탐지 |
| 이름 규칙 확인 | State 이름 / Task 이름 규칙 유지 |

완료 기준:

- 검증 결과가 `pass`, `warning`, `fail`로 구분된다.
- 실패 항목은 Asset Path, State 이름, 문제 원인, 수정 제안을 포함한다.
- Codex가 다음 명령을 만들 수 있을 정도로 구조화된 JSON을 제공한다.

---

### 4단계. 빈 StateTree 생성

읽기 / 검증이 안정화된 후 제한적 생성을 시작한다.

```bash
ue-auto ai statetree create \
  --name ST_Enemy \
  --path /Game/AI/StateTrees \
  --dry-run
```

실제 적용:

```bash
ue-auto ai statetree create \
  --name ST_Enemy \
  --path /Game/AI/StateTrees \
  --apply
```

완료 기준:

- 빈 StateTree Asset 생성
- 저장 성공
- Snapshot Export 가능
- 같은 명령을 다시 실행해도 중복 생성하지 않음

---

### 5단계. State 단위 추가

```bash
ue-auto ai statetree add-state \
  --asset /Game/AI/StateTrees/ST_Enemy \
  --parent Root \
  --state Patrol \
  --dry-run
```

적용 후 바로 검증한다.

```bash
ue-auto ai statetree validate \
  --asset /Game/AI/StateTrees/ST_Enemy
```

완료 기준:

- 지정한 Parent 아래 State가 생성된다.
- Snapshot에서 새 State가 확인된다.
- 중복 State 생성이 방지된다.
- Parent가 없으면 실패한다.

---

### 6단계. Task 단위 추가

```bash
ue-auto ai statetree add-task \
  --asset /Game/AI/StateTrees/ST_Enemy \
  --state Patrol \
  --task /Script/MyGame.FindPatrolPointTask \
  --param Radius=1200 \
  --dry-run
```

완료 기준:

- Task Class가 로드 가능한지 먼저 검증한다.
- Parameter 이름 / 타입을 확인한다.
- 적용 후 Snapshot에 반영된다.
- 실패 시 어떤 Parameter가 문제인지 표시한다.

---

### 7단계. Transition 단위 추가

```bash
ue-auto ai statetree add-transition \
  --asset /Game/AI/StateTrees/ST_Enemy \
  --from Patrol \
  --to Chase \
  --condition HasTarget=true \
  --dry-run
```

완료 기준:

- From / To State가 모두 존재해야 한다.
- Condition에서 참조하는 Context / Parameter가 존재해야 한다.
- Transition 추가 후 Target 검증을 통과해야 한다.

---

### 8단계. Codex 판단 루프

Codex는 직접 `.uasset`을 수정하지 않고, 다음 형태의 루프만 수행한다.

```text
1. statetree.validation.md 읽기
2. 문제 원인 정리
3. 다음 작업 후보 제안
4. ue-auto 명령 생성
5. dry-run 결과 확인
6. 사용자 승인 후 apply 명령 제안
```

Codex에게 맡길 수 있는 작업:

- 다음에 추가할 State 후보 제안
- 필요한 Task / Condition 스펙 작성
- 잘못된 Transition Target 수정안 작성
- Dead State 해결안 제안
- 검증 실패 원인 요약
- Markdown 리뷰 리포트 생성

Codex에게 맡기면 안 되는 작업:

- `.uasset` 직접 수정
- 검증 없이 대량 State 생성
- 에디터에서 확인해야 하는 감각적 튜닝 자동 적용
- 사용자 승인 없는 `--apply` 실행

---

## Plugin MVP 기능

| 기능 | 설명 |
|---|---|
| `ExportStateTree` | StateTree 구조 JSON Export |
| `GenerateStateTreeReport` | Markdown 리포트 생성 |
| `ValidateStateTree` | 구조 검증 |
| `CreateStateTree` | 빈 StateTree 생성 |
| `AddState` | State 추가 |
| `AddTask` | Task 추가 |
| `AddTransition` | Transition 추가 |
| `CompileAsset` | 에셋 컴파일 |
| `SaveAsset` | 변경된 Asset 저장 |
| `SaveReport` | Markdown / JSON 리포트 저장 |

---

## Shell Bridge 예시

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT="$1"
COMMAND="$2"
shift 2

UE_EDITOR="/Applications/Epic Games/UE_5.5/Engine/Binaries/Mac/UnrealEditor-Cmd"
PLUGIN_CMD="UEAuto.StateTreeCommandlet"

"$UE_EDITOR" "$PROJECT"   -run="$PLUGIN_CMD"   -Command="$COMMAND"   "$@"   -unattended   -nop4   -nosplash
```

---

## 테스트 기준

| 테스트 | 기대 결과 |
|---|---|
| 빈 StateTree 생성 | Asset 생성 성공 |
| Snapshot Export | JSON에 State 구조 기록 |
| State 1개 추가 | Snapshot에 반영 |
| 없는 Parent에 State 추가 | 실패 |
| 없는 Target으로 Transition 추가 | 실패 |
| Dead State 포함 | Validation Warning 발생 |
| Task Class 누락 | Validation Fail 발생 |
| 같은 스펙 2회 적용 | 중복 생성 없음 |

---

## 리스크와 대응

| 리스크 | 대응 |
|---|---|
| StateTree API 공개 범위 제한 | 스냅샷 / 리포트 중심으로 먼저 구현 |
| UE 버전별 API 차이 | UE 5.3 / 5.4 / 5.5 Adapter 분리 |
| 자동 생성 후 에디터 표시 불일치 | Compile / Save / Reload 단계 포함 |
| Codex가 과도한 명령 생성 | dry-run 기본값, apply는 사용자 승인 후 |
| 그래프 구조 변경 위험 | State / Task / Transition 단위로만 제한 |

---

## 1차 MVP 범위

1차는 아래 5개만 만든다.

1. StateTree Snapshot Export
2. State / Task / Transition Markdown 리포트
3. Dead State 탐지
4. Transition Target 검증
5. 빈 StateTree 생성

---

## 추천 진행 순서

1. Plugin에서 StateTree Asset 열기
2. Snapshot JSON Export
3. Markdown Report 생성
4. Validation Rule 최소 3개 구현
   - Dead State
   - Missing Target
   - Missing Task Class
5. Shell Bridge 작성
6. Codex용 명령 예시 문서 작성
7. 빈 StateTree 생성 지원
8. State 추가 지원
9. Task 추가 지원
10. Transition 추가 지원
