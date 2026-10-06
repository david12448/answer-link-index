const PAGE_SIZE = 20;

const state = {
  books: [],
  meta: {},
  visibleCount: PAGE_SIZE,
  view: "list",
  scope: {
    publisher: "",
    subject: "",
    grade: "",
    book: "",
    embed: false
  }
};

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

const schoolShort = {
  elementary: "초",
  middle: "중",
  high: "고"
};

const materialClass = {
  answer: "answer",
  errata: "errata",
  mp3: "mp3",
  additional: "additional"
};

const el = id => document.getElementById(id);

const normalize = value => String(value ?? "")
  .toLowerCase()
  .replace(/[\s._\-·/()\[\]]+/g, "");

function readScope() {
  const params = new URLSearchParams(window.location.search);
  state.scope.publisher = params.get("publisher") || "";
  state.scope.subject = params.get("subject") || "";
  state.scope.grade = params.get("grade") || "";
  state.scope.book = params.get("book") || "";
  state.scope.embed = params.get("embed") === "1";
}

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

function gradeToken(book) {
  if (!book.grade || !book.school_level) return "";
  return `${book.school_level}:${book.grade}`;
}

function gradeLabel(book) {
  if (!book.grade || !book.school_level) return "";
  return `${schoolShort[book.school_level] || ""}${book.grade}`;
}

function matchesGrade(book, value) {
  if (!value) return true;
  const raw = String(value).trim();
  if (raw.includes(":")) return gradeToken(book) === raw;

  const korean = raw.match(/^([초중고])(\d)$/);
  if (korean) {
    const level = { "초": "elementary", "중": "middle", "고": "high" }[korean[1]];
    return book.school_level === level && String(book.grade ?? "") === korean[2];
  }
  return String(book.grade ?? "") === raw;
}

function scopeMatches(book) {
  if (state.scope.publisher && book.publisher !== state.scope.publisher) return false;
  if (state.scope.subject && book.subject !== state.scope.subject) return false;
  if (state.scope.grade && !matchesGrade(book, state.scope.grade)) return false;
  if (state.scope.book && book.book_id !== state.scope.book) return false;
  return true;
}

function selectValue(id) {
  const node = el(id);
  return node ? node.value : "";
}

function effectiveFilters() {
  return {
    publisher: state.scope.publisher || selectValue("publisherFilter"),
    subject: state.scope.subject || selectValue("subjectFilter"),
    grade: state.scope.grade || selectValue("gradeFilter"),
    book: state.scope.book || selectValue("bookFilter")
  };
}

function matchesFilters(book, filters, ignoreKey = "") {
  if (!scopeMatches(book)) return false;
  if (ignoreKey !== "publisher" && filters.publisher && book.publisher !== filters.publisher) return false;
  if (ignoreKey !== "subject" && filters.subject && book.subject !== filters.subject) return false;
  if (ignoreKey !== "grade" && filters.grade && !matchesGrade(book, filters.grade)) return false;
  if (ignoreKey !== "book" && filters.book && book.book_id !== filters.book) return false;
  return true;
}

function sortedUnique(values) {
  return [...new Set(values.filter(v => v !== null && v !== undefined && v !== ""))]
    .sort((a, b) => String(a).localeCompare(String(b), "ko"));
}

function refillSelect(select, options, placeholder, selectedValue = "") {
  select.innerHTML = "";
  const first = document.createElement("option");
  first.value = "";
  first.textContent = placeholder;
  select.append(first);

  for (const item of options) {
    const option = document.createElement("option");
    if (typeof item === "object") {
      option.value = item.value;
      option.textContent = item.label;
    } else {
      option.value = String(item);
      option.textContent = String(item);
    }
    select.append(option);
  }

  if ([...select.options].some(option => option.value === selectedValue)) {
    select.value = selectedValue;
  }
}

