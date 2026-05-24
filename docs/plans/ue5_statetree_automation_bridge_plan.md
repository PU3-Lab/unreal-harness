# UE5 StateTree Automation Bridge — 상세 구현 가이드

> 이 문서는 [03_statetree_plan.md](./03_statetree_plan.md)의 **StateTree Bridge 상세 구현 가이드**다.
> 공통 원칙·CLI 규약·`result.json` 표준·디렉터리/네이밍 규약은 [00_overview.md](./00_overview.md)에서만 정의하며,
> 여기서는 StateTree에 특화된 Phase별 구현 순서를 다룬다.

## 1. 최종 목표

Agent가 StateTree 설계/수정 계획을 세우고, `ue-auto ai statetree` 명령(=`UEAutomationBridge` 플러그인의
`UEAuto.StateTreeCommandlet`)을 통해 실제 StateTree 에셋을 안전하게 생성·수정·검증하는 구조를 만든다.

```text
Agent
  ↓
YAML / JSON 작업 계획 생성
  ↓
ue-auto ai statetree <동작>
  ↓
UnrealEditor-Cmd -run=UEAuto.StateTreeCommandlet
  ↓
UEAutomationBridge Editor Plugin
  ↓
StateTree 생성 / State 추가 / 검증 / 리포트
  ↓
Human 최종 리뷰
```

역할 분리는 [00_overview.md §2](./00_overview.md)를 따른다 (Agent / ue-auto CLI / Plugin·Commandlet / Validator / Human).

---

## 2. 전체 시스템 구조

표준 디렉터리는 [00_overview.md §6](./00_overview.md)을 따른다. StateTree 관련 위치만 추리면:

```text
<UEProjectRoot>/
├─ Plugins/
│  └─ UEAutomationBridge/                # Editor Plugin (UEAuto.StateTreeCommandlet 호스트)
├─ Content/
│  └─ StateTreeSpecs/                    # YAML/JSON specs
├─ Source/
│  └─ MyGame/
│     └─ AI/StateTree/                   # Task/Condition C++ classes
├─ Docs/
│  └─ statetree/                         # 조사/규칙/명령 문서
└─ Saved/
   ├─ AutomationReports/                 # snapshot / report / validation / result.json
   └─ Logs/                              # 실행 로그
```

> 산출물은 모두 `Saved/AutomationReports/`(리포트·스냅샷·result.json)와 `Saved/Logs/`(로그)로 통일한다.

---

## 3. 작업 트랙

| 트랙 | 이름 | 목적 |
|---:|---|---|
| A | API 조사 | UE StateTree 편집 가능 범위 확인 |
| B | Bridge Plugin | Unreal 내부에서 StateTree 조작 |
| C | ue-auto 연동 | Agent가 실행할 안정적 인터페이스 |
| D | Snapshot / Validator | 결과 읽기와 검증 |
| E | Spec Runner | YAML/JSON 단계 실행 |
| F | Agent 운영 규칙 | Agent가 안전하게 작업하도록 제한 |

---

## 4. Phase 구조

### Phase 0 — API 조사

**목표**: StateTree를 코드로 편집할 수 있는 경로를 확인한다.

```text
0-1. UE 버전 확인
0-2. StateTree 관련 플러그인 경로 확인 (StateTreeModule / StateTreeEditorModule)
0-3. StateTreeEditor 모듈 Public/Private 헤더 조사
0-4. UStateTreeEditorData 접근 가능 여부 확인
0-5. State 추가 API 또는 내부 구조 확인
0-6. Compile / Save 호출 경로 확인
0-7. Python API로 가능한 범위 확인
```

**산출물**: `Docs/statetree/api_research.md`, `Docs/statetree/feasibility_matrix.md`

**완료 기준**
- 빈 StateTree 생성 가능 여부 확인
- Snapshot export 가능 여부 확인
- AddState 구현 방식 후보 1개 이상 확보
- Compile/Save 방식 후보 1개 이상 확보

---

### Phase 1 — Bridge Plugin 골격

**목표**: `UnrealEditor-Cmd`에서 호출 가능한 최소 Editor Plugin(`UEAutomationBridge`)을 만든다.

