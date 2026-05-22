# UE5 자동화 후보별 상세 작업 계획 Index

원본 후보 정리 파일을 기준으로 후보별 상세 작업 계획을 분리했다.

## 파일 목록

- [01. 에셋 생성 / 경로 / 네이밍 관리 자동화 작업 계획](./01_asset_path_naming_plan.md)
- [02. Animation 관련 세팅 자동화 작업 계획](./02_animation_plan.md)
- [03. StateTree 자동화 작업 계획](./03_statetree_plan.md)
- [04. Blueprint 반복 작업 자동화 계획](./04_blueprint_plan.md)
- [05. C++ 클래스 생성 반복 자동화 작업 계획](./05_cpp_class_generation_plan.md)
- [06. DataAsset / DataTable / Config 관리 자동화 작업 계획](./06_dataasset_datatable_config_plan.md)
- [07. GameplayTag / Input / Ability 세팅 자동화 작업 계획](./07_gameplaytag_input_ability_plan.md)
- [08. UI / UMG 반복 작업 자동화 계획](./08_ui_umg_plan.md)
- [09. 테스트 / 리뷰 / 검증 자동화 작업 계획](./09_test_review_validation_plan.md)
- [10. Packaging / Cook / Build 설정 자동화 작업 계획](./10_packaging_cook_build_plan.md)

## 추천 진행 순서

1. `09. 테스트 / 리뷰 / 검증`
2. `01. 에셋 생성 / 경로 / 네이밍 관리`
3. `03. StateTree`
4. `05. C++ 클래스 생성 반복`
5. `06. DataAsset / DataTable / Config`
6. `07. GameplayTag / Input / Ability`
7. `02. Animation`
8. `08. UI / UMG`
9. `04. Blueprint`
10. `10. Packaging / Cook / Build`

## 초기 MVP 기준

처음부터 에셋을 직접 수정하지 말고, 다음 3가지만 먼저 만든다.

```text
Snapshot
  ↓
Validation
  ↓
Markdown Report
```

그 다음에 Codex가 리포트를 읽고 다음 명령을 제안하는 루프로 확장한다.