function updateDependentSelects() {
  const filters = effectiveFilters();

  const publisherOptions = sortedUnique(
    state.books.filter(scopeMatches).map(book => book.publisher)
  );
  refillSelect(el("publisherFilter"), publisherOptions, "출판사 전체",
    state.scope.publisher || selectValue("publisherFilter"));

  const publisher = state.scope.publisher || selectValue("publisherFilter");
  const subjectBooks = state.books.filter(book =>
    scopeMatches(book) && (!publisher || book.publisher === publisher)
  );
  const subjectOptions = sortedUnique(subjectBooks.map(book => book.subject));
  refillSelect(el("subjectFilter"), subjectOptions, "과목 전체",
    state.scope.subject || filters.subject);

  const subject = state.scope.subject || selectValue("subjectFilter");
  const gradeBooks = state.books.filter(book =>
    scopeMatches(book) &&
    (!publisher || book.publisher === publisher) &&
    (!subject || book.subject === subject)
  );

  const gradeMap = new Map();
  for (const book of gradeBooks) {
    const token = gradeToken(book);
    if (token) gradeMap.set(token, gradeLabel(book));
  }
  const gradeOptions = [...gradeMap.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label, "ko"));

  let gradeSelection = filters.grade;
  if (state.scope.grade && !state.scope.grade.includes(":")) {
    const matching = gradeOptions.find(item =>
      matchesGrade(
        { school_level: item.value.split(":")[0], grade: Number(item.value.split(":")[1]) },
        state.scope.grade
      )
    );
    gradeSelection = matching?.value || "";
  }
  refillSelect(el("gradeFilter"), gradeOptions, "학년 전체",
    state.scope.grade ? gradeSelection : filters.grade);

  const grade = state.scope.grade || selectValue("gradeFilter");
  const bookBooks = state.books.filter(book =>
    scopeMatches(book) &&
    (!publisher || book.publisher === publisher) &&
    (!subject || book.subject === subject) &&
    (!grade || matchesGrade(book, grade))
  );
  const bookOptions = bookBooks
    .map(book => ({ value: book.book_id, label: book.title }))
    .sort((a, b) => a.label.localeCompare(b.label, "ko"));
  refillSelect(el("bookFilter"), bookOptions, "교재 선택",
    state.scope.book || filters.book);
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

function bookDetailUrl(book) {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  url.searchParams.set("book", book.book_id);
  if (state.scope.embed) url.searchParams.set("embed", "1");
  return url.toString();
}

function navigateToBook(book) {
  window.location.assign(bookDetailUrl(book));
}

function applyMaterialClasses(node, type = "", primary = false) {
  node.className = "material-link";
  if (primary) node.classList.add("primary");
  if (type && materialClass[type]) node.classList.add(materialClass[type]);
}

function createMaterialLink(label, href, type = "", primary = false) {
  if (!href) return null;
  const a = document.createElement("a");
  applyMaterialClasses(a, type, primary);
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.textContent = label;
  return a;
}

function createPreviewMaterialBadge(label, type, primary, book) {
  const a = document.createElement("a");
  applyMaterialClasses(a, type, primary);
  a.classList.add("preview-material");
  a.href = "javascript:void(0)";
  a.textContent = label;
  a.setAttribute("aria-label", `${label} - 교재 상세 페이지에서 보기`);
  a.addEventListener("click", event => {
    event.preventDefault();
    navigateToBook(book);
  });
  return a;
}

function setupCover(fragment, book) {
  const coverLink = fragment.querySelector(".cover-link");
  const image = fragment.querySelector(".cover-image");
  const placeholder = fragment.querySelector(".cover-placeholder");

  coverLink.href = bookDetailUrl(book);

  if (!book.cover_image_url) {
    image.hidden = true;
    placeholder.hidden = false;
    return;
  }

  placeholder.hidden = true;
  image.hidden = false;
  image.src = book.cover_image_url;
  image.alt = `${book.title} 표지`;
  image.addEventListener("error", () => {
    image.hidden = true;
    placeholder.hidden = false;
  }, { once: true });
}

