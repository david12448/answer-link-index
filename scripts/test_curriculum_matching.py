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
