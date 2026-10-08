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

## EBS 초등·중등 정오표 자동 점검

- 매주 월요일·목요일 오전 10:15 KST에 일부 미확인 교재부터 점검합니다.
- 교재명 정확 일치 → 정오표 상세 → 공식 첨부파일 1개 → 실제 파일 응답 검증을 모두 통과해야 자동 PR을 만듭니다.
- 정오표가 없거나 애매하면 catalog를 변경하지 않고 뱃지도 숨긴 상태를 유지합니다.
- 다른 학년/학기 유사 제목은 자동 매칭하지 않습니다.

## EBSi 영어 MP3 자동 점검

- 매주 화요일·금요일 오전 10:45 KST에 EBSi 영어 교재의 MP3 존재를 확인합니다.
- 해당 bookId의 교재별 MP3 상세 페이지에 실제 공식 `wdown.ebsi.co.kr/bookmp3/{bookId}/` 파일이 존재할 때만 MP3 자료를 `available`로 승격합니다.
- 한 교재에 MP3가 여러 개이므로 catalog에는 교재별 MP3 상세 페이지를 연결하고 개별 음원 수백 개를 모두 저장하지 않습니다.
- 변화가 있을 때만 검토용 PR을 생성합니다.
## 대량 catalog CI 운영

교재가 늘어나도 PR 피드백이 느려지지 않도록 검증을 두 층으로 나눕니다.

### 모든 PR
- JSON Schema
- 중복 book/resource/publisher ID
- 학교급/학년 및 EBS ID/host 일관성
- collector Python 문법
- JavaScript 문법
- 2,000권 UI 필터 smoke test
- catalog 품질 요약

### 외부 EBS 브라우저 검사
- collector/workflow 코드가 바뀔 때 probe smoke test
- 정답/정오표/MP3/표지는 각 scheduled sync에서 주기 점검
- 실제 자료가 새로 확인되면 자동 PR 생성
- 단순 catalog 데이터 수정만으로 전체 Playwright probe를 반복하지 않음



## 자동 PR 권한 복구 확인 (2026-10-08)

사용자가 Allow GitHub Actions to create and approve pull requests 설정을 켠 뒤 main의 Check official links 실행 37734857718을 재실행했다. 실제 실행은 success로 완료됐으며 github-actions가 PR #4(automation/link-status)를 생성했다. 권한 차단은 해소됐다. 자동 승인이나 main 병합은 하지 않는다.

검사 결과 보존을 위해 PR 생성 전에 official-link-status artifact를 업로드하도록 feature에서 보완했다. 초·중등 정답/정오표/표지 및 MP3 sync는 현재 feature의 구현이며 main 병합 전 scheduled 운영 중이라고 표현하지 않는다.

정오표 sync는 available 교재도 순환 점검해 후속 게시물을 감시한다. 제목만 유사한 구판·학년·연도와 HTML 파일 오류는 거부하며 여러 첨부에서는 상세 화면을 사용한다. 품질 리포트는 초·중등 진행률과 별도로 전체 catalog의 정오표/MP3/부가자료 available/unavailable/unknown 수를 제공한다.

이미 검증된 정오표 direct가 있는 교재의 단일 파일 재검증이 일시 실패하면 기존 링크를 유지한다. 검색 실패도 기존 자료의 삭제 근거로 쓰지 않는다. 실제 여러 첨부가 확인되는 경우에만 임의 파일 대신 정확한 상세 페이지로 연결한다.