```text
1-1. Plugins/UEAutomationBridge 생성
1-2. Editor Module 생성
1-3. Commandlet 생성 (UEAuto.StateTreeCommandlet)
1-4. Action=ping 구현
1-5. result.json 출력 구현 (스키마는 00_overview §7)
```

**실행 예시 (raw commandlet)**

```bash
UnrealEditor-Cmd MyProject.uproject \
  -run=UEAuto.StateTreeCommandlet \
  -Action=ping \
  -Result=Saved/AutomationReports/result.json
```

**ue-auto 래퍼**

```bash
ue-auto ai statetree ping --project ./MyProject.uproject
```

**완료 기준**: 프로젝트 빌드 성공 / commandlet 실행 성공 / `result.json` 생성 성공.

---

### Phase 2 — ue-auto 연동

**목표**: Agent가 사용할 `ue-auto ai statetree` 서브커맨드를 `UEAuto.StateTreeCommandlet`에 연결한다.
(`ue-auto` 디스패처 골격 자체는 [ROADMAP Sprint 0](../../ROADMAP.md)에서 정의)

```text
2-1. project / spec / action / result 인자 매핑
2-2. UNREAL_EDITOR_CMD 환경변수 지원
2-3. macOS/Linux 경로 기본값 지원
2-4. 로그 파일 저장 (Saved/Logs/)
2-5. result.json 출력 (Saved/AutomationReports/)
2-6. exit code 전달
```

**실행 예시**

```bash
ue-auto ai statetree ping --project ./MyProject.uproject
```

**완료 기준**: ping 실행 가능 / 로그 저장 / `result.json` 출력 / 실패 시 non-zero exit code.

---

### Phase 3 — 빈 StateTree 생성

**목표**: Bridge를 통해 빈 StateTree 에셋을 생성한다.

```bash
ue-auto ai statetree create \
  --project ./MyProject.uproject \
  --name ST_Test \
  --path /Game/AI/StateTrees \
  --dry-run
```

**내부 처리**

```text
3-1. AssetToolsModule 로드
3-2. StateTreeFactory 사용
3-3. UStateTree asset 생성
3-4. Package dirty 처리
3-5. Save
3-6. result.json 생성
```

**완료 기준**: `/Game/AI/StateTrees/ST_Test` 생성 / 에디터에서 열림 / 재실행해도 로드 가능 / 중복 생성 방지.

---

### Phase 4 — Snapshot Exporter

**목표**: StateTree 구조를 JSON으로 읽어낸다.

```bash
ue-auto ai statetree snapshot \
  --project ./MyProject.uproject \
  --asset /Game/AI/StateTrees/ST_Test \
  --out Saved/AutomationReports/statetree.snapshot.json
```

**Snapshot 1차 구조**

```json
{
  "asset": "/Game/AI/StateTrees/ST_Test",
  "states": [ { "name": "Root", "children": [] } ],
  "transitions": [],
  "tasks": [],
  "conditions": [],
  "errors": []
}
```

**완료 기준**: asset 로드 가능 / Root·EditorData 정보 export / JSON 저장 가능.

---

### Phase 5 — Validator

**목표**: StateTree 기본 구조를 검증한다. 검증 입력 규약은 [00_overview §5.3](./00_overview.md)(`--asset` 또는 `--snapshot`).

**검증 항목 1차**

```text
Asset:  path valid / exists / class is UStateTree / editor data exists
State:  root exists / no duplicate names / parent references valid
Build:  compile callable / save callable
```

```bash
ue-auto ai statetree validate \
  --project ./MyProject.uproject \
  --asset /Game/AI/StateTrees/ST_Test \
  --out-json Saved/AutomationReports/statetree.validation.json
```

결과 스키마(checks 배열)는 [00_overview §7](./00_overview.md)을 따른다.

**완료 기준**: 성공/실패가 JSON으로 반환 / 실패 사유가 Agent가 읽을 수 있게 명확.

---

### Phase 6 — Add State

**목표**: StateTree에 State 하나를 추가한다.

```bash
ue-auto ai statetree add-state \
  --project ./MyProject.uproject \
  --asset /Game/AI/StateTrees/ST_Test \
  --state Idle \
  --parent Root \
  --dry-run
```

