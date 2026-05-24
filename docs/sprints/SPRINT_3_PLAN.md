# Sprint 3 — StateTree AI 파이프라인

> 상태: ✅ 완료 (2026-05-24)  
> 참조: [03_statetree_plan.md](../plans/03_statetree_plan.md)

---

## 목표

`ue-auto ai statetree` 하위 명령어 파이프라인 구현 — snapshot / report / validate.  
`snapshot`은 C++ commandlet 호출, `report` / `validate`는 순수 Python (snapshot JSON 기반).

---

## 구현 명령어

| 명령어 | 설명 | 구현 방식 |
|---|---|---|
| `ue-auto ai statetree snapshot` | StateTree 구조를 JSON으로 덤프 | C++ commandlet (`StateTreeSnapshotCommandlet`) |
| `ue-auto ai statetree report` | Snapshot JSON → Markdown 리포트 | Pure Python |
| `ue-auto ai statetree validate` | Dead State / Missing Target 검증 | Pure Python |

### Stub (Sprint 4+ 예정)

- `create`, `add-state`, `add-task`, `add-transition`, `add-condition`, `compile`

---

## 검증 규칙

### Dead State (`DEAD_STATE`)

어떤 transition의 target도 아닌 상태 — 단, 예외:

- `parent == None` (root 자체) → 항상 reachable
- Root의 **첫 번째 자식** (root에 explicit transition이 없을 때) → 암묵적 reachable  
  (UE StateTree는 Root 진입 시 첫 번째 자식 상태를 활성화함)

### Missing Target (`MISSING_TARGET`)

`transition.target`이 `states[]`에 존재하지 않는 상태.

---

## Snapshot JSON 스키마

```json
{
  "asset_path": "/Game/AI/StateTrees/ST_Enemy",
  "name": "ST_Enemy",
  "states": [
    {
      "name": "Root",
      "parent": null,
      "tasks": [],
      "transitions": []
    },
    {
      "name": "Patrol",
      "parent": "Root",
      "tasks": ["MoveToTask"],
      "transitions": [{"target": "Chase", "trigger": "HasTarget"}]
    }
  ]
}
```

---

## 테스트

| 파일 | 테스트 수 | 커버리지 |
|---|---|---|
| `tests/test_statetree_snapshot.py` | 7 | missing project/asset/editor, commandlet args, default out, failure, success |
| `tests/test_statetree_report.py` | 9 | missing/not-found, result ok, MD contents (asset, states, tasks, transitions), no out |
| `tests/test_statetree_validate.py` | 9 | missing/not-found, clean tree, dead state, root-child exemption, missing target, multiple violations, JSON/MD output |

**합계: 25 tests, 25 passed**

---

## 파일

- `cli/ue_auto/commands/ai_statetree.py` — 전체 구현
- `cli/tests/test_statetree_snapshot.py`
- `cli/tests/test_statetree_report.py`
- `cli/tests/test_statetree_validate.py`
