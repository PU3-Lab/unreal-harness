# Sprint 3 후속 — StateTree 파이프라인 완성

> 상태: ⬜ 미착수  
> 참조: [03_statetree_plan.md](../plans/03_statetree_plan.md)

---

## 목표

Sprint 3에서 스텁으로 남긴 StateTree 기능을 실제 동작하도록 완성한다.  
핵심은 두 가지: **Snapshot C++ 완전 구현**, **spec 기반 wire**.

---

## 작업 항목

### 1. StateTreeSnapshotCommandlet 완성 (C++)

현재 Root 상태만 출력하는 스텁. 실제 StateTree 구조 전체를 덤프해야 한다.

수집 필드:
- State 목록 + Parent/Child 계층
- State별 Tasks (Class 이름 + InstanceData 파라미터)
- State별 Enter Conditions (Class 이름 + bInvert + 파라미터)
- State별 Transitions (Trigger + Type + Target + Conditions)
- Evaluators (Class 이름 + 파라미터)
- Parameters (외부 주입 파라미터)

완료 기준:
- `snapshot` 결과 JSON에 Task/Transition/Condition 모두 포함
- 기존 `report`, `validate` 테스트 통과 유지

---

### 2. wire — spec.yaml 기반으로 전환

현재 Idle/Flee 하드코딩. 임의 구조를 spec에서 읽어 배선해야 한다.

```yaml
# wire.spec.yaml 예시
statetree:
  asset: /Game/AI/ST_EnemyAI
  states:
    - name: Idle
      transitions:
        - trigger: OnTick
          target: Flee
          conditions:
            - class: IsPlayerNear
              radius: 500
    - name: Flee
      tasks:
        - class: FleeTask
          flee_distance: 1000
      transitions:
        - trigger: OnTick
          target: Idle
          conditions:
            - class: IsPlayerNear
              radius: 500
              invert: true
```

```bash
ue-auto ai statetree wire \
  --spec wire.spec.yaml \
  --project MyGame.uproject
```

완료 기준:
- spec.yaml에서 State/Task/Transition/Condition 구조를 읽어 배선
- 기존 `--asset` 직접 지정 방식도 하위 호환 유지
- dry-run 지원 (배선 계획만 출력, 실제 적용 안 함)

---

### 3. validate 규칙 추가

| 규칙 | 코드 | 설명 |
|---|---|---|
| Exit Transition 없는 상태 탐지 | `NO_EXIT_TRANSITION` | Transition이 없고 leaf 상태인 경우 |
| Evaluator 참조 검증 | `INVALID_EVALUATOR` | Evaluator Class가 비어있는 경우 |
| 중복 State 이름 탐지 | `DUPLICATE_STATE` | 같은 이름의 State가 2개 이상 |
| spec vs snapshot 일치 검증 | `SPEC_MISMATCH` | 예상 구조와 실제 구조 불일치 |

```bash
ue-auto ai statetree validate \
  --snapshot statetree.snapshot.json \
  --spec wire.spec.yaml    # spec 있으면 일치 검증 추가
```

---

### 4. 단위 명령어 구현 (stub → 실 구현)

| 명령어 | 설명 |
|---|---|
| `add-state` | 지정 Parent 아래 State 추가 |
| `add-task` | State에 Task 추가 (Class + 파라미터) |
| `add-transition` | State에 Transition 추가 (From/To/Condition) |
| `add-condition` | 기존 Transition에 Condition 추가 |
| `compile` | StateTree 에셋 컴파일만 단독 실행 |

모두 C++ commandlet 기반. dry-run 기본값, `--apply`로 실제 적용.

---

## 명령어 전체 목록 (완성 후)

```bash
ue-auto ai statetree snapshot    # C++ — 전체 구조 덤프
ue-auto ai statetree report      # Python — Markdown 리포트
ue-auto ai statetree validate    # Python — 구조 검증 (규칙 추가)
ue-auto ai statetree create      # Python/UE — 에셋 생성
ue-auto ai statetree wire        # C++ — spec 기반 상태 배선
ue-auto ai statetree add-state   # C++ — State 단위 추가
ue-auto ai statetree add-task    # C++ — Task 단위 추가
ue-auto ai statetree add-transition  # C++ — Transition 단위 추가
ue-auto ai statetree add-condition   # C++ — Condition 단위 추가
ue-auto ai statetree compile     # C++ — 에셋 컴파일
```

---

## 작업 우선순위

| 우선순위 | 항목 | 이유 |
|---|---|---|
| 1 | Snapshot C++ 완성 | report/validate의 입력값이 부실하면 전체가 의미없음 |
| 2 | wire spec.yaml 지원 | Idle/Flee 하드코딩은 실사용 불가 |
| 3 | validate 규칙 추가 | Snapshot 완성 후 의미있는 검증 가능 |
| 4 | 단위 명령어 | 파이프라인 완성 후 세분화 |
