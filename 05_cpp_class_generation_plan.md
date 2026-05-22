# 05. C++ 클래스 생성 반복 자동화 작업 계획

## 목표

UE C++ 보일러플레이트, 매크로, Build.cs 의존성, UPROPERTY / UFUNCTION 정책을 자동화한다. Codex가 가장 잘할 수 있는 영역이다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| Actor 생성 | 템플릿 기반 | 1 |
| ActorComponent 생성 | 템플릿 기반 | 1 |
| DataAsset 클래스 생성 | 템플릿 기반 | 1 |
| Interface 생성 | UINTERFACE 패턴 생성 | 1 |
| Subsystem 생성 | GameInstance / World / LocalPlayer | 2 |
| Delegate 선언 | 스펙 기반 생성 | 2 |
| Build.cs 의존성 추가 | 분석 후 제안 / 수정 | 2 |
| UHT 에러 분석 | 로그 파싱 | 2 |

## 파일 구조

```text
/Source/MyGame
  MyGame.Build.cs
  /Characters
  /Components
  /Data
  /Interfaces
  /Subsystems

/Docs/cpp
  class_templates.yaml
  module_dependencies.yaml
```

## 작업 단계

### 1단계. 클래스 생성 스펙 정의

```yaml
class:
  name: HealthComponent
  type: ActorComponent
  module: MyGame
  path: Source/MyGame/Components
  blueprint_type: true
  tick: false
properties:
  - name: MaxHealth
    type: float
    default: 100.0
    metadata:
      EditAnywhere: true
      BlueprintReadOnly: true
      Category: Health
functions:
  - name: ApplyDamage
    return_type: void
    params:
      - name: DamageAmount
        type: float
    metadata:
      BlueprintCallable: true
      Category: Health
```

### 2단계. Header / CPP 생성

```bash
ue-auto cpp generate \
  --spec Docs/cpp/health_component.spec.yaml \
  --out Source/MyGame/Components
```

생성 결과:

```text
HealthComponent.h
HealthComponent.cpp
```

### 3단계. Build.cs 의존성 검사

```bash
ue-auto cpp validate-buildcs \
  --module MyGame \
  --out Saved/AutomationReports/cpp.buildcs.md
```

검증 항목:

- 필요한 Module 누락
- 사용하지 않는 Module 후보
- Public / Private dependency 구분
- Include Path 정책 위반

### 4단계. UPROPERTY / UFUNCTION 정책 검사

```bash
ue-auto cpp validate-reflection \
  --source Source/MyGame \
  --policy Docs/cpp/reflection.policy.yaml \
  --out Saved/AutomationReports/cpp.reflection.md
```

정책 예시:

```yaml
properties:
  forbid:
    - EditAnywhere + BlueprintReadWrite on runtime state
  prefer:
    - EditDefaultsOnly for config values
    - VisibleAnywhere for components
functions:
  require_category: true
```

### 5단계. 빌드 / UHT 로그 분석

```bash
ue-auto build editor \
  --project ./MyProject.uproject \
  --out-log Saved/Logs/build.log

ue-auto cpp analyze-uht \
  --log Saved/Logs/build.log \
  --out Saved/AutomationReports/uht.errors.md
```

## Codex 역할

- 스펙 기반 C++ 생성
- UHT 오류 원인 분석
- Include 정리 제안
- Build.cs 의존성 제안
- Reflection 메타데이터 정책 위반 수정안 제안

## 테스트 기준

- 생성 후 UHT 통과
- Editor Build 통과
- `BlueprintCallable` 함수는 Category 포함
- Component는 `CreateDefaultSubobject` 패턴 준수
- UObject 파생 클래스는 올바른 매크로 포함

## 리스크

| 리스크 | 대응 |
|---|---|
| UE 매크로 실수 | 템플릿 고정 |
| Build.cs 누락 | 자동 검사 |
| Include 순환 | IWYU 리포트 |
| Codex가 기존 코드 과수정 | 새 파일 생성부터 시작 |

## 1차 MVP

- Actor / ActorComponent / DataAsset / Interface 생성
- Build.cs 의존성 리포트
- UHT 로그 분석
- Reflection 정책 검사
