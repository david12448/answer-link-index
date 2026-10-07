"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

class FakeSelect {
  constructor() {
    this.options = [];
    this.value = "";
  }
  set innerHTML(value) {
    this.options = [];
    this.value = "";
  }
  append(option) {
    this.options.push(option);
  }
}

class FakeButton {
  constructor(level) {
    this.dataset = { level };
    this.hidden = false;
    this.attributes = {};
    this.classList = { toggle() {} };
    this.textContent = "";
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
}

const buttons = ["", "elementary", "middle", "high"].map(level => new FakeButton(level));
const elements = {
  publisherFilter: new FakeSelect(),
  subjectFilter: new FakeSelect(),
  gradeFilter: new FakeSelect(),
  bookFilter: new FakeSelect(),
  searchInput: { value: "" },
  embedSearchInput: { value: "" },
  schoolShortcuts: {
    hidden: true,
    querySelectorAll() { return buttons; },
  },
};
const document = {
  getElementById(id) {
    if (!elements[id]) throw new Error("Missing test element: " + id);
    return elements[id];
  },
  createElement(tag) {
    if (tag !== "option") throw new Error("Unexpected test DOM node: " + tag);
    return { value: "", textContent: "" };
  },
  addEventListener() {},
};
const context = vm.createContext({ document, window: {location: {href:"https://example.com/index.html"}}, URL });
const script = fs.readFileSync(path.join(__dirname, "../assets/app.js"), "utf8");
vm.runInContext(script, context);
const evaluate = code => vm.runInContext(code, context);

evaluate(`state.books = [
  {book_id:"a", title:"만점왕 수학 3-1", school_level:"elementary", grade:3, publisher:"EBS", subject:"수학", brand:"만점왕", materials:[]},
  {book_id:"b", title:"뉴런 수학1(상)", school_level:"middle", grade:1, publisher:"EBS", subject:"수학", brand:"중학 뉴런", materials:[]},
  {book_id:"c", title:"수능특강 수학", school_level:"high", grade:3, publisher:"EBS", subject:"수학", brand:"수능특강", materials:[]}
]; updateDependentSelects(); updateSchoolShortcuts();`);
assert.equal(elements.schoolShortcuts.hidden, false, "Mixed school levels show shortcuts");
assert.deepEqual(
  elements.gradeFilter.options.slice(1).map(x => x.textContent),
  ["초3", "중1", "고3"],
  "School grades should sort elementary, middle, high",
);
assert.equal(evaluate("getFilteredBooks().length"), 3);

evaluate(`state.schoolLevel = "middle"; updateDependentSelects(); updateSchoolShortcuts();`);
assert.equal(evaluate("getFilteredBooks().length"), 1);
assert.equal(elements.gradeFilter.options[1].textContent, "중1");
assert.equal(buttons[2].attributes["aria-pressed"], "true");

elements.searchInput.value = "뉴런";
assert.equal(evaluate("getFilteredBooks().length"), 1);
elements.searchInput.value = "만점왕";
assert.equal(evaluate("getFilteredBooks().length"), 0);

evaluate(`state.schoolLevel = ""; state.scope.embed = true;`);
elements.embedSearchInput.value = "만점왕";
assert.equal(evaluate("getFilteredBooks().length"), 1, "Embedded pages use their own search");
elements.embedSearchInput.value = "";

elements.searchInput.value = "";
evaluate(`state.scope = {publisher:"EBS", level:"elementary", subject:"", grade:"", book:"", embed:true}; state.schoolLevel=""; state.books = [
  {book_id:"scope-a", title:"초등 수학", school_level:"elementary", grade:3, publisher:"EBS", subject:"수학", materials:[]},
  {book_id:"scope-b", title:"중등 수학", school_level:"middle", grade:1, publisher:"EBS", subject:"수학", materials:[]}
];`);
elements.embedSearchInput.value = "";
assert.equal(evaluate("getFilteredBooks().length"), 1, "URL level scope filters to one school level");
assert.equal(evaluate("getFilteredBooks()[0].book_id"), "scope-a");

assert.equal(evaluate(`shouldShowMaterial({type:"errata", availability:"available", status:"ok"})`), true);
assert.equal(evaluate(`shouldShowMaterial({type:"errata", availability:"unavailable", status:"needs_review"})`), false);
assert.equal(evaluate(`shouldShowMaterial({type:"errata", availability:"unknown", status:"needs_review"})`), false);
assert.equal(evaluate(`shouldShowMaterial({type:"answer", availability:"unknown", status:"needs_review"})`), true);
assert.equal(evaluate(`shouldShowMaterial({type:"mp3", availability:"available", status:"ok"})`), true);
assert.equal(evaluate(`shouldShowMaterial({type:"mp3", availability:"unknown", status:"needs_review"})`), false);
assert.equal(evaluate(`shouldShowMaterial({type:"additional", availability:"unknown", status:"needs_review"})`), false);


evaluate(`state.scope.embed = false; state.books = Array.from({length:2000}, (_,i) => ({
  book_id:"bulk-"+i, title:"교재 "+String(i).padStart(3, "0"),
  school_level:"elementary", grade:3, publisher:"EBS", subject:"수학", materials:[]
})); updateDependentSelects();`);
assert.equal(elements.bookFilter.options.length, 81, "Limit selector to 80 items with 2000 books");
assert.match(elements.bookFilter.options[0].textContent, /검색으로 좁히기/);

elements.searchInput.value = "1999";
evaluate("updateDependentSelects();");
assert.equal(elements.bookFilter.options.length, 2, "Typing filters the big book dropdown");
assert.equal(elements.bookFilter.options[1].value, "bulk-1999");

evaluate(`state.scope.book = "bulk-1999"; state.scope.embed = true;`);
assert.equal(evaluate("getFilteredBooks().length"), 1, "Fixed one-book Tistory view remains available");

const actualCatalog = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../data/catalog.json"), "utf8")
);
evaluate(`state.scope = {publisher:"", level:"", subject:"", grade:"", book:"", embed:false};
state.schoolLevel = "";
state.books = ${JSON.stringify(actualCatalog.books)};
`);
elements.searchInput.value = "";
elements.embedSearchInput.value = "";
evaluate("updateDependentSelects(); updateSchoolShortcuts();");
assert.equal(
  evaluate("getFilteredBooks().length"),
  actualCatalog.books.length,
  "Actual catalog should render every book with no filters"
);
assert.ok(
  elements.bookFilter.options.length <= 81,
  "Actual 100+ book catalog keeps the selector capped"
);

const elementaryCount = actualCatalog.books.filter(book => book.school_level === "elementary").length;
evaluate(`state.schoolLevel = "elementary"; updateDependentSelects(); updateSchoolShortcuts();`);
assert.equal(
  evaluate("getFilteredBooks().length"),
  elementaryCount,
  "Actual catalog school-level shortcut matches elementary count"
);

elements.searchInput.value = "만점왕 수학 플러스";
assert.ok(
  evaluate("getFilteredBooks().length") >= 10,
  "Actual catalog search finds the 만점왕 수학 플러스 series"
);
elements.searchInput.value = "";

console.log("UI filter tests passed: school levels, grade order, search, select cap, optional badges, actual catalog, single-book scope.");
