# 공개 화면과 내부 운영 자료의 경계

다른 사람이 쉽게 전체 시스템을 복제하지 못하게 하는 방향을 기본으로 한다. 핵심 원칙은 내부 자산을 애초에 브라우저로 전달하지 않는 것이다. 공개 화면에 전달된 JavaScript와 공식 자료 URL은 방문자가 볼 수 있다. 우클릭 금지나 난독화는 핵심 보호 수단으로 취급하지 않는다.

collector, source registry/landscape, raw snapshot, parser·pagination 규칙, API endpoint 매핑, correction registry, reconciliation 알고리즘, 품질 판정 기준은 핵심 내부 자산으로 관리하며 private 영역을 기본 목표로 한다. 공개 API와 화면에는 실제 사용자에게 필요한 정규화 결과만 제공한다. robots.txt나 검색 노출, 모바일 접근성을 희생하지 않는다. 이 원칙은 다른 데이터형 서비스에도 동일하게 적용한다.

## 현재 적용한 준비

`python scripts/build_public_site.py`는 새 `dist/public-site` 폴더에 index.html, assets/app.js, assets/style.css와 허용된 공개 data 파일만 만든다. 이미 존재하는 출력 폴더는 덮어쓰지 않는다. 다른 경로는 `--output`으로 지정한다.

공개 catalog는 허용 목록 방식으로 생성한다. 안정적인 book_id, 교재 탐색 정보, 표지와 공식 자료 링크를 유지한다. publisher_site, publisher_book_id, resource_id, publisher_file_id, source_course_id와 내부 검증 기록은 내보내지 않는다. unknown/unavailable인 선택 자료도 제외한다. 앞으로 새로운 내부 필드가 추가돼도 자동으로 공개되지 않는다. 공식 URL에 필요한 교재/파일 ID까지 숨길 수 있다는 의미는 아니다.

경로와 book_id를 유지하므로 `?book={book_id}&embed=1` 계약은 그대로다. PR 검증은 공개 catalog에 대해서도 검색·필터 테스트를 실행하고 public-site-preview artifact를 만든다. 이 artifact는 배포가 아니며 현재 raw.githack 화면의 데이터 경로는 바꾸지 않는다.

## 교재 한 권만 전달하는 단계

공개 묶음에는 `data/site.json`과 `data/books/{book_id}.json`을 생성한다. 새 형식의 개별 교재 화면은 descriptor와 해당 교재 한 권만 요청한다. 존재하지 않는 ID나 서버 오류를 이유로 전체 catalog를 추가 요청하지 않는다. 다른 ID의 응답도 거부한다. 기존 배포에서는 descriptor가 404일 때만 이전 catalog 경로를 사용해 기존 embed를 유지한다.

전체 검색 화면은 아직 정적 catalog를 사용한다. 따라서 현재 묶음도 전체 정규화 데이터의 수집을 막는 API 보안 구조는 아니다. 교재별 파일 분할은 전송 범위를 줄이는 단계다. 규모 증가 시 검색 조건에 따른 서버 페이지네이션, 교재 상세 API, 정상 사용자 요청에 맞춘 rate limit과 요청량 제한을 검토한다. 클라이언트의 20권 더보기는 서버 페이지네이션이나 요청 제한을 대신하지 않는다.

## 남은 중요한 한계와 다음 구조

현재 answer-link-index 저장소 자체가 public이므로 수집기와 과거 커밋은 여전히 복사할 수 있다. 이 내보내기만으로 저장소 소스가 보호됐다고 말하지 않는다.

실질적인 다음 구조는 수집기·검증 코드·원본 catalog·조사 기록을 private 저장소에서 관리하고, 검증을 통과한 public-site 출력만 기존 공개 주소에 전달하는 방식이다. 공개 저장소의 기존 이력에는 이미 내부 소스가 있으므로 이력 유지/주소 유지/새 공개 저장소 중 선택도 필요하다. 비공개 저장소 생성, 공개 범위 변경, 이력 삭제 또는 저장소 교체는 사용자 판단을 받은 뒤 진행한다. 기존 티스토리 링크의 연속성과 main 병합 승인 조건을 우선한다.

비공개 저장소의 Actions artifact도 공개하지 않는 것을 기본으로 한다. 검증 evidence와 수집기 로그는 공개 배포 파일에 포함하지 않는다. 공식 출판사 파일을 재호스팅하지 않는다.

공개 묶음의 실제 Chromium 검사는 UI/내보내기 코드 변경 또는 수동 실행 때만 수행한다. 개별 화면의 네트워크 요청이 전체 catalog를 받지 않는지, 없는 교재 처리, 모바일 가로 넘침, 20권 더보기, 제목 검색을 검증한다. catalog-only 변경에는 모든 PR의 경량 검사를 유지하고 무거운 UI 브라우저 검사를 다시 실행하지 않는다.
