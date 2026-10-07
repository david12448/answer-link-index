# EBS 수집 설계

## 목표
한 교재 레코드 안에 EBS가 제공하는 정답/해설, 정오표, 영어 MP3, 부가자료, 관련 인강을 함께 묶는다.

예시:
- EBS 2027학년도 수능완성 영어영역 영어
- EBS 교재 ID: LB00000005984

## 확인된 공식 진입점

- 정답지: https://www.ebsi.co.kr/ebs/pot/potg/bkAnsList.ebs
- 정오표: https://www.ebsi.co.kr/ebs/pot/potg/bkErrChrgMngList.ebs
- 영어 MP3: https://www.ebsi.co.kr/ebs/pot/potg/retrieveMp3DownList.ebs
- 부가자료실: https://www.ebsi.co.kr/ebs/pot/potg/txbkAdtlDatList.ebs
- 교재 상세: https://www.ebsi.co.kr/ebs/pot/potg/retrieveCourseDetailNw.ebs?bookId={BOOK_ID}

## 통합 키

EBS 교재 상세 URL에는 LB로 시작하는 bookId가 있으므로 이를 publisher_book_id로 저장한다.
가능하면 네 자료실의 항목도 같은 bookId로 연결한다.
자료실에서 bookId가 노출되지 않는 경우에만 정규화한 교재명 + 발행연도 + 영역을 보조 매칭키로 사용한다.

## 자료 타입

- answer: 정답 및 해설
- errata: 정오표
- mp3: 영어 MP3
- additional: 부가자료

자료가 여러 개라면 같은 type을 여러 건 허용한다. 예를 들어 MP3가 회차별/단원별로 나뉘면 각각 resource_id를 부여한다.

## 관련 인강

교재 상세 페이지의 관련강좌 및 EBS 강좌 검색을 통해 course_id/source_course_id/title/teacher/course_url을 수집한다.
한 교재에 여러 교사의 강좌가 연결될 수 있으므로 courses는 배열로 유지한다.

## UI 원칙

1. 카드 상단에 자료 버튼을 먼저 노출한다.
2. direct_url이 있으면 해당 공식 다운로드 주소를 우선 사용한다.
3. direct_url이 아직 없으면 공식 자료실/상세 페이지로 연결한다.
4. 관련 인강은 같은 카드 안에 보조 버튼으로 표시한다.
5. 목록의 교재명·표지·자료 뱃지는 내부 교재 상세 페이지로 이동하고, 공식 교재 페이지는 상세 화면의 보조 링크로 제공한다.

## 다음 조사 항목

- 각 자료실의 목록 요청 방식과 페이지네이션 파라미터
- 항목 상세에서 실제 다운로드 URL을 생성하는 방식
- direct URL이 쿠키 없이도 열리는지 여부
- 정답/정오표/MP3/부가자료 항목에서 bookId를 직접 얻을 수 있는지
- 관련강좌의 정확한 강좌 상세 URL 형식

## 인증

EBS 공개 자료 수집에는 계정 정보를 사용하지 않는다.
향후 로그인 전용 출판사는 별도의 private collector와 GitHub Actions Secrets를 사용한다.


## 2026-10-06 공개 페이지 2차 확인

현재 공개 웹에서 다시 확인한 결과:

- 정답지 목록은 `bkAnsList.ebs`이며 `catGbn`, `devonTargetRow` 같은 쿼리 값이 사용되는 사례가 확인됨.
- 정답지 상세는 `detailBkAnsInfo.ebs?bookId=LB...` 형태가 검색 결과에 반복적으로 노출됨.
- 정오표는 `bkErrChrgMngList.ebs` 목록과 `DetailBkErrInfo.ebs` 상세 경로가 존재함.
- 영어 MP3와 부가자료실은 공개 진입점은 확인됐지만, 최신 상세/다운로드 파라미터는 아직 확정하지 않음.
- 과거 MP3 주소에서 여러 쿼리 파라미터가 사용된 사례가 있으나, 과거 값을 현재 수집기에 그대로 고정하지 않는다.

### 다음 단계: 먼저 probe, 그 다음 collector

EBS 페이지는 목록 HTML에 교재가 직접 들어오지 않고 폼/스크립트 요청으로 채워질 가능성이 있다.
따라서 첫 단계에서는 `scripts/collectors/ebs_probe.py`로 각 공개 페이지의:

- HTTP 상태와 최종 URL
- 폼 action
- input/select name
- HTML에 노출되는 `LB...` bookId
- 상세 링크 흔적

을 읽기 전용으로 수집한다.

