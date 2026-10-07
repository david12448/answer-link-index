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
  constructor(level = "") {
    this.dataset = { level };
    this.hidden = false;
    this.attributes = {};
    this.classList = { toggle() {} };
    this.textContent = "";
    this.type = "button";
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
}

const buttons = ["", "elementary", "middle", "high"].map(level => new FakeButton(level));
class FakeContainer {
  constructor() { this.children = []; }
  set innerHTML(value) { this.children = []; }
  append(node) { this.children.push(node); }
  addEventListener() {}
}
const seriesButtons = new FakeContainer();
const elements = {
  publisherFilter: new FakeSelect(),
  subjectFilter: new FakeSelect(),
  gradeFilter: new FakeSelect(),
  bookFilter: new FakeSelect(),
  searchInput: { value: "" },
  schoolShortcuts: {
    hidden: true,
    querySelectorAll() { return buttons; },
  },
  seriesShortcuts: { hidden: true },
  seriesShortcutButtons: seriesButtons,
};
const document = {
  getElementById(id) {
    if (!elements[id]) throw new Error("Missing test element: " + id);
    return elements[id];
  },
  createElement(tag) {
    if (tag === "option") return { value: "", textContent: "" };
    if (tag === "button") return new FakeButton();
    throw new Error("Unexpected test DOM node: " + tag);
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
elements.searchInput.value = "만점왕";
assert.equal(evaluate("getFilteredBooks().length"), 1, "Embedded list pages use the persistent top search");
elements.searchInput.value = "";

elements.searchInput.value = "";
evaluate(`state.scope = {publisher:"EBS", level:"elementary", brand:"", subject:"", grade:"", book:"", embed:true}; state.schoolLevel=""; state.books = [
  {book_id:"scope-a", title:"초등 수학", school_level:"elementary", grade:3, publisher:"EBS", subject:"수학", materials:[]},
  {book_id:"scope-b", title:"중등 수학", school_level:"middle", grade:1, publisher:"EBS", subject:"수학", materials:[]}
];`);
assert.equal(evaluate("getFilteredBooks().length"), 1, "URL level scope filters to one school level");
assert.equal(evaluate("getFilteredBooks()[0].book_id"), "scope-a");

evaluate(`state.scope = {publisher:"EBS", level:"elementary", brand:"만점왕", subject:"", grade:"", book:"", embed:true};
state.books = [
  {book_id:"brand-a", title:"만점왕 수학 3-1", brand:"만점왕", school_level:"elementary", grade:3, publisher:"EBS", subject:"수학", materials:[]},
  {book_id:"brand-b", title:"만점왕 수학 플러스 3-1", brand:"만점왕 수학 플러스", school_level:"elementary", grade:3, publisher:"EBS", subject:"수학", materials:[]}
];`);
assert.equal(evaluate("getFilteredBooks().length"), 1, "URL brand scope filters to one series");
assert.equal(evaluate("getFilteredBooks()[0].book_id"), "brand-a");

assert.equal(evaluate(`shouldShowMaterial({type:"errata", availability:"available", status:"ok"})`), true);
assert.equal(evaluate(`shouldShowMaterial({type:"errata", availability:"unavailable", status:"needs_review"})`), false);
assert.equal(evaluate(`shouldShowMaterial({type:"errata", availability:"unknown", status:"needs_review"})`), false);
assert.equal(evaluate(`shouldShowMaterial({type:"answer", availability:"unknown", status:"needs_review"})`), true);
assert.equal(evaluate(`shouldShowMaterial({type:"mp3", availability:"available", status:"ok"})`), true);
assert.equal(evaluate(`shouldShowMaterial({type:"mp3", availability:"unknown", status:"needs_review"})`), false);
assert.equal(evaluate(`shouldShowMaterial({type:"additional", availability:"unknown", status:"needs_review"})`), false);


evaluate(`state.scope = {publisher:"", level:"", brand:"", subject:"", grade:"", book:"", embed:false};
state.schoolLevel = "";
state.brand = "";
state.books = Array.from({length:2000}, (_,i) => ({
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
evaluate(`state.scope = {publisher:"", level:"", brand:"", subject:"", grade:"", book:"", embed:false};
state.schoolLevel = "";
state.brand = "";
state.books = ${JSON.stringify(actualCatalog.books)};
`);
elements.searchInput.value = "";
for (const id of ["publisherFilter", "subjectFilter", "gradeFilter", "bookFilter"]) {
  elements[id].value = "";
}
evaluate("updateDependentSelects(); updateSchoolShortcuts(); updateSeriesShortcuts();");
assert.equal(elements.seriesShortcuts.hidden, true, "Initial catalog does not show series shortcuts");
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
evaluate(`state.schoolLevel = "elementary"; updateDependentSelects(); updateSchoolShortcuts(); updateSeriesShortcuts();`);
assert.equal(elements.seriesShortcuts.hidden, true, "School level alone does not clutter the page with series");
assert.equal(
  evaluate("getFilteredBooks().length"),
  elementaryCount,
  "Actual catalog school-level shortcut matches elementary count"
);

elements.publisherFilter.value = "EBS";
evaluate("updateDependentSelects(); updateSeriesShortcuts();");
assert.equal(elements.seriesShortcuts.hidden, false, "Large EBS elementary list shows series shortcuts");
assert.ok(
  seriesButtons.children.some(button => button.dataset.brand === "만점왕"),
  "Series shortcuts include 만점왕"
);
assert.ok(
  seriesButtons.children.some(button => button.dataset.brand === "만점왕 수학 플러스"),
  "Series shortcuts include 만점왕 수학 플러스"
);

const expectedPlus = actualCatalog.books.filter(book =>
  book.publisher === "EBS" &&
  book.school_level === "elementary" &&
  book.brand === "만점왕 수학 플러스"
).length;
evaluate(`state.brand = "만점왕 수학 플러스"; updateDependentSelects();`);
assert.equal(
  evaluate("getFilteredBooks().length"),
  expectedPlus,
  "Series shortcut filters the catalog without changing the four main selects"
);
evaluate(`state.brand = "";`);

elements.searchInput.value = "만점왕 수학 플러스";
assert.ok(
  evaluate("getFilteredBooks().length") >= 10,
  "Actual catalog search finds the 만점왕 수학 플러스 series"
);
elements.searchInput.value = "";

console.log("UI filter tests passed: school levels, series shortcuts, grade order, search, select cap, optional badges, actual catalog, single-book scope.");
