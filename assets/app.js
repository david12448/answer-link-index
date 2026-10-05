const state = { books: [], meta: {} };

const labels = {
  elementary: "초등",
  middle: "중등",
  high: "고등",
  ok: "링크 확인",
  redirect: "주소 이동",
  login_required: "로그인 필요",
  needs_review: "확인 필요",
  broken: "링크 오류",
  unknown: "미확인"
};

const el = id => document.getElementById(id);
const normalize = value => String(value ?? "")
  .toLowerCase()
  .replace(/[\s._\-·/()\[\]]+/g, "");

function searchableText(book) {
  const materialText = (book.materials || []).flatMap(m => [m.title, m.type]).join(" ");
  const courseText = (book.courses || []).flatMap(c => [c.title, c.teacher, c.source_course_id]).join(" ");
  return [
    book.title, book.publisher, book.brand, book.subject, book.grade, book.semester,
    book.curriculum, book.edition_year, book.isbn, book.book_type,
    ...(book.aliases || []), materialText, courseText
  ].join(" ");
}

function matchesSearch(book, query) {
  if (!query.trim()) return true;
  const haystack = normalize(searchableText(book));
  return query.trim().split(/\s+/).every(token => haystack.includes(normalize(token)));
}

function uniqueValues(key) {
  return [...new Set(state.books.map(book => book[key]).filter(v => v !== null && v !== undefined && v !== ""))]
    .sort((a,b) => String(a).localeCompare(String(b), "ko"));
}

function fillSelect(id, key) {
  const select = el(id);
  const first = select.options[0].cloneNode(true);
  select.innerHTML = "";
  select.append(first);
  for (const value of uniqueValues(key)) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = key === "school_level" ? (labels[value] || value) : value;
    select.append(option);
  }
}

function materialStatus(book) {
  const statuses = (book.materials || []).map(m => m.status || "unknown");
  if (!statuses.length) return "unknown";
  if (statuses.includes("broken")) return "broken";
  if (statuses.includes("needs_review")) return "needs_review";
  if (statuses.includes("login_required")) return "login_required";
  if (statuses.every(s => s === "ok")) return "ok";
  return statuses[0];
}

function createMaterialLink(label, href, primary = false) {
  if (!href) return null;
  const a = document.createElement("a");
  a.className = "material-link" + (primary ? " primary" : "");
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.textContent = label;
  return a;
}

function renderBook(book) {
  const fragment = el("bookTemplate").content.cloneNode(true);
  fragment.querySelector(".school-badge").textContent =
    `${labels[book.school_level] || book.school_level} ${book.grade ? book.grade + "학년" : ""}`.trim();

  const status = materialStatus(book);
  const statusEl = fragment.querySelector(".status-badge");
  statusEl.textContent = labels[status] || status;
  statusEl.classList.add(status);

  const titleEl = fragment.querySelector(".book-title");
  if (book.official_page) {
    const titleLink = document.createElement("a");
    titleLink.href = book.official_page;
    titleLink.target = "_blank";
    titleLink.rel = "noopener noreferrer";
    titleLink.textContent = book.title;
    titleEl.append(titleLink);
  } else {
    titleEl.textContent = book.title;
  }
  fragment.querySelector(".book-meta").textContent =
    [book.publisher, book.brand, book.subject, book.semester ? book.semester + "학기" : null]
      .filter(Boolean).join(" · ");
  fragment.querySelector(".book-submeta").textContent =
    [book.curriculum, book.edition_year ? book.edition_year + "년판" : null, book.isbn ? "ISBN " + book.isbn : null]
      .filter(Boolean).join(" · ");

  const materials = fragment.querySelector(".materials");
  for (const material of book.materials || []) {
    const loginRequired = material.access === "login_required";
    const best = loginRequired
      ? (material.resource_page || book.official_page)
      : (material.direct_url || material.resource_page || book.official_page);

    const buttonLabel = loginRequired
      ? "출판사에서 로그인 후 다운로드"
      : (material.direct_url ? (material.title || "정답/해설 다운로드") : (material.title || "공식 자료 보기"));

    const primary = createMaterialLink(buttonLabel, best, true);
    if (primary) materials.append(primary);
  }

  for (const course of book.courses || []) {
    if (!course.course_url) continue;
    const teacher = course.teacher ? ` · ${course.teacher}` : "";
    const courseLink = createMaterialLink(`인강${teacher}`, course.course_url, false);
    if (courseLink) {
      courseLink.classList.add("course-link");
      courseLink.title = course.title || "관련 인강";
      materials.append(courseLink);
    }
  }
  return fragment;
}

function applyFilters() {
  const query = el("searchInput").value;
  const selected = {
    school_level: el("schoolFilter").value,
    grade: el("gradeFilter").value,
    subject: el("subjectFilter").value,
    publisher: el("publisherFilter").value,
    brand: el("brandFilter").value
  };

  const filtered = state.books.filter(book => {
    if (!matchesSearch(book, query)) return false;
    return Object.entries(selected).every(([key, value]) => !value || String(book[key] ?? "") === value);
  });

  const results = el("results");
  results.innerHTML = "";
  el("resultCount").textContent = filtered.length;

  if (!filtered.length) {
    results.innerHTML = '<div class="empty">조건에 맞는 교재가 없습니다.</div>';
    return;
  }
  filtered.forEach(book => results.append(renderBook(book)));
}

function resetFilters() {
  el("searchInput").value = "";
  ["schoolFilter","gradeFilter","subjectFilter","publisherFilter","brandFilter"]
    .forEach(id => el(id).selectedIndex = 0);
  applyFilters();
}

async function init() {
  try {
    const response = await fetch("data/catalog.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.books = data.books || [];
    state.meta = data.meta || {};

    fillSelect("schoolFilter", "school_level");
    fillSelect("gradeFilter", "grade");
    fillSelect("subjectFilter", "subject");
    fillSelect("publisherFilter", "publisher");
    fillSelect("brandFilter", "brand");

    el("updatedAt").textContent = state.meta.generated_at ? `데이터 기준 ${state.meta.generated_at}` : "";
    applyFilters();

    el("searchInput").addEventListener("input", applyFilters);
    ["schoolFilter","gradeFilter","subjectFilter","publisherFilter","brandFilter"]
      .forEach(id => el(id).addEventListener("change", applyFilters));
    el("resetButton").addEventListener("click", resetFilters);
  } catch (error) {
    el("results").innerHTML = `<div class="empty">데이터를 불러오지 못했습니다: ${error.message}</div>`;
  }
}

document.addEventListener("DOMContentLoaded", init);
