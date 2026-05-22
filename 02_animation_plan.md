# 02. Animation 관련 세팅 자동화 작업 계획

## 목표

AnimInstance C++ 클래스 생성, BlendSpace 스펙 검증, Montage Slot / Notify 점검, AnimBP Parent Class 검증을 자동화한다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| AnimInstance C++ 생성 | 템플릿 기반 코드 생성 | 1 |
| BlendSpace 축 설정 검증 | 스펙과 실제 에셋 비교 | 1 |
| Montage Slot 검증 | Slot / Group 규칙 검사 | 2 |
| Notify 검증 | 필수 Notify 존재 여부 검사 | 2 |
| AnimBP Parent Class 검증 | 부모 클래스 정책 검사 | 2 |
| AnimGraph 노드 자동 연결 | 1차 제외 | - |

## 추천 구조

```text
/Source/MyGame/Animation
  MyCharacterAnimInstance.h
  MyCharacterAnimInstance.cpp

/Content/Characters/Hero/Animations
  ABP_Hero.uasset
  BS_Hero_Locomotion.uasset
  AM_Hero_Attack_01.uasset

/Docs/animation
  anim.instance.spec.yaml
  blendspace.spec.yaml
  montage.policy.yaml
```

## 작업 단계

### 1단계. AnimInstance 코드 템플릿 정의

예시 스펙:

```yaml
class_name: UHeroAnimInstance
parent: UAnimInstance
variables:
  - name: Speed
    type: float
    blueprint_read_only: true
  - name: Direction
    type: float
    blueprint_read_only: true
  - name: bIsInAir
    type: bool
    blueprint_read_only: true
functions:
  - name: NativeInitializeAnimation
  - name: NativeUpdateAnimation
```

생성 명령:

```bash
ue-auto anim generate-instance \
  --spec Docs/animation/anim.instance.spec.yaml \
  --module MyGame \
  --out Source/MyGame/Animation
```

### 2단계. BlendSpace 스펙 작성

```yaml
asset: /Game/Characters/Hero/Animations/BS_Hero_Locomotion
axis:
  x:
    name: Direction
    min: -180
    max: 180
    divisions: 8
  y:
    name: Speed
    min: 0
    max: 600
    divisions: 6
required_samples:
  - name: Idle
    x: 0
    y: 0
  - name: Run_F
    x: 0
    y: 600
```

검증 명령:

```bash
ue-auto anim validate-blendspace \
  --spec Docs/animation/blendspace.spec.yaml \
  --out Saved/AutomationReports/animation.blendspace.md
```

### 3단계. Montage Slot / Notify 검증

검증 항목:

- Montage Slot 이름이 정책과 일치하는가
- Group 이름이 프로젝트 규칙과 일치하는가
- 공격 Montage에 `AnimNotify_HitWindowStart`, `AnimNotify_HitWindowEnd`가 있는가
- 발소리 Notify가 Locomotion 애니메이션에 있는가

```bash
ue-auto anim validate-montage \
  --policy Docs/animation/montage.policy.yaml \
  --out Saved/AutomationReports/animation.montage.md
```

### 4단계. AnimBP Parent Class 검증

```bash
ue-auto anim validate-anim-bp \
  --path /Game/Characters/Hero/Animations \
  --required-parent /Script/MyGame.HeroAnimInstance \
  --out Saved/AutomationReports/animation.abp.md
```

### 5단계. 수동 리뷰 체크리스트 생성

AnimGraph는 자동 수정하지 않고 다음 체크리스트만 만든다.

- Locomotion State Machine 존재 여부
- Idle / Walk / Run 전이 조건 확인
- Jump Start / Loop / Land 상태 확인
- 캐릭터 이동 컴포넌트 변수와 AnimBP 변수 연결 확인
- Layered Blend per Bone 설정 확인

## Codex 역할

Codex는 다음을 담당한다.

- AnimInstance C++ 코드 생성
- 스펙 YAML 작성 / 수정
- 검증 리포트 요약
- 누락된 변수 / Notify / Slot 수정안 제안
- UE 로그 기반 UHT 빌드 오류 분석

## 테스트 기준

- 생성된 C++은 UHT 통과
- AnimBP Parent Class가 기대 클래스와 일치
- BlendSpace 축 범위가 정책과 일치
- Montage 필수 Notify 누락 시 실패 코드 반환

## 리스크

| 리스크 | 대응 |
|---|---|
| AnimGraph 자동 연결 실패 | 그래프 수정은 제외 |
| Notify 이름 프로젝트별 차이 | 정책 파일로 분리 |
| BlendSpace 샘플 자동 배치 오류 | 1차는 검증만 |
| C++ 생성 후 빌드 실패 | UHT 로그 분석 단계 추가 |

## 1차 MVP

- AnimInstance C++ 생성
- BlendSpace 축 검증
- Montage Slot / Notify 리포트
- AnimBP Parent Class 리포트
