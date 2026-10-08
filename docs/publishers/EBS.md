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
## 2026-10-07 초등·중등 공식 표지 자동 수집

초등·중등 교재 상세 페이지의 공식 표지는 `cbox.ebs.co.kr/textbook/`에서 제공되는 사례가 확인된다.

자동 반영 조건:
1. 해당 교재의 official_page에서 발견
2. URL host/path가 EBS 공식 cbox textbook 영역
3. 이미지 URL에 동일한 `TB...` textbookId 포함
4. 실제 `image/*` 응답과 충분한 파일 크기 확인
5. 유효 후보가 정확히 하나

표지는 재호스팅하지 않고 `cover_image_url`에 공식 주소만 저장한다.
`Sync EBS school covers` workflow는 표지가 비어 있는 교재를 순환 점검하고 변경 시 PR을 만든다.


## 2026-10-08 검증 보완

- 등록된 초·중등 공식 표지: 90/90권. HTML의 og:image와 img에서 같은 textbookId의 cbox 이미지를 찾고 실제 GET 응답으로 검증했다.
- 초등 정답지는 교재별 `tid`가 지정된 `/board/book/list` 및 `/board/book/view` 요청으로 교재와 게시물을 연결할 수 있다. JS hash는 브라우저의 화면 주소이고 실제 자료 HTML은 이 AJAX 응답에서 온다.
- 중등은 `/book/main/correctAnswerList`가 출발점이며, 같은 제목의 2015/2022 자료가 함께 있을 수 있으므로 교육과정 근거가 없는 항목은 자동 승격하지 않는다.
- PDF 검증은 파일명·HEAD만으로 끝내지 않고 공식 `/board/common/download`에 GET하여 PDF 서명을 검사한다.

