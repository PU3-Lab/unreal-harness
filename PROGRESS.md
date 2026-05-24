# UE Automation Harness — 진행 현황

> 마지막 업데이트: 2026-05-24  
> 테스트: 106 passed, 2 skipped  
> 참조: [전체 설계 개요](docs/plans/00_overview.md) | [CLI 사용법](docs/USAGE.md)

---

## 스프린트 현황

| 스프린트 | 목표 | 상태 | 계획 문서 |
|---|---|---|---|
| Sprint 0 | CLI 골격, Plugin stub, result.json 스키마 | ✅ 완료 | — |
| Sprint 1 | Test/Review 파이프라인 (5개 명령어) | ✅ 완료 | [SPRINT_1_PLAN.md](docs/sprints/SPRINT_1_PLAN.md) |
| Sprint 2 | Asset 네이밍/경로 파이프라인 + Windows 지원 | ✅ 완료 | [SPRINT_2_PLAN.md](docs/sprints/SPRINT_2_PLAN.md) |
| Sprint 3 | StateTree AI 파이프라인 | ⬜ 미착수 | [03_statetree_plan.md](docs/plans/03_statetree_plan.md) |
| Sprint 4 | C++ 클래스 생성 | ⬜ 미착수 | [05_cpp_class_generation_plan.md](docs/plans/05_cpp_class_generation_plan.md) |
| Sprint 5 | DataAsset / DataTable / Config | ⬜ 미착수 | [06_dataasset_datatable_config_plan.md](docs/plans/06_dataasset_datatable_config_plan.md) |
| Sprint 6 | GameplayTag / Input / GAS | ⬜ 미착수 | [07_gameplaytag_input_ability_plan.md](docs/plans/07_gameplaytag_input_ability_plan.md) |
| Sprint 7 | Animation | ⬜ 미착수 | [02_animation_plan.md](docs/plans/02_animation_plan.md) |
| Sprint 8 | UI / UMG | ⬜ 미착수 | [08_ui_umg_plan.md](docs/plans/08_ui_umg_plan.md) |
| Sprint 9 | Blueprint | ⬜ 미착수 | [04_blueprint_plan.md](docs/plans/04_blueprint_plan.md) |
| Sprint 10 | Packaging / Cook / Build | ⬜ 미착수 | [10_packaging_cook_build_plan.md](docs/plans/10_packaging_cook_build_plan.md) |

---

## 구현된 명령어

### ✅ Sprint 0 — 기반 구조

- CLI 골격 (`ue-auto` 엔트리포인트, argparse, `result.json` 스키마)
- `UEAutomationBridge` 플러그인 stub
- `result.py`, `report.py`, `runner.py`

### ✅ Sprint 1 — Test/Review 파이프라인

| 명령어 | 파일 | 테스트 |
|---|---|---|
| `ue-auto review diff` | `commands/review.py` | `tests/test_review_diff.py` |
| `ue-auto review summarize` | `commands/review.py` | `tests/test_review_summarize.py` |
| `ue-auto build editor` | `commands/build_cmd.py` | `tests/test_build.py` |
| `ue-auto logs analyze` | `commands/logs_cmd.py` | `tests/test_logs.py` |
| `ue-auto test automation` | `commands/test_cmd.py` | `tests/test_test_automation.py` |
| `ue-auto validate all` (stub) | `commands/validate_cmd.py` | `tests/test_validate_cmd.py` |

### ✅ Sprint 2 — Asset 파이프라인

| 명령어 | 파일 | 테스트 |
|---|---|---|
| `ue-auto asset snapshot` | `commands/asset.py` | `tests/test_asset_snapshot.py` |
| `ue-auto asset validate` | `commands/asset.py` | `tests/test_asset_validate.py` |

**Plugin:** `AssetSnapshotCommandlet` (C++) — AssetRegistry 스캔 후 JSON 덤프  
**정책 YAML:** `docs/asset_rules/assets.naming_policy.yaml`  
**Windows 지원:** `.bat` → `cmd.exe /c` 래핑, UE 5.3/5.6/5.7 known path, POSIX 경로 변환

---

## 다음 목표: Sprint 3 — StateTree AI 파이프라인

계획 문서: [03_statetree_plan.md](docs/plans/03_statetree_plan.md)

구현 예정 명령어:
```
ue-auto ai statetree snapshot   — StateTree 구조 JSON 덤프
ue-auto ai statetree report     — Markdown 리포트 생성
ue-auto ai statetree validate   — 구조 검증 (Dead State, Transition Target 등)
ue-auto ai statetree create     — StateTree 에셋 생성 (--dry-run 기본)
ue-auto ai statetree add-state
ue-auto ai statetree add-task
ue-auto ai statetree add-transition
ue-auto ai statetree add-condition
ue-auto ai statetree compile
```

---

## 상태 범례

| 아이콘 | 의미 |
|---|---|
| ✅ 완료 | 구현 + 테스트 통과 + 커밋 |
| 🔄 진행중 | 현재 작업 중 |
| ⬜ 미착수 | 계획 문서 있음, 구현 전 |
| 📋 계획없음 | 아직 계획 문서도 없음 |
