# UE5 StateTree Automation Bridge 작업 구조

## 1. 최종 목표

Codex가 StateTree 설계/수정 계획을 세우고, Unreal Editor Plugin 브릿지를 통해 실제 StateTree 에셋을 안전하게 생성·수정·검증하는 구조를 만든다.

```text
Codex
  ↓
YAML / JSON 작업 계획 생성
  ↓
run_bridge.sh 실행
  ↓
UnrealEditor-Cmd
  ↓
StateTreeAutomationBridge Editor Plugin
  ↓
StateTree 생성 / State 추가 / 검증 / 리포트
  ↓
Human 최종 리뷰
```

핵심 역할 분리는 다음과 같다.

| 역할 | 담당 |
|---|---|
| Codex | 계획자. 어떤 State, Transition, Task를 넣을지 판단 |
| Bridge Plugin | 실행자. Unreal 내부 API로 StateTree 에셋 수정 |
| Validator | 검사자. Snapshot / Validate / Report 생성 |
| Human | 최종 승인자. 게임플레이 감각과 의도 검토 |

---

## 2. 전체 시스템 구조

```text
MyGame/
├─ Plugins/
│  └─ StateTreeAutomationBridge/        # Unreal Editor Plugin
│
├─ tools/
│  └─ statetree/                        # CLI wrapper scripts
│
├─ Docs/
│  └─ statetree/                        # 조사/규칙/명령 문서
│
├─ Content/
│  └─ StateTreeSpecs/                   # YAML/JSON specs
│
├─ Source/
│  └─ MyGame/
│     └─ AI/StateTree/                  # Task/Condition C++ classes
│
└─ Saved/
   ├─ StateTreeBridge/                  # result.json
   ├─ StateTreeBridgeLogs/              # execution logs
   ├─ StateTreeSnapshots/               # exported snapshots
   └─ StateTreeReports/                 # markdown/html reports
```

---

## 3. 작업 트랙

전체 작업은 6개 트랙으로 나눈다.

| 트랙 | 이름 | 목적 |
|---:|---|---|
| A | API 조사 | UE StateTree 편집 가능 범위 확인 |
| B | Bridge Plugin | Unreal 내부에서 StateTree 조작 |
| C | CLI Wrapper | Codex가 실행할 안정적인 인터페이스 |
| D | Snapshot / Validator | 결과 읽기와 검증 |
| E | Spec Runner | YAML/JSON 단계 실행 |
| F | Codex 운영 규칙 | Codex가 안전하게 작업하도록 제한 |

---

## 4. Phase 구조

# Phase 0 — API 조사

## 목표

StateTree를 코드로 편집할 수 있는 경로를 확인한다.

## 작업

```text
0-1. UE 버전 확인
0-2. StateTree 관련 플러그인 경로 확인
0-3. StateTreeEditor 모듈 Public/Private 헤더 조사
0-4. UStateTreeEditorData 접근 가능 여부 확인
0-5. State 추가 API 또는 내부 구조 확인
0-6. Compile / Save 호출 경로 확인
0-7. Python API로 가능한 범위 확인
```

## 산출물

```text
Docs/statetree/api_research.md
Docs/statetree/feasibility_matrix.md
```

## 완료 기준

```text
- 빈 StateTree 생성 가능 여부 확인
- Snapshot export 가능 여부 확인
- AddState 구현 방식 후보 1개 이상 확보
- Compile/Save 방식 후보 1개 이상 확보
```

---

# Phase 1 — Bridge Plugin 골격

## 목표

UnrealEditor-Cmd에서 호출 가능한 최소 Editor Plugin을 만든다.

## 작업

```text
1-1. Plugins/StateTreeAutomationBridge 생성
1-2. Editor Module 생성
1-3. Commandlet 생성
1-4. Action=ping 구현
1-5. Result JSON 출력 구현
```

## 실행 예시

```bash
UnrealEditor-Cmd MyGame.uproject \
  -run=StateTreeBridge \
  -Action=ping \
  -Result=Saved/StateTreeBridge/result.json
```

## 결과 예시

```json
{
  "ok": true,
  "action": "ping",
  "message": "StateTreeBridge is running"
}
```

## 완료 기준

```text
- 프로젝트 빌드 성공
- UnrealEditor-Cmd에서 Commandlet 실행 성공
- result.json 생성 성공
```

---

# Phase 2 — CLI Wrapper

## 목표

Codex가 사용할 `sh` 실행 래퍼를 만든다.

## 파일

```text
tools/statetree/run_bridge.sh
```

## 작업

