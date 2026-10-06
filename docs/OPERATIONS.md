# 운영 가이드

## 자동 링크 점검
check-links workflow는 매주 월요일·목요일 오전 9:15 KST에 실행합니다.

점검 대상:
- official_page
- resource_page
- direct_url

결과는 data/link-status.json에 기록합니다.

상태:
- ok: 정상 응답
- redirect: 다른 URL로 이동
- restricted: 401/403
- broken: 404
- http_error: 기타 HTTP 오류
- network_error: 시간초과/DNS 등 네트워크 오류

링크체커는 변경 감지기이지 자동 정답 판별기가 아닙니다.
200 응답이어도 메인페이지/로그인페이지일 수 있으므로 출판사별 검증을 추가합니다.

## PR 운영
1. 기능 단위 브랜치에서 작업
2. 기능 단위 PR 생성
3. 사용자 확인 후 merge
4. 시행착오는 docs/LESSONS.md 업데이트
5. 구조적 결정은 docs/DECISIONS.md 업데이트

다음 GPT 작업에서도 docs의 기록을 먼저 읽는 것을 원칙으로 합니다.

## EBS 정오표 자동 점검
EBS 정오표는 발생 빈도가 높지 않으므로 기존 링크 검사와 같은 주 2회 주기로 점검합니다.

- 실행: 매주 월요일·목요일 오전 9:45 KST
- 대상: catalog에 등록된 EBS 교재의 errata 자료
- 우선순위:
  1. 실제 정오표 파일이 확인되면 공식 EBS 다운로드 주소를 direct_url로 연결
  2. 정오표 파일이 아직 없으면 교재명이 자동 입력된 EBS 정오표 검색 페이지를 resource_page로 사용
  3. 검색어 자동 입력 방식이 EBS 변경으로 깨질 때만 공통 정오표 페이지를 최종 fallback으로 사용
- 새 정오표가 발견되어 catalog가 바뀔 때만 자동 PR을 생성합니다.
- EBS 일시 오류 때문에 기존 direct_url을 자동 삭제하지 않습니다.

