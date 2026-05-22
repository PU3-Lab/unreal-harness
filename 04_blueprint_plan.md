# 04. Blueprint 반복 작업 자동화 계획

## 목표

Blueprint 그래프 직접 수정은 피하고, C++ Base Class / DataAsset / Config / 기본값 검증 중심으로 반복 작업을 줄인다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| Blueprint Parent Class 검증 | 정책 기반 검사 | 1 |
| Component 구성 검사 | 필수 컴포넌트 존재 확인 | 1 |
| 기본값 세팅 검증 | CDO / Asset Data 읽기 | 1 |
| Interface 구현 확인 | Required Interface 검사 | 2 |
| DataAsset 연결 확인 | 참조 누락 검사 | 2 |
| 변수 / 함수 생성 | 제한적 생성 후보 | 3 |
| 노드 그래프 연결 | 제외 | - |

## 권장 방향

Blueprint는 시각적 튜닝과 디자이너 판단이 들어가므로 자동 수정보다 **검증 리포트**가 더 안전하다.

## 산출물

| 파일 | 설명 |
|---|---|
| `Docs/blueprint/blueprint.policy.yaml` | BP 규칙 |
| `Saved/AutomationReports/blueprint.snapshot.json` | BP 구조 스냅샷 |
| `Saved/AutomationReports/blueprint.validation.md` | 검증 리포트 |

## 작업 단계

### 1단계. Blueprint 목록 수집

```bash
ue-auto bp snapshot \
  --path /Game \
  --out Saved/AutomationReports/blueprint.snapshot.json
```

수집 필드:

- Asset Path
- Blueprint Class
- Parent Class
- Implemented Interfaces
- Components
- Exposed Variables
- Default Values
- Compile Status

### 2단계. 정책 파일 작성

```yaml
rules:
  - path: /Game/Characters/**
    required_parent: /Script/MyGame.BaseCharacter
    required_components:
      - CharacterMovement
      - CapsuleComponent
      - SkeletalMeshComponent
    required_interfaces:
      - /Script/MyGame.InteractableInterface

  - path: /Game/Items/**
    required_parent: /Script/MyGame.BaseItemActor
    required_data_asset_field: ItemData
```

### 3단계. 검증

```bash
ue-auto bp validate \
  --snapshot Saved/AutomationReports/blueprint.snapshot.json \
  --policy Docs/blueprint/blueprint.policy.yaml \
  --out-md Saved/AutomationReports/blueprint.validation.md
```

검증 항목:

- Parent Class 불일치
- 필수 Component 누락
- Interface 누락
- DataAsset 참조 누락
- Compile Error
- 기본값 미설정
- Deprecated Class 상속 여부

### 4단계. C++ Base Class 생성

Blueprint 반복이 많아지면 Base Class로 빼는 것이 좋다.

```bash
ue-auto cpp generate-class \
  --type Actor \
  --name BaseInteractableActor \
  --module MyGame
```

### 5단계. Codex 리뷰

Codex에게 맡길 작업:

- BP 검증 리포트 요약
- 반복 변수 / 함수의 C++ Base Class 승격 제안
- 누락된 DataAsset 참조 목록화
- Blueprint별 수동 작업 체크리스트 생성

## 자동 수정 허용 범위

| 작업 | 허용 |
|---|---|
| 리포트 생성 | 가능 |
| C++ Base Class 생성 | 가능 |
| DataAsset 스펙 생성 | 가능 |
| BP 그래프 노드 연결 | 금지 |
| BP 내부 변수 자동 추가 | 보류 |
| BP 자동 저장 | 보류 |

## 테스트 기준

- BP 스냅샷 명령은 에셋을 변경하지 않아야 한다.
- Compile Error가 있는 BP를 정확히 표시해야 한다.
- 정책 위반 항목은 파일 경로와 이유를 함께 출력해야 한다.

## 리스크

| 리스크 | 대응 |
|---|---|
| Blueprint 내부 구조 접근 제한 | 가능한 메타데이터부터 시작 |
| 자동 저장으로 에셋 변경 | 1차에서는 저장 금지 |
| 그래프 자동 연결 실패 | 명시적으로 제외 |
| 정책이 너무 빡빡함 | 예외 규칙 지원 |

## 1차 MVP

- Blueprint Snapshot
- Parent Class 검증
- Required Component 검증
- Compile Status 리포트
- DataAsset 참조 누락 리포트