```text
2-1. project/spec/action/result 인자 처리
2-2. UNREAL_EDITOR_CMD 환경변수 지원
2-3. macOS/Linux 경로 기본값 지원
2-4. 로그 파일 저장
2-5. result.json 출력
2-6. exit code 전달
```

## 실행 예시

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action ping
```

## 완료 기준

```text
- sh로 ping 실행 가능
- 로그 저장됨
- result.json 출력됨
- 실패 시 non-zero exit code 반환
```

---

# Phase 3 — 빈 StateTree 생성

## 목표

Bridge를 통해 빈 StateTree 에셋을 생성한다.

## 커맨드

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action create-tree \
  --name ST_Test \
  --path /Game/AI/StateTrees
```

## 내부 처리

```text
3-1. AssetToolsModule 로드
3-2. StateTreeFactory 사용
3-3. UStateTree asset 생성
3-4. Package dirty 처리
3-5. Save
3-6. 결과 JSON 생성
```

## 완료 기준

```text
- /Game/AI/StateTrees/ST_Test 생성됨
- 에디터에서 열림
- 저장 후 재실행해도 로드 가능
```

---

# Phase 4 — Snapshot Exporter

## 목표

StateTree 구조를 JSON으로 읽어낸다.

## 커맨드

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action snapshot \
  --asset /Game/AI/StateTrees/ST_Test
```

## Snapshot 1차 구조

```json
{
  "asset": "/Game/AI/StateTrees/ST_Test",
  "states": [
    {
      "name": "Root",
      "children": []
    }
  ],
  "transitions": [],
  "tasks": [],
  "conditions": [],
  "errors": []
}
```

## 완료 기준

```text
- StateTree asset 로드 가능
- Root 또는 기본 EditorData 정보 export 가능
- JSON 파일 저장 가능
```

---

# Phase 5 — Validator

## 목표

StateTree 기본 구조를 검증한다.

## 검증 항목 1차

```text
Asset
- asset path valid
- asset exists
- asset class is UStateTree
- editor data exists

State
- root exists
- no duplicate state names
- parent references valid

Build
- compile callable
- save callable
```

## 커맨드

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action validate \
  --asset /Game/AI/StateTrees/ST_Test
```

## 결과 예시

```json
{
  "ok": true,
  "action": "validate",
  "checks": [
    {
      "name": "asset_exists",
      "ok": true
    },
    {
      "name": "editor_data_exists",
      "ok": true
    },
    {
      "name": "no_duplicate_states",
      "ok": true
    }
  ]
}
```

## 완료 기준

```text
- 성공/실패가 JSON으로 반환됨
- 실패 사유가 Codex가 읽을 수 있게 명확함
```

---

# Phase 6 — Add State

## 목표

StateTree에 State 하나를 추가한다.

## 커맨드

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action add-state \
  --asset /Game/AI/StateTrees/ST_Test \
  --state Idle \
  --parent Root
```

## 내부 처리

```text
6-1. UStateTree asset 로드
6-2. EditorData 로드
6-3. Parent state 찾기
6-4. 새 State 생성
6-5. Parent children에 추가
6-6. Compile
6-7. Save
6-8. Snapshot
6-9. Validate
```

## 완료 기준

```text
- 에디터에서 Idle State 확인 가능
- snapshot에 Idle 표시
- validate 통과
```

---

# Phase 7 — Incremental Spec Runner

## 목표

YAML/JSON에 적힌 step을 순서대로 실행한다.

## Spec 예시

```yaml
asset: /Game/AI/StateTrees/ST_NPC_BasicCombat

steps:
  - create_tree:
      name: ST_NPC_BasicCombat
      path: /Game/AI/StateTrees

  - add_state:
      parent: Root
      name: Idle

  - validate: {}

  - add_state:
      parent: Root
      name: Patrol

  - validate: {}

  - snapshot: {}
```

## 실행

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --spec ./Content/StateTreeSpecs/ST_NPC_BasicCombat.yaml
```

## Runner 규칙

```text
- step은 순서대로 실행
- mutation 후 자동 compile/save
- mutation 후 자동 snapshot
- mutation 후 자동 validate
- 실패하면 즉시 중단
- result.json에 실패 step 기록
```

## 완료 기준

```text
- Spec 하나로 create_tree + add_state 여러 개 가능
- 실패 step이 명확히 기록됨
```

---

# Phase 8 — Add Transition

## 목표

State 간 Transition을 추가한다.

## 커맨드

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action add-transition \
  --asset /Game/AI/StateTrees/ST_Test \
  --from Idle \
  --to Patrol
