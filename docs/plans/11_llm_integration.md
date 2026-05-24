# 11. LLM ↔ ue-auto 통합 전략

> 참조: [00_overview.md](./00_overview.md) — 전체 아키텍처 및 역할 분리  
> 현재 상태: `ue-auto` CLI는 독립 실행형. LLM은 명시적으로 명령을 호출해야 함.

---

## 1. 현재 구조의 갭

`00_overview.md`의 아키텍처 다이어그램에서 "Agent"는 최상단에 위치하지만,
실제로 LLM이 `ue-auto`를 호출하는 경로가 정의되지 않은 상태다.

```text
Agent (LLM)
  ↓  ← 이 연결이 현재 정의되지 않음
ue-auto CLI
  ↓
UnrealEditor-Cmd / Commandlet
  ↓
result.json
```

---

## 2. 통합 옵션 비교

| 방식 | 준비 비용 | LLM 자율도 | 안정성 | 비고 |
|---|---|---|---|---|
| A. 코딩 에이전트 bash exec | 0 (지금 즉시) | 중 | 중 | CLI 문법 오류 가능 |
| B. MCP 서버 | 중 (1~2일) | 높음 | 높음 | 타입 스키마 제공 |
| C. CI/CD 파이프라인 | 높음 | 낮음 | 매우 높음 | 사람 트리거 기반 |

---

## 3. 권장 방식: 단계적 이중 전략

### Phase 1 — 코딩 에이전트 bash exec (지금 ~ Sprint 4)

LLM(Claude Code, Codex 등)이 bash 도구로 `ue-auto` 명령을 직접 실행한다.

```bash
# LLM이 생성하는 예시 호출
ue-auto asset snapshot \
  --project /path/to/MyGame.uproject \
  --out Saved/AutomationReports/assets.snapshot.json

ue-auto asset validate \
  --snapshot Saved/AutomationReports/assets.snapshot.json \
  --policy docs/asset_rules/assets.naming_policy.yaml \
  --result Saved/AutomationReports/asset_validate.json
```

**LLM이 result.json을 읽고 다음 행동을 결정한다:**

```python
# LLM 프롬프트 패턴 (자동화 에이전트 루프)
result = json.load(open("Saved/AutomationReports/asset_validate.json"))
if not result["ok"]:
    # violations 분석 → 수정 제안 생성
    for v in result["checks"]:
        if v["type"] == "PREFIX_VIOLATION":
            suggest_rename(v["asset"], v["expected_prefix"])
```

**장점:** 추가 코드 없이 지금 바로 동작. Sprint 3~4 개발 중에도 활용 가능.  
**단점:** LLM이 CLI 인자 문법을 직접 생성해야 해서 오류 가능성 존재.

---

### Phase 2 — MCP 서버 (Sprint 5 이후)

`ue-auto` 명령어들을 MCP(Model Context Protocol) tool로 래핑한다.
LLM이 `tool_use`로 타입화된 스키마를 통해 호출한다.

#### 구조

```text
mcp_server/
├── server.py          # FastMCP 기반 서버
├── tools/
│   ├── asset.py       # asset_snapshot, asset_validate
│   ├── build.py       # build_editor
│   ├── review.py      # review_diff, review_summarize
│   ├── logs.py        # logs_analyze
│   ├── test.py        # test_automation
│   └── statetree.py   # ai_statetree_*
└── schema/
    └── result.py      # result.json → MCP 응답 변환
```

#### MCP tool 예시 (asset_snapshot)

```python
@mcp.tool()
def asset_snapshot(project: str, out: str | None = None) -> dict:
    """AssetRegistry를 스캔해 에셋 목록을 JSON으로 덤프합니다."""
    args = ["ue-auto", "asset", "snapshot", "--project", project]
    if out:
        args += ["--out", out]
    proc = subprocess.run(args, capture_output=True, text=True)
    return json.loads(Path(result_path).read_text())
```

**LLM 호출 흐름:**

```text
LLM → tool_use: asset_snapshot(project="...", out="...")
  → MCP server → ue-auto CLI 실행
  → result.json 읽기
  → structured response (ok, message, checks[]) 반환
LLM → tool_use 응답 해석 → 다음 tool_use 결정
```

**장점:**
- LLM이 bash 문법 없이 타입 안전한 스키마로 호출
- Claude Desktop, VSCode Copilot, 커스텀 에이전트 모두 재사용 가능
- 오류 응답도 구조화되어 LLM이 자동으로 재시도/분기 가능

---

### Phase 3 — CI/CD (선택, 프로덕션)

GitHub Actions, GitLab CI 등에서 `ue-auto` 명령을 파이프라인으로 실행.
LLM의 자율 실행이 아닌 사람이 PR/커밋을 트리거로 자동 검증.

```yaml
# .github/workflows/ue-validate.yml (예시)
on: [push, pull_request]
jobs:
  validate:
    steps:
      - run: ue-auto review diff --base origin/main
      - run: ue-auto asset validate --snapshot $SNAPSHOT --policy $POLICY
      - run: ue-auto review summarize --reports Saved/AutomationReports
```

**용도:** LLM 자율 루프가 아닌 PR 게이트 용도로 별도 운영.

---

## 4. 선택 기준

```
지금 바로 LLM 통합이 필요한가?
  → YES: Phase 1 (bash exec) 즉시 시작
  → NO: Sprint 4~5까지 CLI 명령어 충분히 쌓은 후 Phase 2

명령어 수가 10개 이상이 되면?
  → Phase 2 (MCP 서버)로 전환. bash exec보다 확장성 훨씬 높음.

프로덕션 팀 CI/CD 통합?
  → Phase 3 (CI/CD), LLM 루프와 독립적으로 운영.
```

---

## 5. LLM 에이전트 루프 패턴

Phase 1/2 공통으로 LLM이 따르는 실행 루프:

```text
1. snapshot  — 현재 상태 캡처 (읽기 전용)
2. validate  — 정책 대비 검증, 위반 목록 획득
3. (인간 검토 요청 또는 자동 판단)
4. create/add — --dry-run으로 변경안 생성
5. 리포트 생성 (Markdown)
6. 인간 최종 승인
7. --apply로 실제 적용
```

이 루프는 `00_overview.md` 섹션 3의 **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 원칙과 일치한다.

---

## 6. 실행 계획 (타임라인)

**원칙: CLI 인터페이스가 알파 테스트로 충분히 검증된 후 MCP로 전환한다.**  
MCP schema를 먼저 정의하면 CLI 변경 시 이중 수정이 발생한다.

| 시점 | 작업 | 비고 |
|---|---|---|
| 지금 ~ Sprint 10 | **Phase 1: bash exec 알파 테스트** | CLI 명령어 구축 + 실제 UE 프로젝트 검증 |
| 알파 테스트 완료 후 | **Phase 2: MCP 서버 구축** | 안정된 CLI 인터페이스를 그대로 tool로 래핑 |
| Phase 2 완료 후 | `claude mcp add ue-auto ...` 등록 | Claude Code plugin으로 사용 가능 |
| 프로덕션 준비 시 | Phase 3: CI/CD 설정 | 팀 합의 후 |

### 알파 테스트 완료 기준

MCP 전환을 결정하기 전에 다음이 충족되어야 한다:

- [ ] 모든 CLI 명령어 옵션이 실제 UE 프로젝트에서 검증됨
- [ ] `result.json` 스키마가 안정화됨 (breaking change 없음)
- [ ] 핵심 사용자 피드백 반영 완료
- [ ] Sprint 3~5 (StateTree, C++, DataAsset) 명령어 검증 포함
