"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "../assets/app.js"), "utf8");

async function run(bookId, responses, expectedRequests, reject = false) {
  const requests = [];
  const context = vm.createContext({
    document: { addEventListener() {} },
    fetch: async url => {
      requests.push(url);
      assert.ok(Object.hasOwn(responses, url), `Unexpected request: ${url}`);
      const [status, body] = responses[url];
      return { status, ok: status === 200, json: async () => body };
    },
  });
  vm.runInContext(script, context);
  context.requestedBook = bookId;
  const promise = vm.runInContext("loadCatalog(requestedBook)", context);
  const result = reject ? await assert.rejects(promise) : await promise;
  assert.deepEqual(requests, expectedRequests);
  return result;
}

(async () => {
  const descriptor = [200, { delivery_version: 1, meta: { generated_at: "today" } }];
  const single = [200, { books: [{ book_id: "stable-book" }] }];
  const result = await run("stable-book", { "data/site.json": descriptor, "data/books/stable-book.json": single }, ["data/site.json", "data/books/stable-book.json"]);
  assert.equal(result.books.length, 1);
  const missing = await run("missing", { "data/site.json": descriptor, "data/books/missing.json": [404] }, ["data/site.json", "data/books/missing.json"]);
  assert.equal(missing.books.length, 0);
  await run("../private", { "data/site.json": descriptor }, ["data/site.json"]);
  await run("stable-book", { "data/site.json": [503] }, ["data/site.json"], true);
  await run("stable-book", { "data/site.json": descriptor, "data/books/stable-book.json": [503] }, ["data/site.json", "data/books/stable-book.json"], true);
  await run("stable-book", { "data/site.json": descriptor, "data/books/stable-book.json": [200, { books: [{ book_id: "other-edition" }] }] }, ["data/site.json", "data/books/stable-book.json"], true);
  await run("stable-book", { "data/site.json": [404], "data/catalog.json": single }, ["data/site.json", "data/catalog.json"]);
  await run("", { "data/site.json": descriptor, "data/catalog.json": single }, ["data/site.json", "data/catalog.json"]);
  console.log("Catalog delivery passed: one-book requests, missing IDs, server failures, mismatches, legacy and search.");
})().catch(error => { console.error(error); process.exitCode = 1; });