GitHub Actions의 `Probe EBS public pages` workflow를 수동 실행하여 실제 서버 응답을 JSON artifact로 남긴 뒤,
그 결과에서 목록 요청/페이지네이션/상세 다운로드 규칙을 확정하고 본 collector를 구현한다.

이 probe는 로그인, 쿠키 우회, 파일 재호스팅을 하지 않는다.

## 2026-10-06 기본 교재 seed 확장

EBS 공식 교재 상세 페이지에서 `bookId`와 자료 제공 여부를 직접 확인한 교재를 우선 catalog에 추가한다.

현재 추가한 2027 수능특강 예시:

- 국어 독서 — `LB00000005909`
- 국어 문학 — `LB00000005908`
- 국어 언어와 매체 — `LB00000005911`
- 수학 확률과통계 — `LB00000005914`
- 영어 영어 — `LB00000005917`
- 영어 영어듣기 — `LB00000005918`
- 영어 영어독해연습 — `LB00000005919`

영어 3종은 공식 교재 페이지에서 MP3 + 교재 정답지 + 교재 정오표 제공이 함께 표시된다.
국어/수학 seed는 교재 정답지 + 교재 정오표가 표시된다.

collector가 실제 개별 자료 URL을 확정하기 전까지는 교재별 공식 상세 페이지를 안전한 fallback으로 사용한다.
즉, UI는 먼저 여러 EBS 교재를 실제로 탐색할 수 있게 하고, 이후 collector가 검증된 direct/resource URL을 같은 book_id에 채워 넣는다.

## 사용자 탐색 원칙

EBS 자체 사이트는 시리즈/영역/학년/교재 검색이 혼합되어 있지만 우리 UI는 EBS 방식에 사용자를 맞추지 않는다.

사용자 기준 공통 순서:

**출판사 → 과목 → 학년 → 교재**

- EBS의 `bookId`, 시리즈 ID, 자료실 파라미터는 내부 collector가 처리한다.
- 수능특강/수능완성 같은 시리즈명은 `brand`와 검색 alias로 유지한다.
- 티스토리에서는 각 교재를 `?book={book_id}&embed=1`로 한 권씩 직접 노출하는 것을 기본 배포 방식 중 하나로 유지한다.
## 2026-10-07 정답지 상세 fallback 및 정오표 수집 방향

### 정답지
- 언어와 매체 `LB00000005911`의 확인된 정답지 상세 주소는 `detailBkAnsInfo.ebs`에 `bookId=LB00000005911`, `no=5`가 들어간다.
- 이 상세 주소는 PDF 자체가 아니므로 `resource_page`로 사용한다.
- EBS 다운로드 스크립트는 `bookFlId`를 받아 `bkAnsMngFLdown.ajax`를 호출하고 응답의 `flNm`을 실제 파일 URL로 사용한다.
- collector가 `bookFlId → flNm`을 안정적으로 해석하고 공개/비만료 URL임을 확인하면 그때 `direct_url`로 승격한다.

### 정오표
- 공식 정오표 검색 페이지는 `bkErrChrgMngList.ebs`이다.
- 공개 페이지 구조에서 `bookNm`, `bookId`, `ctgryCd`, `currentPage` 필드를 확인했다.
- 교재별 상세 경로 `DetailBkErrInfo.ebs?bookId={BOOK_ID}`도 존재한다.
- 따라서 collector는 사용자가 검색 버튼을 누르는 과정을 대신하여 교재명/bookId로 결과를 조회하고, 정오표가 있으면 교재별 상세/다운로드 주소를 연결하도록 구현한다.
- 아직 결과 유무 판별이 확정되지 않은 교재는 검색 페이지를 fallback으로 유지한다.

## 2026-10-07 브라우저 collector 배치 결과

정적 HTML probe만으로는 첨부파일 `bookFlId`가 비어 있는 경우가 있었지만,
Playwright로 실제 페이지 렌더링 후 DOM을 읽으면 첨부파일의 `fncDownFile('...')` 값을 얻을 수 있었다.

현재 catalog에 등록된 EBS 8권을 일괄 실행한 결과 **8/8 모두 정답·해설 PDF direct_url 수집에 성공**했다.

확인된 흐름:

1. `detailBkAnsInfo.ebs?bookId={BOOK_ID}&no=5...` 접속
2. 렌더링 후 첨부파일 링크의 `fncDownFile('{bookFlId}')` 추출
3. `/ebs/lms/lmsk/bkAnsMngFLdown.ajax?bookFlId={bookFlId}` 호출
4. JSON의 `flNm`을 공식 PDF `direct_url`로 사용
5. `svNm`은 공식 파일명으로 확인
6. 상세 페이지는 계속 `resource_page` fallback으로 보존

현재 확인된 file ID:

