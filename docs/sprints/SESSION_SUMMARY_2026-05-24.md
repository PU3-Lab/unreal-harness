# Session Summary — 2026-05-24

## 완료 항목

### Sprint 1 — Test/Review 파이프라인 (5개 명령어)

TDD(RED → GREEN → 리뷰 → 수정) 순서로 진행.

| 명령어 | 파일 | 테스트 파일 |
|---|---|---|
| `ue-auto review diff` | `commands/review.py` | `tests/test_review_diff.py` |
| `ue-auto review summarize` | `commands/review.py` | `tests/test_review_summarize.py` |
| `ue-auto build editor` | `commands/build_cmd.py` | `tests/test_build.py` |
| `ue-auto logs analyze` | `commands/logs_cmd.py` | `tests/test_logs.py` |
| `ue-auto test automation` | `commands/test_cmd.py` | `tests/test_test_automation.py` |
| `ue-auto validate all` (stub) | `commands/validate_cmd.py` | `tests/test_validate_cmd.py` |

Sprint 1 최종: **76 passed**

---

### Sprint 2 — Asset 파이프라인

| 명령어 | 파일 | 테스트 파일 |
|---|---|---|
| `ue-auto asset snapshot` | `commands/asset.py` | `tests/test_asset_snapshot.py` |
| `ue-auto asset validate` | `commands/asset.py` | `tests/test_asset_validate.py` |

- `AssetSnapshotCommandlet` C++ 구현 (AssetRegistry 스캔 → JSON 덤프)
- 네이밍 정책 YAML: `docs/asset_rules/assets.naming_policy.yaml`
- Windows 지원: `.bat` → `cmd.exe /c` 래핑, UE 5.3/5.6/5.7 known path

Sprint 2 최종: **106 passed**

---

### Sprint 3 — StateTree AI 파이프라인

| 명령어 | 파일 | 테스트 파일 |
|---|---|---|
| `ue-auto ai statetree snapshot` | `commands/ai_statetree.py` | `tests/test_statetree_snapshot.py` (7) |
| `ue-auto ai statetree report` | `commands/ai_statetree.py` | `tests/test_statetree_report.py` (9) |
| `ue-auto ai statetree validate` | `commands/ai_statetree.py` | `tests/test_statetree_validate.py` (9) |

**검증 규칙:**
- `DEAD_STATE`: transition target이 없는 상태 (root와 root의 첫 번째 자식만 예외)
- `MISSING_TARGET`: transition target이 states[]에 없는 상태

**버그 수정 이력:**
- Dead state 로직: 모든 root 자식이 reachable로 처리되던 문제 → `seen_root_parents`로 첫 번째 자식만 허용
- `--out-json` argparse 중복 등록 오류 (`_add_common_leaf`가 이미 등록)
- `json.JSONDecodeError` 미처리 → `load_snapshot()`에서 `ValueError`로 래핑
- `subprocess.run` 에러 처리 누락 → `capture_output=True` + `FileNotFoundError` 가드 추가
- `s.get("tasks", [])` → `s.get("tasks") or []` (None 값 처리)

**Plugin (C++) — Sprint 3 마무리:**

`StateTreeSnapshotCommandlet.h/.cpp` 신규 추가:
- `-asset=<path>` (필수), `-out=<path>` (선택)
- `FPaths::GetBaseFilename()`으로 asset name 추출
- JSON 직렬화 실패 / 디렉터리 생성 실패 / 파일 쓰기 실패 → return 1 + UE_LOG(Error)
- 현재는 Root 상태만 담은 최소 JSON 출력 (전체 노드 탐색 Sprint 4+ 예정)

Sprint 3 최종: **131 passed, 2 skipped**

---

### 코드 리뷰 루프

`code-reviewer` 에이전트를 구현 완료 후 매번 실행. Sprint 3 리뷰에서 발견된 이슈:

| 심각도 | 내용 | 수정 |
|---|---|---|
| CRITICAL | `FFileHelper::SaveStringToFile()` 반환값 미확인 | 에러 체크 + return 1 추가 |
| CRITICAL | `FJsonSerializer::Serialize()` 반환값 미확인 | 에러 체크 + return 1 추가 |
| HIGH | `FString::Split()` 사용 (fragile) | `FPaths::GetBaseFilename()` 으로 변경 |

---

### LLM 연동 전략 확인

- LLM과 **지금 당장 연결 가능** — Phase 1(bash exec)은 Sprint 1~3 CLI로 충분
- Sprint 4는 연결의 전제 조건이 아니라 LLM이 쓸 수 있는 명령어를 추가하는 것
- Phase 2(MCP 서버): 알파 테스트 완료 후 전환

---

### Sprint 3 후속 — 버그 수정 & 대시보드

