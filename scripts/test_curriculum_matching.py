"""회귀 검사: 교육과정 혼동과 동점 후보의 임의 선택을 방지한다."""
import ast
import re
from pathlib import Path

source = Path(__file__).parent / "collectors/ebs_school_material_probe.py"
tree = ast.parse(source.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {"curriculum_year", "normalize_title", "choose_matching_row"}]
ns = {"re": re}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), ns)
choose = ns["choose_matching_row"]
assert ns["curriculum_year"]("2022교육과정 적용") == "2022"
assert ns["curriculum_year"]("15개정") == "2015"
old = {"text": "중학 뉴런 과학 1 (2015개정)"}
new = {"text": "중학 뉴런 과학 1 (2022개정)"}
assert choose([old, new], "중학 뉴런 과학 1", "2022 개정") == new
assert choose([new, old], "중학 뉴런 과학 1", "2015 개정") == old
assert choose([old], "중학 뉴런 과학 1", "2022 개정") is None
assert choose([old, new], "중학 뉴런 과학 1") is None
assert choose([{"text": "중학 뉴런 과학 2"}], "중학 뉴런 과학 1") is None
print("Curriculum matching regression checks passed")

# 안전 후보 검사는 공식 host/path만 허용하며, 파일명만 PDF인 HTML 오류 응답은 거부한다.
from urllib.parse import parse_qs, urlparse
sync_source = source.with_name('ebs_school_answer_sync.py')
tree = ast.parse(sync_source.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {'safe_candidate', 'verify_download'}]
ns.update(parse_qs=parse_qs, urlparse=urlparse, DOWNLOAD_PATH='/board/common/download', PDF_RE=re.compile(r'\.pdf$', re.I))
exec(compile(ast.Module(body=functions, type_ignores=[]), str(sync_source), 'exec'), ns)
book = {'title': '만점왕 수학 3-1', 'publisher_site': 'ebs_primary'}
result = {'matched_row': {'text': '2026 만점왕 수학 3-1 정답과 해설'},
          'final_url': 'https://primary.ebs.co.kr/book/main/view?textbookId=TB1#answer/view/115/123',
          'direct_candidates': [{'text': '정답.pdf', 'url': 'https://primary.ebs.co.kr/board/common/download?id=123'}]}
assert ns['safe_candidate'](book, result)
for url in ('https://example.com/board/common/download?id=123',
            'https://primary.ebs.co.kr/board/common/download-extra?id=123',
            'http://primary.ebs.co.kr/board/common/download?id=123'):
    modified = dict(result, direct_candidates=[{'text': '정답.pdf', 'url': url}])
    assert ns['safe_candidate'](book, modified) is None
class Response:
    ok = True
    status = 200
    url = 'https://primary.ebs.co.kr/board/common/download?id=123'
    headers = {'content-type': 'application/octet-stream', 'content-disposition': 'attachment; filename=answer.pdf'}
    payload = b'<html>error</html>' * 100
    def body(self): return self.payload
class Request:
    def get(self, *args, **kwargs): return Response()
class Context:
    request = Request()
candidate = {'url': Response.url, 'resource_page': result['final_url']}
assert not ns['verify_download'](Context(), candidate)['ok']
Response.payload = b'%PDF-1.7\n' + b'x' * 1000
assert ns['verify_download'](Context(), candidate)['ok']
print('Official host and PDF response regression checks passed')

answer = {"text": "초등 영어듣기평가 완벽대비 3-1 정답과 해설"}
extra = {"text": "초등 영어듣기평가 완벽대비 3-1 부가자료"}
assert choose([extra, answer], "초등 영어듣기평가 완벽대비 3-1") == answer
assert choose([answer, {"text": "초등 영어듣기평가 완벽대비 3-1 정답과 해설"}], "초등 영어듣기평가 완벽대비 3-1") is None
print('Answer/extra role matching regression checks passed')

# 같은 교육과정의 표기 차이를 허용하되 구판은 계속 거부한다.
assert ns['normalize_title']('한 장 수학 1(상) (2022 개정 교육과정 반영)') == ns['normalize_title']('한 장 수학 1(상)(22개정)')
row22 = {'text': '한 장 수학 1(상)(22개정) 정답과 해설'}
row15 = {'text': '한 장 수학 1(상)(15개정) 정답과 해설'}
assert choose([row15, row22], '한 장 수학 1(상) (2022 개정 교육과정 반영)', '2022 개정') == row22
assert choose([row15], '한 장 수학 1(상) (2022 개정 교육과정 반영)', '2022 개정') is None
assert choose([row15, row22], '한 장 수학 1(상)') is None
print('Curriculum notation equivalence regression checks passed')