- 수능특강 국어 독서 `LB00000005909` → `11247`
- 수능특강 국어 문학 `LB00000005908` → `11246`
- 수능특강 국어 언어와 매체 `LB00000005911` → `11249`
- 수능특강 수학 확률과통계 `LB00000005914` → `11255`
- 수능특강 영어 `LB00000005917` → `11250`
- 수능특강 영어독해연습 `LB00000005919` → `11293`
- 수능특강 영어듣기 `LB00000005918` → `11294`
- 수능완성 영어 `LB00000005984` → `11357`

`scripts/collectors/ebs_batch_collect.py`와 `Collect EBS seed answers` workflow로 현재 catalog의 EBS 교재를 반복 점검할 수 있다.
자동 수집 결과는 후보 데이터로 사용하고, catalog 수정은 검증 후 PR에서 반영하는 기존 원칙을 유지한다.

## 2026-10-07 EBS 초등·중학까지 같은 프로젝트로 확장

EBS는 학교급에 따라 공식 서비스와 교재 고유 ID 체계가 다르다.

### 고등
- 서비스: `www.ebsi.co.kr`
- 교재 고유 ID: `LB...`
- 현재 사용 중인 정답/정오표 collector 유지

### 초등
- 서비스: `primary.ebs.co.kr`
- 교재 목록: `/book/main/list`
- 정답지/자료실: `/book/main/correctAnswerList`
- 정오표: `/book/main/errataList`
- 교재 상세는 `textbookId=TB...` 형태를 사용하는 사례가 확인됨
- 대표 시리즈: 만점왕, 만점왕 통합본, 만점왕 단원평가, 만점왕 수학 플러스, 초등 수해력 등

### 중학
- 서비스: `mid.ebs.co.kr`
- 교재 목록: `/book/main/list`
- 정답지/자료실: `/book/main/correctAnswerList`
- 정오표: `/book/main/errataList`
- 교재 상세는 `textbookId=TB...` 형태
- 대표 시리즈: 중학 뉴런, 중학 뉴런 연산, 중학 수능특강, 필독 중학 국어, 수학 마스터 등

### 데이터 정규화
사용자 UI에서는 세 사이트를 별도 출판사처럼 나누지 않고 모두 **EBS**로 표시한다.
학교급 필터에서 초등/중등/고등이 구분되며, collector만 내부 사이트 차이를 처리한다.

- `publisher = EBS`
- `school_level = elementary | middle | high`
- `publisher_site = ebs_primary | ebs_middle | ebsi`
- `publisher_book_id = TB... | LB...`

즉 EBS가 내부적으로 세 사이트로 나뉘어도 사용자는 같은 교재 검색 UI와 같은 교재 상세 페이지를 사용한다.

## 2026-10-07 초등·중학 정답 자료 게시물 구조 확인

EBS 초등/중학도 고등 EBSi와 방식은 다르지만 교재별 정답 파일까지 자동 연결할 수 있음을 확인했다.

### 공통 흐름
1. 교재 상세의 `textbookId=TB...` 페이지 접속
2. 교재별 정답지/자료 hash 진입
3. 자료 게시판의 교재명 행에서 `goDetail('{게시물ID}', '-1')` 확인
4. 게시물 상세에서 첨부파일 `/board/common/download?division=&id=...` 추출
5. 이 공식 다운로드 주소를 `direct_url`로 저장
6. 게시물 상세 hash는 `resource_page` fallback으로 보존

### 직접 파일까지 확인된 대표 교재
- 초등 만점왕 수학 3-1
  - textbookId: `TB1000013052`
  - post: `60000464757`
  - attachment id: `30000005525`
- 중학 뉴런 수학1(상) (22 개정)
  - textbookId: `TB1000011110`
  - post: `60000456320`
  - attachment id: `30000004068`
- 중학 뉴런 수학 1(하)
  - textbookId: `TB1000012110`
  - post: `60000458763`
  - attachment id: `30000004533`

초등·중학은 고등의 `bookFlId → flNm` 방식이 아니라 **자료 게시물 → 첨부파일 id** 방식으로 adapter를 분리한다.

## 2026-10-07 EBS 목록 확장과 검증 상태

초등 공식 교재 목록에서 `textbookId`/교재명을 수집한 결과 451개,
중등 공식 교재 목록에서 156개, 합계 607개의 교재 ID·제목 후보를 확인했다.
단, 이 수치는 **정답 PDF 검증 수치가 아니라 목록 발견 수치**이다.

