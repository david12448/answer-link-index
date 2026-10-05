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
