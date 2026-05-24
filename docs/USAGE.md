# ue-auto CLI 사용법

UE5 자동화 파이프라인 CLI. 모든 명령어는 `result.json`을 출력하며,
CI/CD 스크립트에서 종료 코드(0 = 성공, 1 = 실패)로 판별할 수 있습니다.

## 설치

```bash
cd cli
pip install -e .
```

## 공통 옵션

모든 명령어에 사용할 수 있는 옵션입니다.

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--project PATH` | — | `.uproject` 파일 경로 |
| `--out PATH` | — | 주 출력 파일 경로 |
| `--out-md PATH` | — | Markdown 리포트 출력 경로 |
| `--result PATH` | 자동 (`<action>.result.json`) | `result.json` 출력 경로 (미지정 시 `Saved/AutomationReports/<action>.result.json`) |
| `--dry-run` | 활성화 | 실제 변경 없이 분석만 수행 |
| `--apply` | 비활성화 | 실제 변경 적용 |

## 환경 변수

| 변수 | 설명 |
|---|---|
| `UE_EDITOR_CMD` | `UnrealEditor-Cmd` 바이너리 경로 (설정 시 known path 탐색 생략) |
| `UE_BUILD_SCRIPT` | `Build.sh` / `Build.bat` 경로 (설정 시 자동 탐색 생략) |

---

## 명령어 목록

### `ue-auto review diff` — Git diff 위험도 분석

git diff를 분석해 변경된 파일의 위험도를 분류합니다. UE 실행 없이 순수 Python으로 동작합니다.

```bash
ue-auto review diff [--base REF] [--head REF] [--out-md PATH] [--result PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--base` | `main` | 비교 기준 브랜치/커밋 |
| `--head` | `HEAD` | 비교 대상 커밋 |

**위험도 분류:**
- `HIGH` — C++ 소스(`.cpp`, `.h`), 빌드 스크립트, 플러그인 설정
- `MEDIUM` — Blueprint(`.uasset`), 설정 파일(`.ini`, `.yaml`)
- `LOW` — 문서, 텍스트

**예시:**
```bash
ue-auto review diff --base origin/main --out-md reports/diff.md
```

---

### `ue-auto review summarize` — 리포트 집계

`reports/` 디렉터리 내 `result.json` 파일들을 읽어 전체 통과/실패 요약을 생성합니다.

```bash
ue-auto review summarize [--reports DIR] [--logs DIR] [--out-md PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--reports` | `Saved/AutomationReports` | result.json 파일들이 있는 디렉터리 |
| `--logs` | `Saved/Logs` | 로그 디렉터리 |

**예시:**
```bash
ue-auto review summarize --reports Saved/AutomationReports --out-md reports/summary.md
```

---

### `ue-auto build editor` — 에디터 빌드

UnrealBuildTool(UBT)을 사용해 에디터 타겟을 빌드합니다.

```bash
ue-auto build editor --project PATH [--config CONFIG] [--result PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--project` | 필수 | `.uproject` 파일 경로 |
| `--config` | `Development` | 빌드 구성 (`Development`, `Shipping`, `DebugGame` 등) |

**동작 방식:**
1. `UE_BUILD_SCRIPT` 환경 변수 → 직접 사용
2. `UE_EDITOR_CMD` 경로에서 `Engine/Build/BatchFiles/Build.{sh,bat}` 자동 탐색
3. Windows에서 `.bat` 파일은 자동으로 `cmd.exe /c`로 래핑

**예시:**
```bash
export UE_BUILD_SCRIPT=/Users/Shared/Epic\ Games/UE_5.5/Engine/Build/BatchFiles/Build.sh

ue-auto build editor --project MyGame/MyGame.uproject --config Development
```

---

### `ue-auto logs analyze` — 로그 분석

UE 로그 파일에서 에러, 경고, 크래시 패턴을 분류합니다. UE 실행 없이 순수 Python으로 동작합니다.

```bash
ue-auto logs analyze [--log FILE] [--out-md PATH] [--result PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--log` | `Saved/Logs/UnrealEditor.log` | 분석할 로그 파일 경로 |

**분류 카테고리:** `error`, `warning`, `crash`, `info`

**예시:**
```bash
ue-auto logs analyze --log Saved/Logs/UnrealEditor.log --out-md reports/logs.md
```

---

### `ue-auto test automation` — 자동화 테스트 실행

UE Automation 시스템을 통해 테스트를 실행합니다. `UnrealEditor-Cmd`가 필요합니다.

```bash
ue-auto test automation --project PATH [--filter FILTER] [--timeout SEC] [--result PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--project` | 필수 | `.uproject` 파일 경로 |
| `--filter` | — | 실행할 테스트 필터 (예: `MyGame.Unit`) |
| `--timeout` | `300` | 타임아웃 (초) |

**예시:**
```bash
export UE_EDITOR_CMD=/Users/Shared/Epic\ Games/UE_5.5/Engine/Binaries/Mac/UnrealEditor-Cmd

ue-auto test automation --project MyGame/MyGame.uproject --filter MyGame.Unit --timeout 600
```

---

### `ue-auto asset snapshot` — 에셋 스냅샷 캡처

UE AssetRegistry를 스캔해 모든 에셋 정보를 JSON으로 덤프합니다. `UnrealEditor-Cmd`와 `UEAutomationBridge` 플러그인이 필요합니다.

```bash
ue-auto asset snapshot --project PATH [--out PATH] [--result PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--project` | 필수 | `.uproject` 파일 경로 |
| `--out` | `Saved/AutomationReports/assets.snapshot.json` | 스냅샷 출력 경로 |

**출력 형식 (`assets.snapshot.json`):**
```json
[
  {
    "name": "BP_PlayerCharacter",
    "package_path": "/Game/Characters/BP_PlayerCharacter",
    "asset_class": "Blueprint",
    "is_redirector": false
  }
]
```

**예시:**
```bash
ue-auto asset snapshot \
  --project MyGame/MyGame.uproject \
  --out Saved/AutomationReports/assets.snapshot.json
```

---

### `ue-auto asset validate` — 에셋 네이밍/경로 검증

스냅샷 JSON과 정책 YAML을 비교해 PREFIX, PATH, REDIRECTOR 위반을 검출합니다. UE 실행 없이 순수 Python으로 동작합니다.

```bash
ue-auto asset validate --snapshot PATH [--policy PATH] [--out-md PATH] [--result PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--snapshot` | 필수 | `assets.snapshot.json` 경로 |
| `--policy` | — | 정책 YAML 경로 (미지정 시 검사 없이 통과) |

**위반 유형:**
| 유형 | 설명 |
|---|---|
| `PREFIX_VIOLATION` | 에셋 이름이 규정된 접두사로 시작하지 않음 |
| `PATH_VIOLATION` | 에셋이 허용된 경로에 없음 |
| `REDIRECTOR` | 리다이렉터 에셋 감지 (삭제 권장) |

**예시:**
```bash
ue-auto asset validate \
  --snapshot Saved/AutomationReports/assets.snapshot.json \
  --policy docs/asset_rules/assets.naming_policy.yaml \
  --out-md reports/asset_validation.md
```

---

### `ue-auto status` — 실행 결과 대시보드

`Saved/AutomationReports/` 내 모든 `*.result.json`을 읽어 pass/fail 테이블을 출력합니다. UE 실행 없이 순수 Python으로 동작합니다.

```bash
ue-auto status [--reports-dir PATH]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--reports-dir` | `Saved/AutomationReports` | result.json 파일들이 있는 디렉터리 |

**출력 예시:**
```
STATUS  ACTION    MESSAGE
---------------------------------------------
PASS    ping      pong  (2026-05-24 09:56:07)
PASS    snapshot  Asset snapshot written to ...  (2026-05-24 10:06:25)
FAIL    validate  59 violations found in 254 assets  [59 issues]  (2026-05-24 10:06:31)

총 3개  PASS 2  FAIL 1
```

**종료 코드:** FAIL이 하나라도 있으면 1, 모두 PASS면 0.

---

### `ue-auto validate all` — 전체 검증 (스텁)

모든 도메인 검증기를 순서대로 실행합니다. 현재 스텁 상태입니다.

```bash
ue-auto validate all --project PATH
```

---

### `ue-auto ai statetree` — StateTree AI 도메인

AI StateTree 관련 명령어 그룹입니다.

```bash
ue-auto ai statetree <action> --project PATH
```

---

## result.json 스키마

모든 명령어는 `--result` 경로에 결과를 기록합니다.

**성공:**
```json
{
  "ok": true,
  "action": "build",
  "message": "Build succeeded: MyGameEditor Win64 Development",
  "timestamp": "2026-05-24T13:00:00"
}
```

**실패:**
```json
{
  "ok": false,
  "action": "build",
  "error": {
    "code": "BUILD_FAILED",
    "message": "Build failed with exit code 1"
  },
  "hint": "Check the build log for compile/link errors.",
  "timestamp": "2026-05-24T13:00:00"
}
```

---

## 정책 YAML 형식

`ue-auto asset validate`에서 사용하는 정책 파일 형식입니다.

```yaml
rules:
  - class: Blueprint
    prefix: BP_
    allowed_paths:
      - /Game/Characters/**
      - /Game/Systems/**

  - class: StaticMesh
    prefix: SM_
    allowed_paths:
      - /Game/Environment/**
      - /Game/Props/**
```

`/**` 패턴은 해당 경로와 모든 하위 경로를 허용합니다.

샘플 정책: [`docs/asset_rules/assets.naming_policy.yaml`](asset_rules/assets.naming_policy.yaml)

---

## CI/CD 파이프라인 예시

```bash
#!/bin/bash
set -e

export UE_EDITOR_CMD=/opt/unreal/UE_5.5/Engine/Binaries/Linux/UnrealEditor-Cmd
PROJECT=MyGame/MyGame.uproject
REPORTS=Saved/AutomationReports

# 1. diff 위험도 확인
ue-auto review diff --base origin/main --result $REPORTS/diff.json

# 2. 에디터 빌드
ue-auto build editor --project $PROJECT --result $REPORTS/build.json

# 3. 자동화 테스트
ue-auto test automation --project $PROJECT --timeout 600 --result $REPORTS/test.json

# 4. 에셋 스냅샷 + 검증
ue-auto asset snapshot --project $PROJECT --out $REPORTS/assets.snapshot.json
ue-auto asset validate \
  --snapshot $REPORTS/assets.snapshot.json \
  --policy docs/asset_rules/assets.naming_policy.yaml

# 5. 전체 결과 대시보드 (FAIL 있으면 exit 1)
ue-auto status --reports-dir $REPORTS
```