`data/ebs-school-targets.json`에 다음 확장 대상 24권을 분리해 기록했고,
이들의 공식 교재 ID·제목을 활용해 catalog에 같은 24권을 추가했다.
- 초등 15권: 만점왕 수학 1~6학년 중심, 국어/과학 일부
- 중등 9권: 중학 뉴런 수학 2~3학년, 국어/영어/과학 일부

신규 24권의 `answer.direct_url`은 아직 비어 있고 `needs_review`로 표시했다.
검증되지 않은 교재를 다른 학년의 답지로 연결하지 않기 위한 조치다.
안정적인 공식 다운로드 파일이 확인되면 해당 `book_id`를 유지한 채 direct_url만 채워 넣는다.

학교급은 사용자에게 하나의 EBS로 보이지만 내부 수집기는 각각 유지한다.
UI 점검 기준: `docs/UI_SCALING.md`.

## 2026-10-07 MP3 및 초등 답지 추가 검증

### EBSi 영어 MP3
영어 MP3 목록의 교재 행은 `mp3Detail(bookId, iemDs, rowNum)`으로
`retrieveMp3Down.ebs` 교재별 상세 페이지에 진입한다.

상세 페이지의 각 음원 checkbox에는 다음 정보가 직접 들어 있다.

- `mp3url=https://wdown.ebsi.co.kr/bookmp3/{bookId}/...`
- 문항코드
- 단원/회차
- 통파일 여부

현재 2027 영어 교재 4권에서 실제 MP3를 확인했다.

- 수능완성 영어: 91개 MP3, 통파일 후보 6개
- 수능특강 영어: 277개 MP3, 통파일 후보 34개
- 수능특강 영어독해연습: 244개 MP3, 통파일 후보 16개
- 수능특강 영어듣기: 305개 MP3, 통파일 후보 30개

한 교재에 파일이 많으므로 임의의 MP3 하나를 대표 direct_url로 저장하지 않는다.
사용자 MP3 뱃지는 검증된 `retrieveMp3Down.ebs?bookId=...` 교재 상세로 연결하고,
개별 mp3url은 collector 결과에서 검증 근거로 사용한다.

### 초등 답지 추가
HEAD 응답의 `Content-Disposition`까지 확인하여 다음 정답 PDF를 direct_url로 승격했다.

- 만점왕 수학 1-1 — attachment `30000005523`
- 만점왕 국어 1-2 — attachment `30000006560`

### 초등·중등 정오표
정오표 게시물은 유사 시리즈/학년 오매칭 위험이 더 커서,
정규화한 대상 교재명이 게시물 제목에 정확히 포함되는 경우만 후보로 인정한다.
샘플 재검사에서는 확정 가능한 정오표가 없었으므로 뱃지는 계속 숨김 상태를 유지한다.
새 정오표는 주기적 sync가 실제 첨부파일 응답까지 검증한 경우에만 노출한다.
## 2026-10-07 EBSi MP3 확인 방식

EBSi 영어 MP3는 정답 PDF와 달리 하나의 파일이 아니라 교재별로 많은 음원으로 구성될 수 있다.

확인된 예:
- 2027 수능특강 영어: 277개 MP3
- 2027 수능특강 영어독해연습: 244개 MP3
- 2027 수능특강 영어듣기: 305개 MP3

교재별 상세 URL은 `retrieveMp3Down.ebs?bookId=LB...&iemDs=...` 형태로 확인되며,
실제 개별 음원은 `wdown.ebsi.co.kr/bookmp3/{bookId}/...`에 있다.

운영 원칙:
1. 실제 MP3 목록이 확인되면 `availability=available`
2. 사용자 버튼은 교재별 MP3 상세 화면으로 연결
3. 특정 음원 하나를 임의로 대표 direct_url로 저장하지 않음
4. 파일을 확인하지 못한 교재는 `unknown`으로 숨김
5. `Sync EBSi optional materials` workflow가 주기적으로 상태를 재점검
## 2026-10-07 수능완성 영어 MP3 판정 보정

EBS 공식 교재 검색에서는 **2027학년도 수능완성 영어영역 영어**에 MP3가 제공되는 것으로 표시된다.
기존 브라우저 probe도 `LB00000005984`의 `mp3Detail(...)` 상세 페이지까지는 정상 진입했지만,
실제 목록이 `retrieveMp3Down.ajax`에서 후속 로딩되는 구조를 충분히 읽지 못해 0개로 오판했다.

따라서:
- 해당 교재 MP3는 `availability=available`로 복구
- probe는 `retrieveMp3Down.ajax` 응답 자체의 MP3 URL도 검사
- `#ajaxArea`가 채워질 때까지 기다린 뒤 DOM을 재검사
- 일시적/구조적 수집 실패만으로 기존 `available` 자료를 자동 숨기지 않음

