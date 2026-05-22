# ROADMAP — 스프린트 계획

이 문서는 [00_overview.md](./00_overview.md)의 추천 진행 순서를 **시간축 스프린트**로 분해한 것이다.
모든 스프린트는 공통 원칙(읽기전용 → 리포트 → 제한적 생성 → 사람 승인 → 적용)을 그대로 따른다.

> 범위 메모: 본 레포는 현재 **기획 문서만** 존재한다. 아래 스프린트는 구현 로드맵이며,
> 각 스프린트의 산출물은 코드가 아닌 "구현 대상 정의"다. 실제 코드 착수는 별도 결정으로 진행한다.

---

## 스프린트 한눈에 보기

| Sprint | 주제 | 도메인 | 의존성 | 핵심 산출물 |
|---:|---|---|---|---|
| 0 | Foundation | 공통 | — | ue-auto 골격, result.json/리포트 포맷, Plugin/commandlet skeleton(ping) |
| 1 | Test / Review 파이프라인 | 09 | S0 | review.summary, build 래퍼, 로그 분석, diff 위험도 |
| 2 | Asset 네이밍/경로 | 01 | S0 | AssetRegistry snapshot, naming/path 검증, redirector 리포트 |
| 3 | StateTree 읽기 중심 | 03 + Bridge | S0 | snapshot/report/validate → create/add-state |
| 4 | C++ 코드 생성 | 05 | S0 | Actor/Component/DataAsset/Interface 생성, Build.cs, UHT 분석 |
| 5 | Data 검증 | 06 | S0, S2 | schema/DataTable/DataAsset 검증 |
| 6 | GameplayTag/Input/Ability | 07 | S0, S4 | tag/input snapshot+validate, GAS/AttributeSet 생성 |
| 7 | Animation | 02 | S0, S4 | AnimInstance 생성, BlendSpace/Montage/AnimBP 검증 |
| 8 | UI / UMG | 08 | S0, S4 | Widget snapshot, Parent/MVVM/Localization/Style 검증, Widget C++ Base |
| 9 | Blueprint 검증 | 04 | S0, S2 | BP snapshot, Parent/Component/Compile/DataAsset 검증 |
| 10 | Packaging/Cook/Build | 10 | S1 | plugin/config diff, cook smoke, 로그 분석 |

---

## Sprint 0 — Foundation (선행 필수)

**목표**: 모든 도메인이 공유할 골격을 확정한다. (정의/계약 중심, 최소 동작)

- `ue-auto <도메인> <동작>` 디스패처 골격 + 공통 옵션(`--project/--out/--result/--dry-run/--apply`)
- `result.json` 표준 writer (성공/실패 스키마 — [00_overview §7](./00_overview.md))
- Markdown 리포트 공통 포맷 (상태 PASS/WARN/FAIL, 심각 항목 최상단)
- `UEAutomationBridge` Editor 플러그인 skeleton + commandlet `ping`
- 표준 디렉터리 생성 규약 (`Saved/AutomationReports/`, `Saved/Logs/`)

**완료 기준**
- `ue-auto ai statetree ...` 류 ping이 commandlet까지 도달하고 `result.json` 생성
- 실패 시 non-zero exit code
- 리포트/JSON 포맷이 이후 도메인에서 재사용 가능

---

## Sprint 1 — Test / Review 파이프라인 (09, 중심축)

**목표**: 하네스의 중추인 `Git Diff → Build → Validation → Test → Log → Review Report` 흐름.

- `ue-auto review diff` : 변경 파일 위험도 리포트 (`.uasset/.umap/Config` = 높음)
- `ue-auto build editor` : 에디터 빌드 래퍼 + 로그 저장
- `ue-auto logs analyze` : UHT/Compile/Link/Missing Module 분류
- `ue-auto validate all` : 도메인 검증 통합 호출 (초기엔 가용 도메인만)
- `ue-auto test automation` : Automation Test 실행
- `ue-auto review summarize` : `review.summary.md/json` 생성

**완료 기준**
- 같은 입력에 대해 요약 결과가 안정적
- 심각 오류 최상단, 수동 확인 항목 분리
- 전체 상태 PASS/WARN/FAIL 단일 판정

---

## Sprint 2 — Asset 네이밍/경로 (01)

**목표**: 읽기 전용 에셋 스냅샷 + 네이밍/경로 정책 검증.

- `ue-auto asset snapshot` : AssetRegistry 전수 스냅샷 (이름/경로/클래스/의존/참조/redirector)
- 네이밍/경로 정책 YAML (`Docs/asset_rules/*.yaml`)
- `ue-auto asset validate` : prefix/path 위반, redirector, 누락/미참조 후보 리포트

**완료 기준**
- snapshot은 프로젝트 무변경(읽기 전용)
- validate는 동일 입력 → 동일 결과
- 자동 수정 명령은 `--dry-run` 기본

