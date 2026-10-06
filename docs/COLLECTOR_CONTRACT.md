# 출판사 Collector 공통 계약

출판사마다 교재를 찾는 방식은 다르지만, 사용자에게는 같은 검색 경험을 제공하기 위한 공통 계약입니다.

## 1. 수집기는 출판사 고유 구조를 흡수한다

각 collector는 출판사 사이트의 실제 구조를 그대로 이해합니다.

예:
- EBS: `bookId=LB...` 중심
- 다른 출판사: ISBN, 상품번호, 시리즈 ID, 자료실 게시물 번호 등

이 차이를 프런트엔드에 전달하지 않습니다. 최종 결과만 공통 catalog 형식으로 정규화합니다.

## 2. 최소 교재 필드

각 교재는 가능한 한 다음 값을 제공합니다.

- `book_id`: 우리 시스템의 안정적인 교재 ID
- `publisher`
- `publisher_book_id`: 출판사 내부 고유 ID가 있을 때
- `brand`: 시리즈/브랜드
- `title`
- `aliases`
- `school_level`
- `grade`
- `subject`
- `edition_year`
- `official_page`
- `cover_image_url`
- `materials[]`
- `courses[]`
- `post_url`: 티스토리 관련 글 연결용 선택 필드

## 3. 사용자 UI 계약

출판사마다 사이트 메뉴가 달라도 기본 사용자 탐색은 다음 순서를 유지합니다.

**출판사 → 과목 → 학년 → 교재**

추가로 교재명 검색을 항상 제공하며, 브랜드/시리즈명도 검색어로 잡힙니다.

## 4. 티스토리 개별 포스팅 계약

한 교재는 반드시 아래처럼 독립적으로 표시할 수 있어야 합니다.

```text
/?book={book_id}&embed=1
```

개별 포스팅에서는 선택창을 최소화하고 해당 교재의 자료 버튼을 우선 표시합니다.

## 5. 자료 URL 우선순위

1. 공개 검증된 `direct_url`
2. 교재별 `resource_page`
3. `official_page`

로그인/세션/만료 토큰 의존 URL은 공개 direct URL로 저장하지 않습니다.

## 6. 자동화 원칙

- 신규 교재 발견: 후보 생성
- URL 변경 발견: 후보 생성
- 자동으로 catalog를 덮어쓰지 않음
- 검증 후 PR로 반영
- 실패/예외는 `docs/LESSONS.md`에 기록
