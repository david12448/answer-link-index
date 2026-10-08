# 공개 화면과 내부 운영 자료의 경계

다른 사람이 쉽게 전체 시스템을 복제하지 못하게 하는 방향을 기본으로 한다. 공개 화면에 전달된 JavaScript와 공식 자료 URL은 방문자가 볼 수 있다. 우클릭 금지나 난독화는 핵심 보호 수단으로 취급하지 않는다.

## 현재 적용한 준비

`python scripts/build_public_site.py`는 새 `dist/public-site` 폴더에 index.html, assets/app.js, assets/style.css, data/catalog.json만 만든다. 이미 존재하는 출력 폴더는 덮어쓰지 않는다. 다른 경로는 `--output`으로 지정한다.

공개 catalog는 허용 목록 방식으로 생성한다. 안정적인 book_id, 교재 탐색 정보, 표지와 공식 자료 링크를 유지한다. publisher_site, publisher_book_id, resource_id, publisher_file_id, source_course_id와 내부 검증 기록은 내보내지 않는다. unknown/unavailable인 선택 자료도 제외한다. 앞으로 새로운 내부 필드가 추가돼도 자동으로 공개되지 않는다. 공식 URL에 필요한 교재/파일 ID까지 숨길 수 있다는 의미는 아니다.

경로와 book_id를 유지하므로 `?book={book_id}&embed=1` 계약은 그대로다. PR 검증은 공개 catalog에 대해서도 검색·필터 테스트를 실행하고 public-site-preview artifact를 만든다. 이 artifact는 배포가 아니며 현재 raw.githack 화면의 데이터 경로는 바꾸지 않는다.

## 남은 중요한 한계와 다음 구조

현재 answer-link-index 저장소 자체가 public이므로 수집기와 과거 커밋은 여전히 복사할 수 있다. 이 내보내기만으로 저장소 소스가 보호됐다고 말하지 않는다.

실질적인 다음 구조는 수집기·검증 코드·원본 catalog·조사 기록을 private 저장소에서 관리하고, 검증을 통과한 public-site 출력만 기존 공개 주소에 전달하는 방식이다. 공개 저장소의 기존 이력에는 이미 내부 소스가 있으므로 이력 유지/주소 유지/새 공개 저장소 중 선택도 필요하다. 비공개 저장소 생성, 공개 범위 변경, 이력 삭제 또는 저장소 교체는 사용자 판단을 받은 뒤 진행한다. 기존 티스토리 링크의 연속성과 main 병합 승인 조건을 우선한다.

비공개 저장소의 Actions artifact도 공개하지 않는 것을 기본으로 한다. 검증 evidence와 수집기 로그는 공개 배포 파일에 포함하지 않는다. 공식 출판사 파일을 재호스팅하지 않는다.
