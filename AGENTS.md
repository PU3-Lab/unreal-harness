# UE5 Automation Harness — Agent Instructions

이 프로젝트는 UE5 프로젝트 자동화 CLI(`ue-auto`)를 제공한다.
사용자가 자연어로 요청하면 아래 명령어를 조합해 실행하고, 결과를 한국어로 요약한다.

> **Codex CLI / OpenAI Codex 용.** Claude Code는 `CLAUDE.md`를 사용한다.

## 경로 변수 (실행 전 결정)

```bash
# 1. 하네스 레포 루트
HARNESS_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo /Users/kimkyungpyo/Workspaces/projests/unreal-harness)"

# 2. UE 에디터 바이너리
UE_EDITOR_CMD="${UE_EDITOR_CMD:-$(find '/Users/Shared/Epic Games' -name 'UnrealEditor-Cmd' -type f 2>/dev/null | sort -r | head -1)}"

# 3. UE 프로젝트 (.uproject)
UE_PROJECT="${UE_SMOKE_PROJECT:-$(find ~/Workspaces/Unreal -name '*.uproject' -maxdepth 3 2>/dev/null | head -1)}"

# 4. 리포트 출력 디렉터리 (절대 경로 필수)
UE_REPORTS="$(dirname "$UE_PROJECT")/Saved/AutomationReports"

# 5. 네이밍 정책 YAML
POLICY="$HARNESS_DIR/docs/asset_rules/assets.naming_policy.yaml"
```

경로가 확정되지 않으면 명령 실행 전 사용자에게 확인한다.

## 명령어 레퍼런스

### 연결 확인
```bash
ue-auto validate ping --project "$UE_PROJECT"
```

### 에셋 스냅샷 (UE 실행 필요, ~30초 소요)
```bash
ue-auto asset snapshot \
  --project "$UE_PROJECT" \
  --out "$UE_REPORTS/assets.snapshot.json"
```

### 에셋 네이밍 검증 (스냅샷 필요, UE 불필요)
```bash
ue-auto asset validate \
  --snapshot "$UE_REPORTS/assets.snapshot.json" \
  --policy "$POLICY"
```

### StateTree 스냅샷 (UE 실행 필요)
```bash
ue-auto ai statetree snapshot \
  --project "$UE_PROJECT" \
  --asset /Game/AI/ST_Enemy
```

### StateTree 검증
```bash
ue-auto ai statetree validate \
  --snapshot "$UE_REPORTS/ST_Enemy.snapshot.json"
```

### Git diff 위험도 분석
```bash
ue-auto review diff --base main
```

### 결과 대시보드
```bash
ue-auto status --reports-dir "$UE_REPORTS"
```

## 자연어 → 명령어 매핑 예시

| 사용자 요청 | 실행할 명령어 |
|------------|-------------|
| "에셋 검증해줘" | snapshot → validate → status |
| "네이밍 위반 목록 보여줘" | validate (snapshot 있으면 재사용) |
| "StateTree 문제 있는지 봐줘" | statetree snapshot → validate |
| "뭐가 실패했어?" | status |
| "최근 변경 위험한 거 있어?" | review diff |

## 결과 해석 규칙

- `result.json`의 `ok: true` → PASS
- `ok: false` → `error.message` 또는 `checks[]` 읽어서 원인 설명
- `checks[]` 있으면 건수와 대표 항목 3개 요약
- 모든 답변은 한국어로, 기술 용어(asset class, prefix 등)는 영어 유지

## 실행 순서 원칙

1. snapshot 없으면 먼저 실행 (UE 필요)
2. snapshot 있으면 validate는 UE 없이 즉시 실행
3. 결과는 항상 `status`로 마무리
4. `--apply` 없이는 실제 변경 없음 — 항상 읽기/리포트만