**내부 처리**

```text
6-1. UStateTree asset 로드          6-5. Parent children에 추가
6-2. EditorData 로드                6-6. Compile
6-3. Parent state 찾기              6-7. Save
6-4. 새 State 생성                  6-8. Snapshot → 6-9. Validate
```

**완료 기준**: 에디터에서 Idle 확인 / snapshot에 Idle 표시 / validate 통과.

---

### Phase 7 — Incremental Spec Runner

**목표**: YAML/JSON에 적힌 step을 순서대로 실행한다.

**Spec 예시**

```yaml
asset: /Game/AI/StateTrees/ST_NPC_BasicCombat
steps:
  - create:    { name: ST_NPC_BasicCombat, path: /Game/AI/StateTrees }
  - add_state: { parent: Root, name: Idle }
  - validate:  {}
  - add_state: { parent: Root, name: Patrol }
  - validate:  {}
  - snapshot:  {}
```

**실행**

```bash
ue-auto ai statetree run \
  --project ./MyProject.uproject \
  --spec ./Content/StateTreeSpecs/ST_NPC_BasicCombat.yaml
```

**Runner 규칙**: step 순서대로 / mutation 후 자동 compile·save·snapshot·validate / 실패 시 즉시 중단 / `result.json`에 실패 step 기록.

**완료 기준**: Spec 하나로 create + add_state 여러 개 / 실패 step 명확히 기록.

---

### Phase 8 — Add Transition

**목표**: State 간 Transition을 추가한다. (1차는 Condition 없이 Transition만)

```bash
ue-auto ai statetree add-transition \
  --project ./MyProject.uproject \
  --asset /Game/AI/StateTrees/ST_Test \
  --from Idle \
  --to Patrol \
  --dry-run
```

**검증 항목**: from/target state 존재 / duplicate transition 없음 / compile 가능.

**완료 기준**: 에디터에서 Transition 확인 / snapshot에 표시 / validate 통과.

---

### Phase 9 — Task / Condition 코드 생성기

**목표**: StateTree용 C++ Task / Condition 클래스를 스펙 기반으로 생성한다. (C++ 생성 규약은 [05](./05_cpp_class_generation_plan.md) 연계)

**입력**

```yaml
tasks:
  - name: MoveToTarget
    class: STT_MoveToTarget
    inputs: { TargetActor: AActor*, AcceptanceRadius: float }
conditions:
  - name: CanSeeTarget
    class: STC_CanSeeTarget
    inputs: { TargetActor: AActor* }
```

**출력**

```text
Source/MyGame/AI/StateTree/Tasks/STT_MoveToTarget.{h,cpp}
Source/MyGame/AI/StateTree/Conditions/STC_CanSeeTarget.{h,cpp}
```

**완료 기준**: 생성 C++ 빌드 성공 / 에디터에서 클래스 검색 가능.

---

### Phase 10 — Add Task / Add Condition

**목표**: 생성된 Task / Condition 클래스를 StateTree에 붙인다.

```bash
ue-auto ai statetree add-task \
  --project ./MyProject.uproject \
  --asset /Game/AI/StateTrees/ST_Test \
  --state Patrol \
  --task STT_MoveToTarget \
  --dry-run
```

```bash
ue-auto ai statetree add-condition \
  --project ./MyProject.uproject \
  --asset /Game/AI/StateTrees/ST_Test \
  --from Patrol \
  --to Chase \
  --condition STC_CanSeeTarget \
  --dry-run
```

**완료 기준**: Task가 State에 / Condition이 Transition에 붙음 / compile·save·validate 통과.

---

### Phase 11 — Binding 자동화

**목표**: Context / Parameter / Task Input을 연결한다.

```yaml
bindings:
  - target: Patrol.STT_MoveToTarget.TargetActor
    source: Context.TargetActor
  - target: Patrol.STT_MoveToTarget.AcceptanceRadius
    value: 150.0
```

**우선순위**: 초기 MVP에서는 Binding을 사람이 에디터에서 잡아도 충분하므로 자동화 우선순위는 낮다.

