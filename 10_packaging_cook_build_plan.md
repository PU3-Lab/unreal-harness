# 10. Packaging / Cook / Build 설정 자동화 작업 계획

## 목표

Cook / Packaging / 플랫폼별 Build 설정 / Plugin 의존성 / Config 차이를 자동 검증하고 로그 분석 리포트를 만든다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| Cook Smoke Test | 짧은 Cook 실행 | 1 |
| Packaging Log Analyzer | 로그 패턴 분석 | 1 |
| Platform Config Diff | Windows / Mac / Linux 설정 비교 | 1 |
| Plugin Dependency Checker | `.uplugin`, `.uproject` 분석 | 2 |
| Asset 참조 누락 | Cook 로그 기반 탐지 | 2 |
| Development / Shipping 차이 | Config 비교 | 2 |

## 추천 구조

```text
/Config
  DefaultEngine.ini
  DefaultGame.ini
  DefaultInput.ini
  Windows/WindowsEngine.ini
  Mac/MacEngine.ini

/Docs/build
  platform.policy.yaml
  plugin.policy.yaml
  packaging.policy.yaml
```

## 작업 단계

### 1단계. 플랫폼 정책 정의

```yaml
platforms:
  - Windows
  - Mac
  - Linux

config_rules:
  Shipping:
    forbid_console_commands: true
    require_use_pak_file: true
    require_full_rebuild: false

plugins:
  required:
    - EnhancedInput
    - GameplayAbilities
  forbidden_in_shipping:
    - EditorScriptingUtilities
```

### 2단계. Plugin 의존성 검사

```bash
ue-auto package validate-plugins \
  --project ./MyProject.uproject \
  --policy Docs/build/plugin.policy.yaml \
  --out Saved/AutomationReports/package.plugins.md
```

검증 항목:

- 필수 Plugin 누락
- Shipping에 포함되면 안 되는 Plugin
- Editor 전용 Plugin 런타임 포함 여부
- `.uplugin` Module Type 문제

### 3단계. Config Diff

```bash
ue-auto package config-diff \
  --config Config \
  --policy Docs/build/platform.policy.yaml \
  --out Saved/AutomationReports/package.config_diff.md
```

검증 항목:

- Development / Shipping 차이
- 플랫폼별 누락 설정
- Input / GameplayTag / Collision 설정 차이
- Map / GameMode 설정 누락

### 4단계. Cook Smoke Test

```bash
ue-auto package cook-smoke \
  --project ./MyProject.uproject \
  --platform Windows \
  --map /Game/Maps/TestMap \
  --out-log Saved/Logs/cook_smoke.log
```

### 5단계. Cook / Packaging 로그 분석

```bash
ue-auto package analyze-log \
  --log Saved/Logs/cook_smoke.log \
  --out Saved/AutomationReports/package.cook_log.md
```

분석 항목:

- Missing Asset
- Unable to load package
- SoftObjectPath resolve 실패
- Plugin missing
- Shader compile error
- Blueprint compile warning
- Map Check Error

### 6단계. Packaging Dry Run

```bash
ue-auto package dry-run \
  --project ./MyProject.uproject \
  --platform Windows \
  --configuration Development \
  --out Saved/AutomationReports/package.dry_run.md
```

## Codex 역할

- Packaging 실패 로그 요약
- Plugin / Config 수정안 제안
- 누락 Asset 경로 기반 원인 추정
- 플랫폼별 빌드 정책 작성
- Shipping 전 체크리스트 생성

## 테스트 기준

- Cook 실패 시 실패 원인을 리포트 최상단에 표시
- Plugin 정책 위반 탐지
- Config Diff가 파일 / 섹션 / 키 단위로 출력
- Missing Asset은 참조한 에셋과 참조된 에셋을 함께 표시
- Shipping 금지 Plugin이 있으면 실패

## 리스크

| 리스크 | 대응 |
|---|---|
| Cook 시간이 오래 걸림 | Smoke / Full Cook 분리 |
| 플랫폼 SDK 설치 차이 | 환경 체크 명령 추가 |
| 로그 패턴 다양함 | 패턴 룰 누적 |
| Plugin 의존성 복잡함 | 필수 / 금지 / 선택 그룹화 |

## 1차 MVP

- Plugin 의존성 리포트
- Config Diff
- Windows Cook Smoke Test
- Cook 로그 분석
- Packaging 체크리스트
