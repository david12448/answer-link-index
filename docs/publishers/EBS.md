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
5. 교재명 자체는 공식 교재 상세 페이지 링크다.

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
