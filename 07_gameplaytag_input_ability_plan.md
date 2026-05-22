# 07. GameplayTag / Input / Ability 세팅 자동화 작업 계획

## 목표

GameplayTag, Enhanced Input, GAS Ability / AttributeSet / GameplayEffect 연결을 자동 검증하고 반복 코드를 생성한다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| GameplayTag 등록 검증 | 태그 목록 / 사용처 비교 | 1 |
| GameplayTag 오타 탐지 | 선언 / 참조 불일치 검사 | 1 |
| InputAction 목록 스냅샷 | 에셋 구조 Export | 2 |
| InputMappingContext 검증 | 키 바인딩 정책 검사 | 2 |
| Ability Class 생성 | 템플릿 기반 | 2 |
| AttributeSet 생성 | 템플릿 기반 | 2 |
| GameplayEffect / Cue 연결 | 참조 검증 | 3 |

## 추천 구조

```text
/Config
  DefaultGameplayTags.ini
  DefaultInput.ini

/Content/Input
  IA_Move
  IA_Attack
  IMC_Player

/Source/MyGame/Ability
  GA_Attack.h
  GA_Attack.cpp
  MyAttributeSet.h
  MyAttributeSet.cpp

/Docs/gameplay
  gameplay_tags.policy.yaml
  input.policy.yaml
  ability.spec.yaml
```

## 작업 단계

### 1단계. GameplayTag 스냅샷

```bash
ue-auto gameplay tags snapshot \
  --project ./MyProject.uproject \
  --out Saved/AutomationReports/gameplay_tags.snapshot.json
```

수집 항목:

- 등록된 GameplayTag
- Native GameplayTag
- Config GameplayTag
- 에셋에서 참조 중인 태그
- 코드에서 문자열로 참조하는 태그 후보

### 2단계. GameplayTag 검증

```bash
ue-auto gameplay tags validate \
  --policy Docs/gameplay/gameplay_tags.policy.yaml \
  --out Saved/AutomationReports/gameplay_tags.validation.md
```

정책 예시:

```yaml
required_roots:
  - Ability
  - State
  - Event
  - UI
  - Item
forbid:
  - Temp.*
  - Test.*
naming:
  separator: "."
  max_depth: 4
```

### 3단계. InputAction / Mapping 검증

```bash
ue-auto input snapshot \
  --path /Game/Input \
  --out Saved/AutomationReports/input.snapshot.json

ue-auto input validate \
  --snapshot Saved/AutomationReports/input.snapshot.json \
  --policy Docs/gameplay/input.policy.yaml \
  --out Saved/AutomationReports/input.validation.md
```

검증 항목:

- 필수 InputAction 존재
- IMC에 매핑 누락 없음
- 키 중복 바인딩 경고
- Gamepad / Keyboard 대응 여부
- Trigger / Modifier 설정 확인

### 4단계. Ability Class 생성

```yaml
ability:
  name: GA_Attack
  parent: UGameplayAbility
  instancing_policy: InstancedPerActor
  tags:
    ability: Ability.Combat.Attack
    activation_blocked:
      - State.Dead
      - State.Stunned
```

```bash
ue-auto gas generate-ability \
  --spec Docs/gameplay/ga_attack.spec.yaml \
  --out Source/MyGame/Ability
```

### 5단계. AttributeSet 생성

```yaml
attribute_set:
  name: CombatAttributeSet
  attributes:
    - Health
    - MaxHealth
    - AttackPower
    - Defense
```

```bash
ue-auto gas generate-attributeset \
  --spec Docs/gameplay/combat_attributes.spec.yaml \
  --out Source/MyGame/Ability
```

## Codex 역할

- GameplayTag 정책 작성
- GAS C++ 코드 생성
- AttributeSet 반복 코드 생성
- InputMapping 검증 리포트 요약
- Ability / Effect / Cue 누락 연결 제안

## 테스트 기준

- 등록되지 않은 GameplayTag 사용 시 실패
- 필수 InputAction 누락 시 실패
- Ability 코드 UHT 통과
- AttributeSet 생성 코드 빌드 통과
- 중복 키 바인딩은 경고 이상으로 표시

## 리스크

| 리스크 | 대응 |
|---|---|
| 태그 문자열 오탐 | Native Tag / Config Tag 구분 |
| 프로젝트마다 태그 정책 다름 | YAML 정책화 |
| GAS 코드 복잡도 증가 | 템플릿 최소화 후 확장 |
| Input 플랫폼 차이 | Keyboard / Gamepad / Touch 정책 분리 |

## 1차 MVP

- GameplayTag 목록 스냅샷
- 등록 / 참조 불일치 검사
- InputAction / IMC 리포트
- Ability / AttributeSet 템플릿 생성
