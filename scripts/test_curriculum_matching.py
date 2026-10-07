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