function renderBook(book, detailMode = false) {
  const fragment = el("bookTemplate").content.cloneNode(true);
  const card = fragment.querySelector(".book-card");
  if (detailMode) card.classList.add("detail-card");

  setupCover(fragment, book);

  fragment.querySelector(".school-badge").textContent =
    [gradeLabel(book), book.subject].filter(Boolean).join(" · ");

  const status = materialStatus(book);
  const statusEl = fragment.querySelector(".status-badge");
  statusEl.textContent = labels[status] || status;
  statusEl.classList.add(status);

  const titleEl = fragment.querySelector(".book-title");
  if (detailMode) {
    titleEl.textContent = book.title;
  } else {
    const titleLink = document.createElement("a");
    titleLink.href = bookDetailUrl(book);
    titleLink.textContent = book.title;
    titleEl.append(titleLink);
  }

  fragment.querySelector(".book-meta").textContent =
    [book.publisher, book.brand, gradeLabel(book), book.subject, book.semester ? book.semester + "학기" : null]
      .filter(Boolean).join(" · ");
  fragment.querySelector(".book-submeta").textContent =
    [book.curriculum, book.edition_year ? book.edition_year + "년판" : null, book.isbn ? "ISBN " + book.isbn : null]
      .filter(Boolean).join(" · ");

  const intro = fragment.querySelector(".book-intro");
  const availableMaterials = (book.materials || []).map(material => material.title).filter(Boolean);
  intro.textContent = book.summary || [
    `${book.publisher} ${book.brand || ""} ${gradeLabel(book)} ${book.subject} 교재입니다.`.replace(/\s+/g, " ").trim(),
    availableMaterials.length ? `${availableMaterials.join(", ")} 등 공식 학습자료를 이 페이지에서 확인할 수 있습니다.` : ""
  ].filter(Boolean).join(" ");
  intro.hidden = !detailMode;

  const materials = fragment.querySelector(".materials");
  for (const material of book.materials || []) {
    const loginRequired = material.access === "login_required";
    const best = loginRequired
      ? (material.resource_page || book.official_page)
      : (material.direct_url || material.resource_page || book.official_page);

    const buttonLabel = loginRequired
      ? "출판사에서 로그인 후 다운로드"
      : (material.title || "공식 자료 보기");

    const primary = material.type === "answer";
    const link = detailMode
      ? createMaterialLink(buttonLabel, best, material.type, primary)
      : createPreviewMaterialBadge(buttonLabel, material.type, primary, book);
    if (link) materials.append(link);
  }

  for (const course of book.courses || []) {
    const teacher = course.teacher ? ` · ${course.teacher}` : "";
    if (detailMode) {
      if (!course.course_url) continue;
      const courseLink = createMaterialLink(`인강${teacher}`, course.course_url, "course", false);
      if (courseLink) {
        courseLink.classList.add("course-link");
        courseLink.title = course.title || "관련 인강";
        materials.append(courseLink);
      }
    } else if (course.course_url) {
      const courseLink = createPreviewMaterialBadge(`인강${teacher}`, "course", false, book);
      courseLink.classList.add("course-link");
      materials.append(courseLink);
    }
  }

  const secondary = fragment.querySelector(".book-secondary-links");
  if (detailMode) {
    if (book.official_page) {
      const official = document.createElement("a");
      official.href = book.official_page;
      official.target = "_blank";
      official.rel = "noopener noreferrer";
      official.className = "secondary-link";
      official.textContent = "출판사 공식 교재 안내";
      secondary.append(official);
    }
    if (book.post_url) {
      const post = document.createElement("a");
      post.href = book.post_url;
      post.target = "_blank";
      post.rel = "noopener noreferrer";
      post.className = "secondary-link";
      post.textContent = "관련 티스토리 글";
      secondary.append(post);
    }
    secondary.hidden = !secondary.children.length;
  }

  const hint = fragment.querySelector(".official-hint");
  hint.textContent = detailMode
    ? "정답·정오표·MP3 버튼은 검증된 직접 파일 주소가 있으면 그 주소를, 없으면 출판사의 해당 자료 페이지를 엽니다."
    : "교재명 또는 자료 뱃지를 누르면 이 사이트의 교재 상세 페이지가 열립니다.";

  return fragment;
}

function getFilteredBooks() {
  const filters = effectiveFilters();
  const query = state.scope.book ? "" : el("searchInput").value;
  return state.books.filter(book => {
    if (!matchesFilters(book, filters)) return false;
    return matchesSearch(book, query);
  });
}

function isDetailMode() {
  return Boolean(state.scope.book || selectValue("bookFilter"));
}

function applyFilters() {
  const filtered = getFilteredBooks();
  const detailMode = isDetailMode();
  const results = el("results");

  el("resultCount").textContent = filtered.length;
  results.innerHTML = "";
  results.classList.toggle("detail-view", detailMode);
  results.classList.toggle("cover-view", !detailMode && state.view === "cover");
  results.classList.toggle("list-view", detailMode || state.view === "list");

  const visible = detailMode ? filtered : filtered.slice(0, state.visibleCount);

  if (!visible.length) {
    results.innerHTML = '<div class="empty">조건에 맞는 교재가 없습니다.</div>';
  } else {
    visible.forEach(book => results.append(renderBook(book, detailMode)));
  }

  const more = el("loadMoreButton");
  more.hidden = detailMode || visible.length >= filtered.length;
  if (!more.hidden) {
    more.textContent = `${Math.min(PAGE_SIZE, filtered.length - visible.length)}개 더 보기`;
  }

  if (state.scope.book && filtered[0]) {
    el("scopeTitle").textContent = filtered[0].title;
    document.title = `${filtered[0].title} 자료 | 답지 통합 검색`;
  }
}