```

## 1차 범위

초기에는 Condition 없이 Transition만 만든다.

```text
Idle → Patrol
```

## 검증 항목

```text
- from state exists
- target state exists
- duplicate transition 없음
- compile 가능
```

## 완료 기준

```text
- 에디터에서 Transition 확인 가능
- snapshot에 transition 표시
- validate 통과
```

---

# Phase 9 — Task / Condition 코드 생성기

## 목표

StateTree용 C++ Task / Condition 클래스를 스펙 기반으로 생성한다.

## 입력

```yaml
tasks:
  - name: MoveToTarget
    class: STT_MoveToTarget
    inputs:
      TargetActor: AActor*
      AcceptanceRadius: float

conditions:
  - name: CanSeeTarget
    class: STC_CanSeeTarget
    inputs:
      TargetActor: AActor*
```

## 출력

```text
Source/MyGame/AI/StateTree/Tasks/STT_MoveToTarget.h
Source/MyGame/AI/StateTree/Tasks/STT_MoveToTarget.cpp

Source/MyGame/AI/StateTree/Conditions/STC_CanSeeTarget.h
Source/MyGame/AI/StateTree/Conditions/STC_CanSeeTarget.cpp
```

## 완료 기준

```text
- 생성된 C++ 빌드 성공
- Unreal Editor에서 클래스 검색 가능
```

---

# Phase 10 — Add Task / Add Condition

## 목표

생성된 Task / Condition 클래스를 StateTree에 붙인다.

## 커맨드

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action add-task \
  --asset /Game/AI/StateTrees/ST_Test \
  --state Patrol \
  --task STT_MoveToTarget
```

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action add-condition \
  --asset /Game/AI/StateTrees/ST_Test \
  --from Patrol \
  --to Chase \
  --condition STC_CanSeeTarget
```

## 완료 기준

```text
- Task 클래스가 State에 붙음
- Condition 클래스가 Transition에 붙음
- compile/save/validate 통과
```

---

# Phase 11 — Binding 자동화

## 목표

Context / Parameter / Task Input을 연결한다.

## 예시

```yaml
bindings:
  - target: Patrol.STT_MoveToTarget.TargetActor
    source: Context.TargetActor

  - target: Patrol.STT_MoveToTarget.AcceptanceRadius
    value: 150.0
```

## 우선순위

초기 MVP에서는 Binding은 사람이 에디터에서 잡아도 충분하다.  
자동화 우선순위는 낮게 둔다.

## 완료 기준

```text
- source/target property resolve 가능
- binding 생성 후 compile 통과
- snapshot에 binding 표시
```

---

# Phase 12 — Report Generator

## 목표

사람 리뷰용 Markdown/HTML 리포트를 생성한다.

## 파일

```text
Saved/StateTreeReports/ST_NPC_BasicCombat.md
Saved/StateTreeReports/ST_NPC_BasicCombat.html
```

## 리포트 내용

```text
- State count
- Transition count
- Task count
- Condition count
- Compile result
- Validation warnings
- Snapshot diff
- Missing bindings
- Unreachable states
```

## 완료 기준

```text
- Codex와 사람이 모두 읽기 쉬움
- PR에 첨부 가능
```

---

# Phase 13 — Codex 운영 규칙

## 목표

Codex가 안전하게 브릿지를 사용하도록 규칙화한다.

## 파일

```text
.codex/AGENTS.md
Docs/statetree/codex_rules.md
```

## 규칙

```md
# StateTree Automation Rules

- Do not edit .uasset files directly.
- Use tools/statetree/run_bridge.sh for all StateTree asset changes.
- Prefer one mutation per step.
- Always run snapshot after mutation.
- Always run validate after mutation.
- Stop immediately when result ok=false.
- Do not add transition before source and target states exist.
- Do not add task before class exists and project builds.
- Do not add binding before source and target properties are known.
```

## 완료 기준

```text
- Codex가 직접 .uasset 수정 시도하지 않음
- 모든 StateTree 변경은 bridge 명령으로만 수행
```

---

# 5. MVP 범위

처음 MVP는 여기까지만 잡는다.

```text
MVP
├─ Phase 0: API 조사
├─ Phase 1: Bridge Plugin 골격
├─ Phase 2: run_bridge.sh
├─ Phase 3: create_tree
├─ Phase 4: snapshot
├─ Phase 5: validate
└─ Phase 6: add_state
```

## MVP 성공 기준

```text
UnrealEditor-Cmd로 다음을 수행한다.

1. 빈 StateTree 생성
2. Idle State 추가
3. Snapshot export
4. Validate 통과
5. result.json 출력
```

---

# 6. Codex 작업 단위 추천

## PR 1 — API 조사 문서

```text
목표:
StateTree 자동화 가능 범위 조사

