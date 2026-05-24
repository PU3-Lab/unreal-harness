# 00. 전체 개요 / 아키텍처 / CLI 규약 (단일 출처)

이 문서는 UE5 자동화 하네스의 **단일 출처(Single Source of Truth)** 다.
공통 원칙, `ue-auto` CLI 규약, 하네스 구성, 표준 디렉터리, `result.json` 표준,
네이밍 규약은 **여기서만 정의**하고 나머지 문서(01~10, StateTree Bridge)는 이 문서를 참조한다.

---

## 1. 비전

Agent(LLM)가 직접 `.uasset`을 건드리지 않는다. Agent는 **계획·스펙·명령·리포트 해석**만 맡고,
실제 UE 내부 접근은 **Editor Plugin / Commandlet**이 담당한다. 모든 변경은
**읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로만 흐른다.

```text
Agent
  ↓ 스펙(YAML/JSON) 작성 / 명령 판단 / 리포트 해석
ue-auto CLI (얇은 브릿지)
  ↓ UnrealEditor-Cmd commandlet 호출
UE Editor Plugin / Commandlet
  ↓ UE 내부 API 접근
Asset (StateTree / Blueprint / DataTable / ...)
  ↓
Snapshot / Validation / Markdown Report / result.json
  ↓
Human 최종 승인
```

---

## 2. 역할 분리

| 역할 | 담당 | 책임 |
|---|---|---|
| Agent | 계획자 | 스펙 작성, 명령 생성, 리포트 해석, 수정안 제안 |
| ue-auto CLI | 브릿지 | 인자 파싱, commandlet 실행, 로그/exit code 전달 |
| Editor Plugin / Commandlet | 실행자 | UE API로 snapshot/생성/검증/저장 |
| Validator | 검사자 | 정책 대비 검증, pass/warning/fail 판정 |
| Human | 승인자 | 게임플레이 감각·의도 최종 검토, `--apply` 승인 |

---

## 3. 공통 원칙 (모든 도메인 공통 — 여기서만 정의)

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Agent는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.
- 변형(mutation) 명령은 **`--dry-run`이 기본값**이고, 실제 적용은 **`--apply` + 사람 승인** 후에만 한다.

---

## 4. 하네스 구성 (플러그인 / 컴포넌트)

### 4.1 커스텀 Editor 플러그인 — `UEAutomationBridge`

하네스가 직접 만드는 **Editor 전용 플러그인 1개**. 런타임 패키징에 포함되지 않는다.
이 플러그인이 모든 commandlet의 호스트다.

| 항목 | 값 |
|---|---|
| 플러그인 이름 | `UEAutomationBridge` |
| 모듈 타입 | `Editor` (LoadingPhase: `PostEngineInit` 또는 `Default`) |
| 실행 진입점 | `UnrealEditor-Cmd <project> -run=<Commandlet>` |
| 대표 Commandlet | `UEAuto.StateTreeCommandlet`, `UEAuto.AssetCommandlet`, `UEAuto.DataCommandlet` … (도메인별) |
| 출력 | `Saved/AutomationReports/*`, `result.json`, `Saved/Logs/*` |

### 4.2 의존 엔진 모듈/플러그인 (신규 제작 아님)

| 모듈/플러그인 | 용도 | 관련 도메인 |
|---|---|---|
| `AssetRegistry`, `AssetTools` | 에셋 목록/메타/생성 | 01, 03 |
| `EditorScriptingUtilities` | 에디터 자동화 (Shipping 제외) | 전반 |
| `DataValidation` (`UEditorValidatorBase`) | 네이티브 검증 프레임워크 | 01, 04, 06, 08 |
| `StateTreeModule` / `StateTreeEditorModule` | StateTree 조작 (※ 버전별 Experimental/Beta — Phase 0 조사 필요) | 03 |
| `GameplayAbilities` | GAS Ability/AttributeSet | 07 |
| `EnhancedInput` | InputAction/IMC | 07 |
| `AutomationController` / Functional Testing | Automation Test 실행 | 09 |
| `PythonScriptPlugin` (선택) | 조사/프로토타이핑 한정 (본 실행은 Commandlet) | 03 |

### 4.3 검증 구현 방침 (하이브리드)

- **공용 에셋 검증**(네이밍/경로/Parent/필수필드 등)은 UE 내장 **DataValidation** 프레임워크(`UEditorValidatorBase`)에 얹어 에디터 "Validate Assets" 메뉴와도 통합한다.
- **프레임워크 밖 검증**(StateTree 구조, Dead State, Transition Target 등)은 해당 commandlet 안에서 **자체 검증**으로 구현한다.

---

## 5. 통합 CLI 규약 — `ue-auto`

### 5.1 문법

```text
ue-auto <도메인> <동작> [옵션...]
```

- 공통 옵션: `--project <path>.uproject`, `--out <path>` / `--out-md` / `--out-json`, `--result <path>`
- 변형 명령 공통: `--dry-run`(기본) / `--apply`
- 모든 명령은 성공 시 0, 실패 시 non-zero exit code를 반환하고 `result.json`을 쓴다.

### 5.2 명령 인덱스 (도메인 → 동작 → 정의 문서)