function resetVisible() {
  state.visibleCount = PAGE_SIZE;
}

function setView(view) {
  state.view = view;
  el("listViewButton").classList.toggle("is-active", view === "list");
  el("coverViewButton").classList.toggle("is-active", view === "cover");
  el("listViewButton").setAttribute("aria-pressed", String(view === "list"));
  el("coverViewButton").setAttribute("aria-pressed", String(view === "cover"));
  applyFilters();
}

function hideFixedControls() {
  const mappings = [
    ["publisher", "publisherField"],
    ["subject", "subjectField"],
    ["grade", "gradeField"],
    ["book", "bookField"]
  ];
  for (const [key, fieldId] of mappings) {
    if (state.scope[key]) el(fieldId).hidden = true;
  }

  if (state.scope.book) {
    el("filters").hidden = true;
    el("toolbar").hidden = true;
    el("loadMoreButton").hidden = true;
  }

  if (state.scope.embed) {
    document.body.classList.add("embed-mode");
    el("hero").hidden = true;
    el("scopeHeading").hidden = false;
    el("viewSwitch").hidden = true;
  }

  const visibleFields = [...document.querySelectorAll(".filter-field")].filter(node => !node.hidden);
  if (!visibleFields.length && !state.scope.book) {
    el("resetButton").hidden = true;
  }
}

function updateScopeHeading() {
  if (!state.scope.embed || state.scope.book) return;
  const parts = [];
  if (state.scope.publisher) parts.push(state.scope.publisher);
  if (state.scope.grade) {
    const book = state.books.find(item => scopeMatches(item));
    if (book) parts.push(gradeLabel(book));
  }
  if (state.scope.subject) parts.push(state.scope.subject);
  el("scopeTitle").textContent = parts.length ? `${parts.join(" ")} 교재 자료` : "교재 자료";
}

function resetFilters() {
  if (!state.scope.publisher) el("publisherFilter").value = "";
  if (!state.scope.subject) el("subjectFilter").value = "";
  if (!state.scope.grade) el("gradeFilter").value = "";
  if (!state.scope.book) el("bookFilter").value = "";
  el("searchInput").value = "";
  resetVisible();
  updateDependentSelects();
  applyFilters();
}

function bindEvents() {
  el("searchInput").addEventListener("input", () => {
    resetVisible();
    applyFilters();
  });

  el("publisherFilter").addEventListener("change", () => {
    if (!state.scope.subject) el("subjectFilter").value = "";
    if (!state.scope.grade) el("gradeFilter").value = "";
    if (!state.scope.book) el("bookFilter").value = "";
    resetVisible();
    updateDependentSelects();
    applyFilters();
  });

  el("subjectFilter").addEventListener("change", () => {
    if (!state.scope.grade) el("gradeFilter").value = "";
    if (!state.scope.book) el("bookFilter").value = "";
    resetVisible();
    updateDependentSelects();
    applyFilters();
  });

  el("gradeFilter").addEventListener("change", () => {
    if (!state.scope.book) el("bookFilter").value = "";
    resetVisible();
    updateDependentSelects();
    applyFilters();
  });

  el("bookFilter").addEventListener("change", () => {
    const selected = el("bookFilter").value;
    if (selected && !state.scope.book) {
      const book = state.books.find(item => item.book_id === selected);
      if (book) {
        navigateToBook(book);
        return;
      }
    }
    resetVisible();
    applyFilters();
  });

  el("resetButton").addEventListener("click", resetFilters);
  el("listViewButton").addEventListener("click", () => setView("list"));
  el("coverViewButton").addEventListener("click", () => setView("cover"));
  el("loadMoreButton").addEventListener("click", () => {
    state.visibleCount += PAGE_SIZE;
    applyFilters();
  });
}

async function init() {
  readScope();
  try {
    const response = await fetch("data/catalog.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.books = data.books || [];
    state.meta = data.meta || {};

    updateDependentSelects();
    hideFixedControls();
    updateScopeHeading();

    el("updatedAt").textContent = state.meta.generated_at ? `데이터 기준 ${state.meta.generated_at}` : "";
    bindEvents();
    applyFilters();
  } catch (error) {
    el("results").innerHTML = `<div class="empty">데이터를 불러오지 못했습니다: ${error.message}</div>`;
  }
}

document.addEventListener("DOMContentLoaded", init);
