# Sprint 1 구현 계획 — Test/Review 파이프라인

## 목표

Sprint 0 골격 위에 `Git Diff → Build → Log → Test → Review` 파이프라인 5개 명령어를 TDD로 구현한다.

## 신규 파일 구조

```
cli/
  ue_auto/
    commands/
      review.py        # review diff, review summarize
      build_cmd.py     # build editor
      logs_cmd.py      # logs analyze
      test_cmd.py      # test automation
      validate_cmd.py  # validate all (Sprint 1 스텁)
  tests/
    test_review_diff.py
    test_review_summarize.py
    test_build.py
    test_logs.py
    test_test_automation.py
    test_validate_cmd.py
```

## Phase 1: review diff

### 테스트

- `classify_risk(filepath)` → HIGH / MEDIUM / LOW
  - `.uasset`, `.umap` → HIGH
  - `Config/*.ini` → HIGH
  - `.Build.cs`, `.cpp`, `.h` → MEDIUM
  - 나머지 → LOW
- `get_changed_files(base, head)` subprocess 모킹
- `_cmd_review_diff` : result.json + Markdown 출력

### 구현

- `commands/review.py` — `classify_risk()`, `get_changed_files()`, `register()`, `_cmd_review_diff()`
- `main.py` — `review diff` 등록

## Phase 2: logs analyze

### 테스트

- 6개 패턴: UHT_ERROR, COMPILE_ERROR, LINK_ERROR, MISSING_MODULE, DEPRECATED_WARNING, ASSET_WARNING
- 빈 로그 → PASS
- 클린 로그 → PASS
- 오류 포함 로그 → FAIL (exit 1)

### 구현

- `commands/logs_cmd.py` — `analyze_log_lines()`, `_cmd_logs_analyze()`
- `main.py` — `logs analyze` 등록

## Phase 3: build editor

### 테스트

- `--project` 누락 → exit 1
- `find_build_script()` — `UE_BUILD_SCRIPT` env var 우선, `UE_EDITOR_CMD`에서 유도
- subprocess mock returncode 0 → ok=true
- subprocess mock returncode 1 → ok=false, exit 1

### 구현

- `commands/build_cmd.py` — `find_build_script()`, `_editor_target()`, `_build_platform()`, `_cmd_build_editor()`
- `main.py` — `build editor` 등록

## Phase 4: test automation

### 테스트

- `--project` 누락 → exit 1
- editor not found → exit 1
- subprocess mock returncode 0 → PASS
- subprocess mock returncode 1 → FAIL

### 구현

- `commands/test_cmd.py` — `_cmd_test_automation()` (runner.find_editor() 재사용)
- `main.py` — `test automation` 등록

## Phase 5: review summarize

### 테스트

- `reports/` 내 모든 `*.json` 스캔 (review.summary.json 제외)
- 모두 ok=true → PASS, exit 0
- 하나라도 ok=false → FAIL, exit 1
- `review.summary.md` + `review.summary.json` 모두 생성 확인

### 구현

- `review.py`에 `_cmd_review_summarize()` 추가
- `main.py` — `review summarize` 등록

## Phase 6: validate all (스텁)

- `--project` 필수
- Sprint 1 : "no domain validators registered" WARN 반환
- Sprint 2+에서 채워질 플러그인 레지스트리 뼈대

## 완료 기준

| 명령어 | 단위 테스트 | Exit Code | result.json | Markdown |
|---|---|---|---|---|
| `review diff` | ✓ | 0 항상 | ✓ | ✓ |
| `logs analyze` | ✓ | 오류시 1 | ✓ | ✓ |
| `build editor` | ✓ (mock) | 빌드 결과 반영 | ✓ | - |
| `test automation` | ✓ (mock) | 테스트 결과 반영 | ✓ | - |
| `review summarize` | ✓ | 실패시 1 | ✓ | ✓ + JSON |

전체 유닛 테스트: `pytest tests/ -v` (UE 불필요)

## 위험 요소

| 위험 | 대응 |
|---|---|
| `test` 도메인명이 Python 예약어와 충돌 | 파일명 `test_cmd.py`, argparse domain은 `"test"` 문자열 사용 |
| `build` subprocess 호출이 플랫폼 종속 | `find_build_script()`에서 env var + 파생 경로 우선 |
| `review summarize`가 스캔할 JSON 없음 | 빈 dir → PASS (경고 메시지 출력) |
