# 01. 에셋 생성 / 경로 / 네이밍 관리 자동화 작업 계획

## 목표

UE5 프로젝트의 에셋 폴더 구조, 네이밍 규칙, Redirector, 깨진 참조, 미사용 에셋 후보를 자동으로 검사하고 리뷰 가능한 리포트로 만든다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 자동화 방식 | 우선순위 |
|---|---|---:|
| 폴더 구조 생성 | 표준 폴더 스펙 기반 생성 | 1 |
| 에셋 네이밍 규칙 검사 | Prefix / Suffix / Path 룰 검증 | 1 |
| 에셋 경로 규칙 검사 | `/Game/...` 기준 Path Policy 검증 | 1 |
| Redirector 검사 | AssetRegistry / Editor Utility 기반 탐지 | 2 |
| 깨진 참조 검사 | Reference Viewer / AssetRegistry 기반 리포트 | 2 |
| 미사용 에셋 후보 | 참조 카운트 / 제외 규칙 기반 후보화 | 3 |

## 권장 폴더 구조

```text
/Content
  /Characters
    /Hero
      /Blueprints
      /Meshes
      /Animations
      /Materials
  /AI
    /BehaviorTrees
    /Blackboards
    /StateTrees
  /UI
    /Widgets
    /ViewModels
    /Styles
  /Data
    /DataAssets
    /DataTables
  /Maps
  /Systems
```

## 산출물

| 파일 | 설명 |
|---|---|
| `Docs/asset_rules/assets.path_policy.yaml` | 경로 규칙 |
| `Docs/asset_rules/assets.naming_policy.yaml` | Prefix / Suffix 규칙 |
| `Saved/AutomationReports/assets.snapshot.json` | AssetRegistry 스냅샷 |
| `Saved/AutomationReports/assets.validation.md` | 사람이 읽는 검증 리포트 |
| `Saved/AutomationReports/assets.validation.json` | Codex가 읽는 구조화 리포트 |

## 작업 단계

### 1단계. 읽기 전용 AssetRegistry 스냅샷

- UE Editor Plugin 또는 Commandlet에서 전체 에셋 목록을 수집한다.
- 수집 필드:
  - Asset Name
  - Package Path
  - Asset Class
  - Dependencies
  - Referencers
  - Redirector 여부
  - Modified Time 가능하면 포함

```bash
ue-auto asset snapshot \
  --project ./MyProject.uproject \
  --out Saved/AutomationReports/assets.snapshot.json
```

### 2단계. 네이밍 / 경로 정책 정의

예시:

```yaml
rules:
  - class: Blueprint
    prefix: BP_
    allowed_paths:
      - /Game/Characters/**
      - /Game/Systems/**
  - class: AnimationBlueprint
    prefix: ABP_
    allowed_paths:
      - /Game/Characters/**/Animations/**
  - class: BehaviorTree
    prefix: BT_
    allowed_paths:
      - /Game/AI/BehaviorTrees/**
  - class: BlackboardData
    prefix: BB_
    allowed_paths:
      - /Game/AI/Blackboards/**
```

### 3단계. 검증 리포트 생성

리포트 항목:

- 잘못된 Prefix
- 경로 위반
- Redirector 존재
- 누락 참조
- 참조 없는 에셋 후보
- 수동 확인 필요 항목

```bash
ue-auto asset validate \
  --snapshot Saved/AutomationReports/assets.snapshot.json \
  --naming Docs/asset_rules/assets.naming_policy.yaml \
  --paths Docs/asset_rules/assets.path_policy.yaml \
  --out-md Saved/AutomationReports/assets.validation.md
```

### 4단계. Codex 리뷰 연결

Codex에게 넘길 작업:

```text
Saved/AutomationReports/assets.validation.md를 읽고,
1. 위험도 높은 항목부터 정렬
2. 실제 수정 전 사람이 확인해야 할 항목 표시
3. 자동 수정 가능한 항목과 수동 수정 항목 분리
4. 다음 실행할 ue-auto 명령 제안
```

### 5단계. 제한적 자동 수정

초기에는 안전한 작업만 자동화한다.

| 작업 | 자동 적용 여부 |
|---|---|
| 빈 폴더 구조 생성 | 가능 |
| Redirector Fixup | 조건부 가능 |
| 에셋 Rename | 보류 |
| 에셋 Move | 보류 |
| 미사용 에셋 삭제 | 금지 |

## 테스트 기준

- 스냅샷 명령은 프로젝트를 변경하지 않아야 한다.
- 검증 명령은 동일 입력에 대해 동일 결과를 내야 한다.
- 자동 수정 명령은 반드시 `--dry-run`을 기본값으로 둔다.

## 리스크

| 리스크 | 대응 |
|---|---|
| 에셋 이동으로 참조 깨짐 | 1차 자동화에서 Move 제외 |
| 미사용 에셋 오탐 | 삭제 금지, 후보 리포트만 생성 |
| Prefix 정책 과도 적용 | 예외 목록 지원 |
| 플러그인별 에셋 경로 충돌 | `/Game`, `/Plugins` 정책 분리 |

## 1차 MVP

- AssetRegistry 스냅샷
- Prefix 검사
- Path 검사
- Redirector 목록 리포트
- Markdown 리포트 생성
