"""Check that new internal fields cannot silently leak into the public bundle."""
import json
import tempfile
import unittest
from pathlib import Path
from build_public_site import ROOT, build, public_catalog


class PublicExportTests(unittest.TestCase):
    def test_internal_fields_and_unknown_resources_are_removed(self):
        source = {"meta": {"generated_at": "2026-10-08", "private_notes": "secret"},
                  "books": [{"book_id": "stable", "publisher_book_id": "internal",
                             "future_evidence": "secret", "materials": [
                                 {"type": "answer", "direct_url": "https://example.com/a.pdf", "publisher_file_id": "internal"},
                                 {"type": "errata", "availability": "unknown"},
                                 {"type": "mp3", "availability": "available", "resource_page": "https://example.com/mp3"}],
                             "courses": [{"title": "Course", "course_url": "https://example.com/course", "source_course_id": "internal"}]}]}
        result = public_catalog(source)
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("internal", json.dumps(result))
        self.assertEqual([m["type"] for m in result["books"][0]["materials"]], ["answer", "mp3"])
        self.assertEqual(result["books"][0]["book_id"], "stable")

    def test_real_bundle_and_stable_links(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            build(output)
            files = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
            source = json.loads((ROOT / "data/catalog.json").read_text())
            public = json.loads((output / "data/catalog.json").read_text())
            expected = {"index.html", "assets/app.js", "assets/style.css", "data/catalog.json", "data/site.json"}
            expected.update(f"data/books/{b['book_id']}.json" for b in public["books"])
            self.assertEqual(files, expected)
            self.assertEqual([b["book_id"] for b in source["books"]], [b["book_id"] for b in public["books"]])
            for original, exported in zip(source["books"], public["books"]):
                single = json.loads((output / "data/books" / f"{exported['book_id']}.json").read_text())
                self.assertEqual(single["books"], [exported])
                self.assertEqual(original.get("cover_image_url"), exported.get("cover_image_url"))
                for material in exported["materials"]:
                    self.assertTrue(any(all(old.get(k) == v for k, v in material.items()) for old in original["materials"]))
            with self.assertRaises(FileExistsError):
                build(output)


if __name__ == "__main__":
    unittest.main()
