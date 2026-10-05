# Contributing

## 교재 추가 원칙

교재 1권을 `data/catalog.json`의 `books` 배열에 추가합니다.

### 필수 확인

- 교재명이 실제 공식 표기와 맞는가
- 학교급 / 학년 / 과목 / 학기 구분이 맞는가
- 같은 이름의 구판과 개정판이 섞이지 않았는가
- 가능하면 개정 교육과정, 발행연도, ISBN을 기록했는가
- 자료가 공식 출판사에서 제공되는가
- 로그인이 필요하면 `access: login_required`로 표시했는가
- `last_checked`에 실제 확인일을 기록했는가

## URL 우선순위

자료를 열 때는 다음 우선순위를 사용합니다.

1. `direct_url` — 공식 직접 파일/다운로드 URL
2. `resource_page` — 공식 정답/자료 페이지
3. `official_page` — 공식 교재 소개 페이지

직접 URL이 자주 바뀌는 출판사는 `resource_page`를 함께 반드시 기록합니다.

## ID 규칙

- `book_id`: 출판사-브랜드-학교급-과목-학년-학기-개정판을 알아볼 수 있는 영문 소문자 slug
- `resource_id`: `book_id` + 자료 종류
- URL이 바뀌어도 ID는 바꾸지 않습니다.

## 검증

```bash
pip install jsonschema
python scripts/validate_data.py
```