| 도메인 | 대표 명령 | 정의 문서 |
|---|---|---|
| `asset` | `snapshot`, `validate` | [01](./01_asset_path_naming_plan.md) |
| `anim` | `generate-instance`, `validate-blendspace`, `validate-montage`, `validate-anim-bp` | [02](./02_animation_plan.md) |
| `ai statetree` | `snapshot`, `report`, `validate`, `create`, `add-state`, `add-task`, `add-transition`, `add-condition`, `compile` | [03](./03_statetree_plan.md), [Bridge 상세](./ue5_statetree_automation_bridge_plan.md) |
| `bp` | `snapshot`, `validate` | [04](./04_blueprint_plan.md) |
| `cpp` | `generate`, `generate-class`, `validate-buildcs`, `validate-reflection`, `analyze-uht` | [05](./05_cpp_class_generation_plan.md) |
| `data` | `validate-source`, `validate-datatable`, `validate-assets`, `balance-report` | [06](./06_dataasset_datatable_config_plan.md) |
| `gameplay tags` | `snapshot`, `validate` | [07](./07_gameplaytag_input_ability_plan.md) |
| `input` | `snapshot`, `validate` | [07](./07_gameplaytag_input_ability_plan.md) |
| `gas` | `generate-ability`, `generate-attributeset` | [07](./07_gameplaytag_input_ability_plan.md) |
| `ui` | `snapshot`, `validate-widget`, `validate-mvvm`, `validate-localization`, `validate-style` | [08](./08_ui_umg_plan.md) |
| `build` | `editor` | [05](./05_cpp_class_generation_plan.md), [09](./09_test_review_validation_plan.md) |
| `logs` | `analyze` | [09](./09_test_review_validation_plan.md) |
| `test` | `automation` | [09](./09_test_review_validation_plan.md) |
| `review` | `diff`, `summarize` | [09](./09_test_review_validation_plan.md) |
| `validate` | `all` | [09](./09_test_review_validation_plan.md) |
| `package` | `validate-plugins`, `config-diff`, `cook-smoke`, `analyze-log`, `dry-run` | [10](./10_packaging_cook_build_plan.md) |

### 5.3 `validate` 입력 규약

검증 명령은 다음 두 입력을 모두 허용한다.

- `--asset <path>` : 에디터에서 라이브로 열어 검증 (최신 상태)
- `--snapshot <path>` : 이미 export 된 스냅샷 JSON으로 검증 (재현/캐시)

둘 다 주어지면 `--snapshot`을 우선한다.

---

## 6. 표준 디렉터리 레이아웃

하네스는 UE 프로젝트 안에서 동작하는 것을 전제로 한다.

```text
<UEProjectRoot>/
├─ MyProject.uproject               # 프로젝트 파일 (이름은 플레이스홀더)
├─ Plugins/
│  └─ UEAutomationBridge/           # 하네스 Editor 플러그인
├─ Source/
│  └─ MyGame/                       # 게임 모듈 (이름은 플레이스홀더)
├─ Content/                         # 에셋 + spec
├─ Config/                          # ini
├─ Docs/                            # 정책/스펙 (asset_rules, ai, data, ui, ...)
└─ Saved/
   ├─ AutomationReports/            # snapshot / validation / report / result.json
   └─ Logs/                         # build / test / cook 로그
```

> 모든 산출물 경로는 `Saved/AutomationReports/` 와 `Saved/Logs/` 두 곳으로 통일한다.
> (`Saved/StateTreeBridge|Snapshots|Reports/` 같은 도메인별 분리 디렉터리는 쓰지 않는다.)

---

## 7. `result.json` 표준 스키마

모든 `ue-auto` 명령은 종료 시 `result.json`을 쓴다. 기본 위치는 `Saved/AutomationReports/result.json`이며 `--result`로 변경한다.

### 성공

```json
{
  "ok": true,
  "action": "add-state",
  "asset": "/Game/AI/StateTrees/ST_Test",
  "message": "State added successfully",
  "snapshot": "Saved/AutomationReports/ST_Test_002.json",
  "checks": [
    { "name": "asset_exists", "ok": true },
    { "name": "no_duplicate_states", "ok": true }
  ]
}
```

### 실패

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

규칙: 실패 시 `error.code`(머신 판독용)와 `error.message`(사람 판독용)를 함께 제공하고,
가능하면 다음 행동을 안내하는 `hint`를 포함한다.

---

## 8. 네이밍 규약

| 항목 | 표준값 | 비고 |
|---|---|---|
| 프로젝트 파일 | `MyProject.uproject` | 플레이스홀더. 실제 프로젝트명으로 치환 |
| 게임 모듈 | `MyGame` | `Source/MyGame/`, `/Script/MyGame.*` |
| 하네스 플러그인 | `UEAutomationBridge` | Editor 전용 |
| StateTree commandlet | `UEAuto.StateTreeCommandlet` | 도메인별 commandlet 동일 접두 `UEAuto.` |
| 리포트 디렉터리 | `Saved/AutomationReports/` | snapshot/validation/report/result.json |
| 로그 디렉터리 | `Saved/Logs/` | build/test/cook |

---

## 9. LLM 통합 전략

LLM(Agent)이 `ue-auto`를 호출하는 구체적인 방식과 단계적 로드맵은 별도 문서에서 정의한다.

→ **[11_llm_integration.md](./11_llm_integration.md)** — bash exec / MCP 서버 / CI/CD 비교 및 권장 순서

---

## 10. 추천 진행 순서 & MVP

상세 시간축은 [ROADMAP.md](./ROADMAP.md) 참조. 요약 순서:

1. 09 테스트/리뷰/검증 (하네스 중심축)
2. 01 에셋 네이밍/경로
3. 03 StateTree
4. 05 C++ 클래스 생성
5. 06 DataAsset/DataTable/Config
6. 07 GameplayTag/Input/Ability
7. 02 Animation
8. 08 UI/UMG
9. 04 Blueprint
10. 10 Packaging/Cook/Build

**1차 MVP 공통 골격**: `Snapshot → Validation → Markdown Report → result.json`.
이 골격이 도메인 하나(우선 09 또는 03)에서 돌아가면 나머지는 같은 패턴으로 확장한다.