long_name = {'text': '한 장 수학 중학 수학 1(상) (2022 개정 교육과정 반영)'}
assert choose([long_name], '한 장 수학 1(상) (2022 개정 교육과정 반영)', '2022 개정') == long_name
assert ns['normalize_title']('한 장 수학 중학 수학 1(상)') != ns['normalize_title']('한 장 수학 1(하)')
assert ns['normalize_title']('한 장 수학 수학 2(상)') != ns['normalize_title']('한 장 수학 1(상)')
print('Official Han-jang title variant regression checks passed')


# 교재별 official hash는 판본 근거가 되지만 전역 검색/다른 ID/명시된 충돌은 거부한다.
assert ns['curriculum_year']('2022') == '2022'
scoped_book = {'title': '뉴런 기출로 영문법 중1', 'publisher_site': 'ebs_middle',
               'publisher_book_id': 'TB1000013123', 'curriculum': '2022'}
scoped_url = 'https://mid.ebs.co.kr/book/main/view?textbookId=TB1000013123'
scoped_result = {'official_page': scoped_url,
                 'per_book_hash': {'href': '#answer/list/103/1/TB1000013123'},
                 'matched_row': {'text': '중학 뉴런 기출로 영문법 중1 정답과 해설'},
                 'post_id': '60000470304',
                 'final_url': scoped_url + '#answer/view/103/60000470304/0/1/TB1000013123/0///',
                 'direct_candidates': [{'text': '정답.pdf', 'url': 'https://mid.ebs.co.kr/board/common/download?id=30000005868'}]}
assert ns['safe_candidate'](scoped_book, scoped_result)
for modified in (
    dict(scoped_result, per_book_hash=None),
    dict(scoped_result, per_book_hash={'href': '#answer/list/103/1/TB1000013124'}),
    dict(scoped_result, post_id='other-post'),
    dict(scoped_result, final_url=scoped_result['final_url'].replace('/TB1000013123/', '/TB1000013124/')),
    dict(scoped_result, official_page=scoped_url.replace('mid.ebs.co.kr', 'example.com')),
    dict(scoped_result, matched_row={'text': '중학 뉴런 기출로 영문법 중1 (2015개정) 정답과 해설'}),
    dict(scoped_result, matched_row={'text': '중학 뉴런 기출로 영문법 중2 정답과 해설'}),
):
    assert ns['safe_candidate'](scoped_book, modified) is None
listening = dict(scoped_book, title='중학 영어듣기능력평가 완벽대비 중1 (2025)', edition_year=2025)
assert ns['safe_candidate'](listening, dict(scoped_result, matched_row={'text': '중학 영어듣기능력평가 완벽대비 중1 (2023) 정답과 해설'})) is None
print('Official textbook scope and conflicting edition regression checks passed')


errata_source = source.with_name('ebs_school_errata_probe.py')
tree = ast.parse(errata_source.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'choose_strict_errata_row']
exec(compile(ast.Module(body=functions, type_ignores=[]), str(errata_source), 'exec'), ns)
choose_errata = ns['choose_strict_errata_row']
old_errata = {'text': '중학 뉴런 과학 2 (2015개정) 정오표'}
new_errata = {'text': '중학 뉴런 과학 2 (2022개정) 정오표'}
assert choose_errata([old_errata, new_errata], '중학 뉴런 과학 2', '2022') == new_errata
assert choose_errata([old_errata], '중학 뉴런 과학 2', '2022') is None
assert choose_errata([{'text': '중학 뉴런 과학 2 정오표'}], '중학 뉴런 과학 2', '2022') is None
assert choose_errata([new_errata, new_errata], '중학 뉴런 과학 2', '2022') is None
assert choose_errata([{'text': '영어듣기 중1 (2023) 정오표'}], '영어듣기 중1 (2025)') is None
errata_sync_source = source.with_name('ebs_school_errata_sync.py')
tree = ast.parse(errata_sync_source.read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'verify_download']
exec(compile(ast.Module(body=functions, type_ignores=[]), str(errata_sync_source), 'exec'), ns)
Response.url = 'https://primary.ebs.co.kr/board/common/download?id=123'
Response.payload = b'<html>error</html>' * 100
assert not ns['verify_download'](Context(), Response.url, 'https://primary.ebs.co.kr/book/main/errataList')['ok']
Response.payload = b'%PDF-1.7' + b'x' * 1000
assert ns['verify_download'](Context(), Response.url, 'https://primary.ebs.co.kr/book/main/errataList')['ok']
assert not ns['verify_download'](Context(), 'https://example.com/board/common/download?id=123', 'https://primary.ebs.co.kr/book/main/errataList')['ok']
Response.url = 'https://example.com/error.pdf'
assert not ns['verify_download'](Context(), 'https://primary.ebs.co.kr/board/common/download?id=123', 'https://primary.ebs.co.kr/book/main/errataList')['ok']
print('Errata curriculum, edition, HTML error and redirect regression checks passed')