산출물:
- Docs/statetree/api_research.md
- Docs/statetree/feasibility_matrix.md
```

## PR 2 — Plugin Skeleton

```text
목표:
StateTreeAutomationBridge Editor Plugin 생성

산출물:
- Plugins/StateTreeAutomationBridge
- ping commandlet
- result.json writer
```

## PR 3 — Shell Wrapper

```text
목표:
Codex가 실행할 run_bridge.sh 작성

산출물:
- tools/statetree/run_bridge.sh
- Docs/statetree/bridge_commands.md
```

## PR 4 — create_tree

```text
목표:
빈 StateTree 에셋 생성

산출물:
- create-tree action
- result.json
- 기본 로그
```

## PR 5 — snapshot

```text
목표:
StateTree 구조 JSON export

산출물:
- snapshot action
- Saved/StateTreeSnapshots/*.json
```

## PR 6 — validate

```text
목표:
기본 검증 추가

산출물:
- validate action
- checks result JSON
```

## PR 7 — add_state

```text
목표:
Root 아래 State 하나 추가

산출물:
- add-state action
- compile/save
- snapshot/validate 자동 실행
```

## PR 8 — Incremental Spec Runner

```text
목표:
YAML/JSON steps 실행

산출물:
- --spec 지원
- step별 결과 기록
- 실패 시 중단
```

---

# 7. 명령 스펙 초안

## 공통

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action <action> \
  --result Saved/StateTreeBridge/result.json
```

## ping

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action ping
```

## create-tree

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action create-tree \
  --name ST_Test \
  --path /Game/AI/StateTrees
```

## snapshot

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action snapshot \
  --asset /Game/AI/StateTrees/ST_Test
```

## validate

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action validate \
  --asset /Game/AI/StateTrees/ST_Test
```

## add-state

```bash
./tools/statetree/run_bridge.sh \
  --project ./MyGame.uproject \
  --action add-state \
  --asset /Game/AI/StateTrees/ST_Test \
  --state Idle \
  --parent Root
```

---

# 8. result.json 표준

## 성공

```json
{
  "ok": true,
  "action": "add-state",
  "asset": "/Game/AI/StateTrees/ST_Test",
  "message": "State added successfully",
  "snapshot": "Saved/StateTreeSnapshots/ST_Test_002.json",
  "checks": [
    {
      "name": "asset_exists",
      "ok": true
    },
    {
      "name": "no_duplicate_states",
      "ok": true
    }
  ]
}
```

## 실패

```json
{
  "ok": false,
  "action": "add-state",
  "asset": "/Game/AI/StateTrees/ST_Test",
  "error": {
    "code": "PARENT_NOT_FOUND",
    "message": "Parent state 'Root' was not found"
  },
  "hint": "Run snapshot to inspect available states."
}
```

---

# 9. 우선순위

## 반드시 먼저

```text
1. API 조사
2. Commandlet 실행
3. result.json
4. create_tree
5. snapshot
6. validate
7. add_state
```

## 그 다음

```text
8. spec runner
9. add_transition
10. report
11. task/condition codegen
12. add_task/add_condition
```

## 나중

```text
13. binding
14. advanced validation
15. graph visualization
16. PR 자동 리포트
```

---

# 10. Codex 첫 지시문

```md
# Task: Plan StateTreeAutomationBridge MVP

Goal:
Create a minimal Unreal Engine Editor automation bridge for StateTree assets.

Scope:
- Research StateTree editor APIs.
- Create Editor plugin skeleton.
- Add Commandlet named StateTreeBridge.
- Add Action=ping.
- Write JSON result to Saved/StateTreeBridge/result.json.
- Add shell wrapper tools/statetree/run_bridge.sh.
- Do not modify .uasset yet.

Rules:
- Do not edit .uasset files directly.
- Use an Editor module, not a Runtime module.
- Keep the first PR limited to plugin skeleton and ping.
- Document all discovered StateTree API paths in Docs/statetree/api_research.md.

Validation:
- Project builds.
- Commandlet runs with UnrealEditor-Cmd.
- result.json is generated.
```

---

# 11. 정리

전체 작업 구조는 다음 순서로 진행한다.

```text
1. API 조사
2. Editor Plugin 브릿지 생성
3. sh 실행 래퍼 생성
4. result.json 표준화
5. create_tree
6. snapshot
7. validate
8. add_state
9. spec runner
10. add_transition
11. task/condition codegen
12. add_task/add_condition
13. binding
14. report
15. Codex 운영 규칙화
```

첫 MVP는 다음까지만 진행한다.

```text
create_tree
→ add_state
→ snapshot
→ validate
```

이 MVP가 성공하면 Transition, Task, Condition, Binding은 같은 패턴으로 하나씩 확장한다.
