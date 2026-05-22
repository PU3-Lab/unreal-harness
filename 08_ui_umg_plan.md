# 08. UI / UMG 반복 작업 자동화 계획

## 목표

UMG Widget 클래스 생성, ViewModel 연결 검증, 로컬라이징 키 누락 검사, 스타일 규칙 검사를 자동화한다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| Widget C++ Base 생성 | 템플릿 기반 | 1 |
| Widget Blueprint Parent 검증 | 정책 기반 | 1 |
| ViewModel 연결 검증 | MVVM Binding 확인 | 1 |
| 로컬라이징 키 검사 | Text / String 정책 검사 | 1 |
| 스타일 통일 검사 | Widget Style 정책 | 2 |
| 버튼 이벤트 바인딩 검사 | 함수 / Delegate 존재 확인 | 2 |
| Widget Graph 자동 연결 | 제외 | - |

## 추천 구조

```text
/Source/MyGame/UI
  BaseUserWidget.h
  InventoryWidget.h
  InventoryViewModel.h

/Content/UI
  /Widgets
  /ViewModels
  /Styles

/Docs/ui
  widget.policy.yaml
  localization.policy.yaml
  style.policy.yaml
```

## 작업 단계

### 1단계. Widget 스냅샷

```bash
ue-auto ui snapshot \
  --path /Game/UI \
  --out Saved/AutomationReports/ui.snapshot.json
```

수집 항목:

- Widget Blueprint 경로
- Parent Class
- Named Widget 목록
- Binding 정보
- ViewModel 연결 정보
- Text 사용 목록
- Button / Delegate 연결 후보

### 2단계. Widget Parent Class 검증

```yaml
rules:
  - path: /Game/UI/Widgets/Inventory/**
    required_parent: /Script/MyGame.InventoryWidget
  - path: /Game/UI/Widgets/Common/**
    required_parent: /Script/MyGame.BaseUserWidget
```

```bash
ue-auto ui validate-widget \
  --snapshot Saved/AutomationReports/ui.snapshot.json \
  --policy Docs/ui/widget.policy.yaml \
  --out Saved/AutomationReports/ui.widget.validation.md
```

### 3단계. ViewModel / Binding 검증

```yaml
viewmodels:
  - widget: /Game/UI/Widgets/WBP_Inventory
    required_viewmodel: InventoryViewModel
    required_bindings:
      - Items
      - SelectedItem
      - Gold
```

```bash
ue-auto ui validate-mvvm \
  --policy Docs/ui/mvvm.policy.yaml \
  --out Saved/AutomationReports/ui.mvvm.validation.md
```

### 4단계. 로컬라이징 키 검사

검증 항목:

- 하드코딩 Text
- 비어 있는 Namespace / Key
- 중복 Key
- 개발용 임시 문자열
- 한국어 / 영어 소스 누락

```bash
ue-auto ui validate-localization \
  --path /Game/UI \
  --policy Docs/ui/localization.policy.yaml \
  --out Saved/AutomationReports/ui.localization.md
```

### 5단계. 스타일 규칙 검사

```yaml
styles:
  buttons:
    required_style_asset: /Game/UI/Styles/DA_ButtonStyle
  fonts:
    default: /Game/UI/Fonts/F_Main
  colors:
    use_design_tokens: true
```

```bash
ue-auto ui validate-style \
  --policy Docs/ui/style.policy.yaml \
  --out Saved/AutomationReports/ui.style.md
```

## Codex 역할

- Widget C++ Base 클래스 생성
- ViewModel C++ 생성
- 로컬라이징 누락 목록 정리
- 스타일 위반 리포트 요약
- Widget별 수동 연결 체크리스트 생성

## 자동 수정 허용 범위

| 작업 | 허용 |
|---|---|
| Widget C++ 클래스 생성 | 가능 |
| ViewModel 클래스 생성 | 가능 |
| 로컬라이징 키 리포트 | 가능 |
| Widget Graph 수정 | 금지 |
| 버튼 이벤트 자동 연결 | 보류 |
| Style 자동 적용 | 보류 |

## 테스트 기준

- Widget Parent Class 불일치 탐지
- 필수 Binding 누락 탐지
- 하드코딩 Text 탐지
- ViewModel 클래스 생성 후 빌드 통과
- 스타일 정책 위반을 Widget 경로와 함께 표시

## 리스크

| 리스크 | 대응 |
|---|---|
| UMG 내부 구조 접근 제한 | 가능한 메타데이터부터 |
| 디자이너 의도 스타일 오탐 | 예외 목록 지원 |
| MVVM 미사용 프로젝트 | ViewModel 검증 optional 처리 |
| 로컬라이징 정책 과함 | 단계적 적용 |

## 1차 MVP

- Widget Snapshot
- Parent Class 검증
- 로컬라이징 키 검사
- ViewModel 연결 리포트
- Widget C++ Base 생성
