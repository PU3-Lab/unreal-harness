# UE5 자동화 후보별 상세 작업 계획 Index

원본 후보 정리 파일을 기준으로 후보별 상세 작업 계획을 분리했다.

> **시작은 [00. 전체 개요 / 아키텍처 / CLI 규약](./docs/plans/00_overview.md)부터.**
> 공통 원칙·`ue-auto` CLI 규약·`result.json` 표준·디렉터리/네이밍 규약은 `00_overview.md`가 단일 출처다.
> 시간축 스프린트 계획은 [ROADMAP.md](./ROADMAP.md) 참조.

## 파일 목록

- [00. 전체 개요 / 아키텍처 / CLI 규약](./docs/plans/00_overview.md) — 단일 출처
- [01. 에셋 생성 / 경로 / 네이밍 관리 자동화 작업 계획](./docs/plans/01_asset_path_naming_plan.md)
- [02. Animation 관련 세팅 자동화 작업 계획](./docs/plans/02_animation_plan.md)
- [03. StateTree 자동화 작업 계획](./docs/plans/03_statetree_plan.md)
- [04. Blueprint 반복 작업 자동화 계획](./docs/plans/04_blueprint_plan.md)
- [05. C++ 클래스 생성 반복 자동화 작업 계획](./docs/plans/05_cpp_class_generation_plan.md)
- [06. DataAsset / DataTable / Config 관리 자동화 작업 계획](./docs/plans/06_dataasset_datatable_config_plan.md)
- [07. GameplayTag / Input / Ability 세팅 자동화 작업 계획](./docs/plans/07_gameplaytag_input_ability_plan.md)
- [08. UI / UMG 반복 작업 자동화 계획](./docs/plans/08_ui_umg_plan.md)
- [09. 테스트 / 리뷰 / 검증 자동화 작업 계획](./docs/plans/09_test_review_validation_plan.md)
- [10. Packaging / Cook / Build 설정 자동화 작업 계획](./docs/plans/10_packaging_cook_build_plan.md)

## 추천 진행 순서 / 스프린트

추천 진행 순서와 스프린트별 목표·산출물·완료기준은 [ROADMAP.md](./ROADMAP.md)에 정리되어 있다.
(요약 순서: 09 → 01 → 03 → 05 → 06 → 07 → 02 → 08 → 04 → 10)

## 초기 MVP 기준

처음부터 에셋을 직접 수정하지 말고, 도메인마다 다음 공통 골격을 먼저 만든다.

```text
Snapshot
  ↓
Validation
  ↓
Markdown Report
  ↓
result.json
```

그 다음에 Agent가 리포트를 읽고 다음 명령을 제안하는 루프로 확장한다.
자세한 골격 정의는 [00_overview.md](./docs/plans/00_overview.md) §9 참조.
