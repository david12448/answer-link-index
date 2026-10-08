"""Export only the files and fields needed by the public textbook UI.

This boundary prepares private-source operation; it does not hide a public git history.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK_FIELDS = (
    "book_id", "publisher", "brand", "title", "aliases", "school_level", "grade",
    "semester", "subject", "book_type", "curriculum", "edition_year", "isbn",
    "official_page", "cover_image_url", "post_url", "summary",
)
MATERIAL_FIELDS = ("type", "title", "resource_page", "direct_url", "access", "status", "availability")


def select(source, fields):
    return {key: source[key] for key in fields if key in source}


def public_catalog(source):
    books = []
    for book in source["books"]:
        item = select(book, BOOK_FIELDS)
        item["materials"] = [
            select(material, MATERIAL_FIELDS)
            for material in book.get("materials", [])
            if material.get("type") not in {"errata", "mp3", "additional"}
            or material.get("availability") == "available"
        ]
        item["courses"] = [select(course, ("title", "teacher", "course_url"))
                           for course in book.get("courses", []) if course.get("course_url")]
        if book.get("publisher_help"):
            item["publisher_help"] = select(book["publisher_help"], ("mode", "url", "label", "note"))
        books.append(item)
    return {"meta": select(source.get("meta", {}), ("generated_at",)), "books": books}


def build(destination):
    source = json.loads((ROOT / "data/catalog.json").read_text())
    public = public_catalog(source)
    ids = [book["book_id"] for book in public["books"]]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", book_id) for book_id in ids):
        raise ValueError("Public book IDs must be unique safe filename slugs")
    destination = Path(destination).resolve()
    # Never clear or overwrite an existing directory (especially the source checkout).
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "assets").mkdir()
    (destination / "data").mkdir()
    (destination / "data/books").mkdir()
    for filename in ("index.html", "assets/app.js", "assets/style.css"):
        shutil.copyfile(ROOT / filename, destination / filename)
    (destination / "data/catalog.json").write_text(
        json.dumps(public, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    (destination / "data/site.json").write_text(json.dumps({"delivery_version": 1, "meta": public["meta"]}) + "\n")
    for book in public["books"]:
        (destination / "data/books" / f"{book['book_id']}.json").write_text(
            json.dumps({"meta": public["meta"], "books": [book]}, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
    print(f"Public site: {destination} ({len(source['books'])} books)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "dist/public-site"))
    build(parser.parse_args().output)