**문제 1: `asset validate` 엔진 에셋 false positive**
- 증상: `validate` 실행 시 9,123개 위반 보고 (엔진 에셋 포함)
- 원인: 정책이 `/Game/**` 대상인데 `/Engine/`, `/Script/` 포함 전체 스냅샷(7,935개)을 검사
- 수정: `validate_assets()`에서 `package_path.startswith("/Game/")` 필터 추가
- 결과: 254개 `/Game/` 에셋 중 59개 실제 위반만 감지

**문제 2: 단일 result.json으로 히스토리 불가**
- 증상: 명령어 실행마다 `result.json` 덮어씀 → 이전 결과 손실
- 수정: 명령어별 `<action>.result.json` 분리 (`result.py`에 `default_path()` 추가)
- 신규: `ue-auto status` — 모든 `*.result.json` 읽어 pass/fail 테이블 출력

| 수정/신규 파일 | 내용 |
|---|---|
| `ue_auto/result.py` | `REPORTS_DIR`, `default_path()`, `write(None)` 지원 |
| `ue_auto/commands/status_cmd.py` | 신규 — `_load_results()`, `_cmd_status()` |
| `ue_auto/main.py` | `status_cmd` 등록, `--result` 기본값 `None` |
| `ue_auto/commands/asset.py` | `/Game/` 필터 버그 수정 |
| `tests/test_status_cmd.py` | 신규 — 7개 테스트 |

**실기(MyProject) 검증:**
```
PASS  ping      pong
PASS  snapshot  7,935개 에셋
FAIL  validate  59/254 위반 (정상 감지)
FAIL  diff      MyProject에 main 브랜치 없음 (git 설정 문제)
```

---

## 최종 상태

| 항목 | 값 |
|---|---|
| 테스트 | 138 passed, 2 skipped |
| 구현 명령어 | 12개 (+ 6개 stub) |
| 완료 스프린트 | Sprint 0~3 + 후속 수정 |
| 다음 목표 | Sprint 4: `ue-auto cpp create` |

---

## 수정된 파일 목록

### CLI (`cli/`)
- `ue_auto/commands/review.py` — 신규
- `ue_auto/commands/build_cmd.py` — 신규
- `ue_auto/commands/logs_cmd.py` — 신규
- `ue_auto/commands/test_cmd.py` — 신규
- `ue_auto/commands/validate_cmd.py` — 신규
- `ue_auto/commands/asset.py` — 신규
- `ue_auto/commands/ai_statetree.py` — 신규 (대규모 수정 포함)
- `ue_auto/main.py` — sprint1~3 명령어 등록
- `ue_auto/runner.py` — Windows 경로 추가
- `pyproject.toml` — 의존성 정리

### Tests (`cli/tests/`)
- `test_review_diff.py`, `test_review_summarize.py`, `test_build.py`, `test_logs.py`
- `test_test_automation.py`, `test_validate_cmd.py`
- `test_asset_snapshot.py`, `test_asset_validate.py`
- `test_statetree_snapshot.py`, `test_statetree_report.py`, `test_statetree_validate.py`

### Plugin (`plugin/`)
- `AssetSnapshotCommandlet.h/.cpp` — 신규
- `StateTreeSnapshotCommandlet.h/.cpp` — 신규

### 문서 (`docs/`)
- `docs/sprints/SPRINT_1_PLAN.md` — 신규
- `docs/sprints/SPRINT_2_PLAN.md` — 신규
- `docs/sprints/SPRINT_3_PLAN.md` — 신규 (C++ stub 섹션 포함)
- `docs/USAGE.md` — 신규
- `docs/plans/11_llm_integration.md` — 신규
- `docs/asset_rules/assets.naming_policy.yaml` — 신규
- `PROGRESS.md` — 업데이트

---

## 수정된 파일 목록 (후속 세션 추가분)

### CLI (`cli/`)
- `ue_auto/result.py` — `REPORTS_DIR`, `default_path()`, `write(None)` 지원
- `ue_auto/main.py` — `status_cmd` 등록, `--result` 기본값 `None`
- `ue_auto/commands/status_cmd.py` — 신규
- `ue_auto/commands/asset.py` — `/Game/` 필터 버그 수정

### Tests (`cli/tests/`)
- `tests/test_status_cmd.py` — 신규 (7개 테스트)

### 문서 (`docs/`)
- `docs/USAGE.md` — `ue-auto status` 섹션 추가, `--result` 기본값 수정
- `PROGRESS.md` — 테스트 수(138), 후속 변경 반영

---

## 다음 목표

**Sprint 4** — `ue-auto cpp create` (C++ 클래스 템플릿 생성: Actor, ActorComponent, DataAsset, Interface, Subsystem)