---

## Sprint 3 — StateTree 읽기 중심 (03 + Bridge 상세)

**목표**: StateTree를 읽기/리포트/검증부터, 그 다음 빈 트리 생성·State 추가까지.
상세 Phase는 [ue5_statetree_automation_bridge_plan.md](./ue5_statetree_automation_bridge_plan.md).

- `ue-auto ai statetree snapshot` / `report` / `validate`
- 검증 최소 3종: Dead State / Missing Target / Missing Task Class
- `ue-auto ai statetree create` (빈 트리) → `add-state`
- mutation 후 자동 compile/save/snapshot/validate

**완료 기준**
- snapshot에 State 계층/Task/Transition 누락 없음
- 없는 Parent에 add-state → 실패, 중복 생성 방지
- create/add-state 후 에디터에서 확인 가능

---

## Sprint 4 — C++ 코드 생성 (05)

**목표**: UE C++ 보일러플레이트 생성과 Build.cs/UHT 검증. (Agent 강점 영역)

- `ue-auto cpp generate` (spec 기반) / `generate-class` (Actor/Component/DataAsset/Interface)
- `ue-auto cpp validate-buildcs` / `validate-reflection`
- `ue-auto cpp analyze-uht` (빌드 로그 파싱)

**완료 기준**
- 생성 코드 UHT/에디터 빌드 통과
- BlueprintCallable 함수는 Category 포함, Component는 CreateDefaultSubobject 패턴

---

## Sprint 5 — Data 검증 (06)

**목표**: 게임 데이터 스키마/무결성 검증.

- `ue-auto data validate-source` (CSV/JSON vs schema)
- `ue-auto data validate-datatable` / `validate-assets`
- `ue-auto data balance-report`

**완료 기준**
- 중복 ID/필수 누락/범위 밖 값 → 실패
- SoftObjectPath 미해결 → 경고 또는 실패

---

## Sprint 6 — GameplayTag / Input / Ability (07)

**목표**: 태그·입력 검증과 GAS 반복 코드 생성.

- `ue-auto gameplay tags snapshot` / `validate`
- `ue-auto input snapshot` / `validate`
- `ue-auto gas generate-ability` / `generate-attributeset`

**완료 기준**
- 미등록 태그 사용/필수 InputAction 누락 → 실패
- 생성된 Ability/AttributeSet 빌드 통과, 중복 키 바인딩 경고 이상

---

## Sprint 7 — Animation (02)

**목표**: AnimInstance 생성 + 애니메이션 에셋 검증.

- `ue-auto anim generate-instance`
- `ue-auto anim validate-blendspace` / `validate-montage` / `validate-anim-bp`
- AnimGraph는 자동 수정 제외 → 수동 체크리스트만

**완료 기준**
- 생성 C++ UHT 통과, AnimBP Parent 일치, BlendSpace 축 정책 일치
- 필수 Notify 누락 시 실패

---

## Sprint 8 — UI / UMG (08)

**목표**: Widget C++ Base 생성 + UMG 검증.

- `ue-auto ui snapshot`
- `ue-auto ui validate-widget` / `validate-mvvm` / `validate-localization` / `validate-style`
- Widget Graph 자동 수정 제외

**완료 기준**
- Parent 불일치/필수 Binding 누락/하드코딩 Text 탐지
- ViewModel 클래스 생성 후 빌드 통과

---

## Sprint 9 — Blueprint 검증 (04)

**목표**: BP 그래프는 건드리지 않고 메타데이터 기반 검증 + C++ Base 승격 제안.

- `ue-auto bp snapshot`
- `ue-auto bp validate` (Parent/Component/Interface/DataAsset/Compile/기본값)
- 반복 BP의 C++ Base Class 승격 제안 (`ue-auto cpp generate-class` 연계)

**완료 기준**
- snapshot 무변경, Compile Error BP 정확 표시
- 정책 위반은 파일 경로 + 사유 동반

---

## Sprint 10 — Packaging / Cook / Build (10)

**목표**: 배포 전 설정/플러그인/Cook 검증.

- `ue-auto package validate-plugins` / `config-diff`
- `ue-auto package cook-smoke` (Windows) / `analyze-log`
- `ue-auto package dry-run`

**완료 기준**
- Cook 실패 원인 최상단 표시, Shipping 금지 Plugin 탐지
- Config Diff가 파일/섹션/키 단위 출력

---

## 진행 규칙

- 한 스프린트의 MVP(`snapshot → validate → report → result.json`)가 끝나야 다음 확장으로 간다.
- mutation 계열은 항상 `--dry-run` 먼저, `--apply`는 사람 승인 후.
- 모든 스프린트 산출물은 [00_overview.md](./00_overview.md)의 CLI/경로/result.json 규약을 따른다.