**완료 기준**: source/target property resolve / binding 생성 후 compile 통과 / snapshot에 binding 표시.

---

### Phase 12 — Report Generator

**목표**: 사람 리뷰용 Markdown 리포트를 생성한다. (공통 리포트 포맷은 [00_overview §3](./00_overview.md) 원칙 준수)

```bash
ue-auto ai statetree report \
  --snapshot Saved/AutomationReports/statetree.snapshot.json \
  --out Saved/AutomationReports/ST_NPC_BasicCombat.md
```

**리포트 내용**: State/Transition/Task/Condition count, Compile result, Validation warnings, Snapshot diff, Missing bindings, Unreachable states.

**완료 기준**: Agent와 사람이 모두 읽기 쉬움 / PR 첨부 가능.

---

### Phase 13 — Agent 운영 규칙

**목표**: Agent가 안전하게 브릿지를 사용하도록 규칙화한다.

**파일**: `AGENTS.md`, `Docs/statetree/agent_rules.md`

```md
# StateTree Automation Rules

- Do not edit .uasset files directly.
- Use `ue-auto ai statetree ...` for all StateTree asset changes.
- Prefer one mutation per step.
- Always run snapshot after mutation.
- Always run validate after mutation.
- Stop immediately when result ok=false.
- Do not add transition before source and target states exist.
- Do not add task before class exists and project builds.
- Do not add binding before source and target properties are known.
- Mutation defaults to --dry-run; --apply requires human approval.
```

**완료 기준**: Agent가 직접 `.uasset` 수정 시도 안 함 / 모든 변경은 `ue-auto` 명령으로만 수행.

---

## 5. MVP 범위

```text
MVP
├─ Phase 0: API 조사
├─ Phase 1: Bridge Plugin 골격
├─ Phase 2: ue-auto 연동
├─ Phase 3: create
├─ Phase 4: snapshot
├─ Phase 5: validate
└─ Phase 6: add-state
```

**MVP 성공 기준**: `UnrealEditor-Cmd`로 (1) 빈 StateTree 생성 → (2) Idle State 추가 →
(3) Snapshot export → (4) Validate 통과 → (5) `result.json` 출력.

---

## 6. PR 작업 단위 추천

| PR | 목표 | 산출물 |
|---:|---|---|
| 1 | API 조사 문서 | `Docs/statetree/api_research.md`, `feasibility_matrix.md` |
| 2 | Plugin Skeleton | `Plugins/UEAutomationBridge`, ping commandlet, result.json writer |
| 3 | ue-auto 연동 | `ue-auto ai statetree` 서브커맨드, `Docs/statetree/bridge_commands.md` |
| 4 | create | create 동작, result.json, 기본 로그 |
| 5 | snapshot | snapshot 동작, `Saved/AutomationReports/*.json` |
| 6 | validate | validate 동작, checks result JSON |
| 7 | add-state | add-state, compile/save, snapshot/validate 자동 실행 |
| 8 | Spec Runner | `--spec` 지원, step별 결과 기록, 실패 시 중단 |

---

## 7. 명령 / result.json 표준

`ue-auto ai statetree` 명령 목록과 공통 옵션은 [00_overview §5](./00_overview.md), `result.json`
성공/실패 스키마는 [00_overview §7](./00_overview.md)을 단일 출처로 따른다. (여기서 재정의하지 않는다.)

---

## 8. 우선순위

```text
반드시 먼저:  API 조사 → commandlet 실행 → result.json → create → snapshot → validate → add-state
그 다음:      spec runner → add-transition → report → task/condition codegen → add-task/add-condition
나중:         binding → advanced validation → graph visualization → PR 자동 리포트
```

---

## 9. 정리

전체 진행 순서: API 조사 → Editor Plugin 브릿지 → ue-auto 연동 → result.json 표준 → create →
snapshot → validate → add-state → spec runner → add-transition → task/condition codegen →
add-task/add-condition → binding → report → Agent 운영 규칙화.

첫 MVP는 `create → add-state → snapshot → validate`까지. 이 MVP가 성공하면
Transition·Task·Condition·Binding은 같은 패턴으로 하나씩 확장한다.
