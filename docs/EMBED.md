# 티스토리 embed / URL scope 사용법

GitHub Pages 기본 주소:

- 전체 검색: `/`
- 전체 embed: `/?embed=1`

## URL 파라미터

- `publisher`: 출판사 고정
- `subject`: 과목 고정
- `grade`: 학년 고정
- `book`: 교재 `book_id` 고정
- `embed=1`: 티스토리 iframe용 compact 화면

URL에서 이미 고정된 조건의 선택창은 자동으로 숨깁니다.

## 예시

### EBS 전체
```text
/?embed=1&publisher=EBS
```

### EBS 영어
```text
/?embed=1&publisher=EBS&subject=영어
```

### EBS 고3 영어
```text
/?embed=1&publisher=EBS&subject=영어&grade=고3
```

숫자만 필요한 기존 링크를 위해 `grade=3`도 허용합니다. 다만 학교급이 섞일 수 있는 범위에서는 `고3`, `중2`처럼 학교급을 포함하는 값을 권장합니다.

### 특정 교재
```text
/?embed=1&book=ebs-suneung-wanseong-english-2027
```

특정 교재 모드에서는 필터/검색 UI를 숨기고 해당 교재의 공식 자료 버튼을 중심으로 표시합니다.

## iframe 예시

```html
<iframe
  src="https://david12448.github.io/answer-link-index/?embed=1&book=ebs-suneung-wanseong-english-2027"
  loading="lazy"
  title="2027 수능완성 영어 공식 학습자료">
</iframe>
```

티스토리 본문에는 iframe만 두지 않고 교재명, 출판사, 대상 학년, 과목, 제공 자료 종류와 공식 자료 안내 문구를 함께 작성합니다.

## 화면 모드

- 기본: compact 1열 목록형
- 표지형: 사용자가 전체 사이트에서 선택 가능
- 상세형: 교재 선택 또는 `book` scope 사용 시 자동 적용
- embed: 큰 헤더와 고정된 선택창을 숨김

## 데이터 필드

- `cover_image_url`: 공식 출판사/CDN 표지 이미지. 실패하면 placeholder 표시
- `post_url`: 향후 관련 티스토리 글로 연결할 때 사용할 선택 필드
