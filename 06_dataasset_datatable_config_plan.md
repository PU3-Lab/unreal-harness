# 06. DataAsset / DataTable / Config 관리 자동화 작업 계획

## 목표

게임 데이터의 누락 필드, 중복 ID, 값 범위, Enum / GameplayTag 불일치를 자동 검증한다.

## 공통 원칙

- **읽기 전용 분석 → 리포트 → 제한적 생성 → 사람 승인 → 적용** 순서로 진행한다.
- `.uasset`, `.umap` 직접 바이너리 수정은 1차 범위에서 제외한다.
- Codex는 판단 / 코드 생성 / 리포트 생성 / 수정안 제안 역할을 맡고, UE Editor Plugin 또는 Commandlet이 실제 UE 내부 접근을 담당한다.
- 모든 자동화는 작은 명령 단위로 쪼갠다.
- 각 명령은 입력 스펙, 출력 리포트, 실패 조건을 명확히 가진다.


## 자동화 대상

| 대상 | 방식 | 우선순위 |
|---|---|---:|
| DataTable Row 구조 검증 | Struct / CSV / JSON 비교 | 1 |
| 중복 ID 검사 | Primary Key 검사 | 1 |
| 필수 필드 누락 검사 | 스키마 기반 | 1 |
| 값 범위 검사 | min / max 정책 | 1 |
| Enum 매칭 검사 | 유효 Enum 값 확인 | 2 |
| GameplayTag 매칭 | 태그 존재 여부 검사 | 2 |
| DataAsset 생성 | 스펙 기반 생성 후보 | 3 |

## 추천 흐름

```text
Spec / CSV / JSON
  ↓
Schema Validation
  ↓
UE DataTable / DataAsset 검증
  ↓
Markdown 리포트
  ↓
Codex 수정안 제안
```

## 산출물

| 파일 | 설명 |
|---|---|
| `Docs/data/item.schema.yaml` | 아이템 데이터 스키마 |
| `Docs/data/skill.schema.yaml` | 스킬 데이터 스키마 |
| `DataSource/items.csv` | 원본 데이터 |
| `Saved/AutomationReports/data.validation.md` | 검증 리포트 |

## 작업 단계

### 1단계. 데이터 스키마 정의

```yaml
table: Items
key: ItemId
fields:
  - name: ItemId
    type: string
    required: true
    unique: true
  - name: DisplayName
    type: text
    required: true
  - name: ItemType
    type: enum
    enum: EItemType
    required: true
  - name: MaxStack
    type: int
    min: 1
    max: 999
  - name: Icon
    type: soft_object_path
    required: true
```

### 2단계. CSV / JSON 검증

```bash
ue-auto data validate-source \
  --schema Docs/data/item.schema.yaml \
  --input DataSource/items.csv \
  --out Saved/AutomationReports/data.source.validation.md
```

### 3단계. UE DataTable 검증

```bash
ue-auto data validate-datatable \
  --asset /Game/Data/DT_Items \
  --schema Docs/data/item.schema.yaml \
  --out Saved/AutomationReports/data.datatable.validation.md
```

### 4단계. DataAsset 참조 검증

```bash
ue-auto data validate-assets \
  --path /Game/Data/DataAssets \
  --schema Docs/data/item.schema.yaml \
  --out Saved/AutomationReports/data.asset.validation.md
```

검증 항목:

- SoftObjectPath가 실제 에셋을 가리키는가
- Icon / Mesh / Effect 참조가 누락되지 않았는가
- GameplayTag가 등록되어 있는가
- Enum 값이 실제 코드와 일치하는가

### 5단계. 밸런스 리포트 생성

```bash
ue-auto data balance-report \
  --input DataSource/items.csv \
  --group-by ItemType \
  --out Saved/AutomationReports/data.balance.md
```

## Codex 역할

- 스키마 작성
- 검증 리포트 요약
- 중복 ID 수정 후보 제안
- 값 범위 이상치 설명
- 데이터 테이블 변경 PR 설명 작성

## 테스트 기준

- 중복 ID가 있으면 실패
- 필수 필드가 비어 있으면 실패
- 범위 밖 값이 있으면 실패
- 참조 경로가 없으면 경고 또는 실패
- 스키마 변경 시 변경점 리포트 생성

## 리스크

| 리스크 | 대응 |
|---|---|
| 디자이너가 의도적으로 범위 밖 값 사용 | override / exception 지원 |
| CSV 인코딩 문제 | UTF-8 기준 + 인코딩 체크 |
| 로컬라이징 Text 처리 | key / source 분리 |
| Enum 변경으로 데이터 깨짐 | Enum 스냅샷 비교 |

## 1차 MVP

- CSV 스키마 검증
- 중복 ID 검사
- 필수 필드 검사
- 값 범위 검사
- DataTable Row 구조 검증