### 추가 교재 검증 근거
- `TB1000012073`, `TB1000012148`: 공식 제목 자체에 2022 개정 교육과정 반영, 중학 수학1 상/하 명시.
- `TB1000013123`, `TB1000013124`, `TB1000013125`: 공식 제목은 뉴런 기출로 영문법 중1/2/3. 해당 상세 페이지의 동일 제목·학년 연계 강좌에 2022개정 명시.
- 위 5권의 제목은 공식 목록과 상세 og:title을 대조했고, 표지는 textbookId 포함 cbox URL의 HTTP 200 image/* 응답으로 확인했다. 학년 범위가 불분명한 50일 수학·중학 국어 어휘 등은 이번 묶음에서 제외했다.
- 기존 초등 영어듣기 3~6학년 각 학기는 정답과 해설 / 부가자료의 역할을 먼저 구분해야 한다. 단순 제목 동점으로 정답 후보를 모두 버리지 않되, 서로 다른 정답 후보가 동점이면 계속 보류한다.

### 한 장 수학 공식 제목 변형
- 교재 상세: ‘한 장 수학 1(상/하) (2022 개정 교육과정 반영)’
- 자료실: ‘한 장 수학 중학 수학 1(상/하) (2022 개정 교육과정 반영)’ 또는 시리즈 뒤에 ‘수학’ 반복
- 확인된 시리즈 접두사의 공식 표기 차이만 흡수한다. 학년·상하·교육과정은 제거하거나 추측하지 않는다. 개정 표기는 제목 비교에서 정규화하되 별도 교육과정 검사를 반드시 유지한다.
- 자료실 검색은 ‘한 장 수학’으로 넓힌 뒤 정확한 교재/판본 검사로 좁힌다. 여러 동점 정답 후보는 계속 보류한다.

### 중2 수학 마스터 교육과정과 자료 게시물 대조 (2026-10-08)

공식 교재 상세의 동일 제목·학년·학기 연계 강좌에서 `(2022개정)`을 각각 확인해 아래 6권의 curriculum을 2022로 보완했다. 교재의 교육과정 확인과 답지 파일의 판본 확인은 별개다.

| textbookId | 교재 | 자료실 후보 postId |
| --- | --- | --- |
| TB1000012137 | 개념 α 중2-1 | 60000462572 |
| TB1000012138 | 유형 β 중2-1 | 60000462573 |
| TB1000012139 | 고난도 Σ 중2-1 | 60000462574 |
| TB1000012168 | 개념 α 중2-2 | 60000462575 |
| TB1000012169 | 유형 β 중2-2 | 60000462576 |
| TB1000012170 | 고난도 Σ 중2-2 | 60000462577 |

근거 페이지는 각 `https://mid.ebs.co.kr/book/main/view?textbookId={textbookId}`. 자료실은 `https://mid.ebs.co.kr/book/main/correctAnswerList`에서 ‘수학 마스터’로 검색했다. 자료실은 ‘중학 수학마스터 2-1학기 알파북 정답 및 풀이’처럼 교재 제목과 다른 표기를 사용한다. 검색을 넓혀 후보를 찾을 수 있지만, 알파/베타/시그마 별칭을 시리즈 전체에 무조건 적용해서는 안 된다.

알파 2-1 후보의 단일 첨부 `30000004956`은 공식 다운로드 GET HTTP 200 및 `%PDF-` 응답을 확인했다. 그러나 게시물 제목과 PDF 첫 3페이지에서 교육과정이나 ISBN 근거를 확보하지 못했다. 따라서 direct URL은 반영하지 않았다. 나머지 5개 게시물은 목록에서 후보 존재만 확인했으며 파일 검증 완료로 기록하지 않는다.

뉴런 연산 수학1(상) 후보 postId `60000457520`의 첨부 `30000004291`, 기출로 영문법 중1 후보 `60000470304`의 첨부 `30000005868`도 실제 공식 HTTP 200/PDF를 확인했다. 각각 2024-09 / 2026-01 제작 시각은 있으나 제작 연도만으로 교육과정을 확정하지 않는다. 동일 학년·제목의 파일 존재 확인을 판본 일치 확인으로 간주하지 않고 fallback을 유지했다.


### 중등 교재별 자료 hash 복원 (2026-10-08)

기존 collector는 중등이면 official_page의 교재별 hash를 무조건 버리고 전역 correctAnswerList로 이동했다. 이 때문에 공식 교재에 직접 연결된 최신 자료도 전역 검색의 구판 후보와 혼동하거나 교육과정 표기 부족으로 보류했다. 중등도 상세에서 발견한 `#answer/list/103/1/{textbookId}`를 우선 사용하고, 없을 때만 전역 자료실로 fallback한다.

공식 `common-tab-back.js`의 bookInnerFn은 list hash의 tid를 `/board/book/list` 요청에 전달한다. 동일 tid의 응답에서 대상 교재 게시물이 나오고, 상세 hash에도 같은 tid 및 postId가 유지되는 것을 판본 연결 근거로 인정한다. 공식 host/path, 제목/학년/상하, 명시된 교육과정·연도 충돌, 단일 PDF, 실제 GET/PDF 서명 검사는 별도로 유지한다. 단순히 tid를 붙여 요청했다는 사실만으로는 부족하며 해당 hash가 공식 교재 상세에 실제 존재해야 한다.

| textbookId | 게시물 | 단일 첨부 ID | 교재 |
| --- | --- | --- | --- |
| TB1000012051 | 60000457520 | 30000004291 | 뉴런 연산 수학1 상 |
| TB1000012052 | 60000457521 | 30000004292 | 뉴런 연산 수학1 하 |
| TB1000013106 | 60000470182 | 30000005886 | 뉴런 과학2 |
| TB1000013220 | 60000479646 | 30000008153 | 뉴런 영어3 |
| TB1000013123 | 60000470304 | 30000005868 | 기출로 영문법 중1 |
| TB1000013124 | 60000470305 | 30000005869 | 기출로 영문법 중2 |
| TB1000013125 | 60000470306 | 30000005870 | 기출로 영문법 중3 |

위 7개 파일은 모두 HTTP 200, 공식 mid host 유지, 실제 PDF 서명과 첫 페이지의 교재/학년/상하를 대조했다. 연산1 상·하는 같은 교재 상세의 정확한 강좌명에서 2022개정을 추가 확인해 curriculum을 보완했다. 뉴런 영어3은 교육과정 문자열을 추측하지 않고 기존 null을 유지하며 공식 textbookId 연결로 판본을 식별한다.

반례: TB1000010434/435/436의 2025 영어듣기 교재 hash에서 2023 정답/MP3 게시물이 반환된다. 공식 교재별 연결이 있어도 연도 충돌이 있으므로 자동 연결하지 않는다. 수학 마스터 중2 6권은 교재별 answer hash와 tid 응답이 없어 여전히 전역 자료실 후보 단계다. 만점왕 단원평가3-1은 게시물 검색 결과가 비어도 자료 없음으로 판정하지 않는다.

### 로그인 필요한 실제 정오표와 XLSX 첨부
중학 뉴런 수학1(상) 22개정(TB1000011110)의 corr 게시물 60000456604에서 동일 제목·교육과정 및 XLSX 정오표 첨부를 확인했다. 공식 상세는 `https://mid.ebs.co.kr/book/main/errataList#corr/view/105/60000456604/0/1//0/title/중학%20뉴런%20수학1(상)%20(22%20개정)/`이다. 비로그인 응답의 첨부 anchor는 javascript:; 및 LoginFocus를 사용하므로 파일 ID를 추측하지 않는다. availability=available, access=login_required, direct_url=null로 정확한 상세 페이지를 연결한다. 첨부 탐지에 XLS/XLSX·MP3 파일명을 포함했으며 로그인 요구와 실제 파일 미검증을 구분한다.
