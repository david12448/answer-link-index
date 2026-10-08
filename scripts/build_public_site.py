"""Export only the files and fields needed by the public textbook UI.

This boundary prepares private-source operation; it does not hide a public git history.
"""
import argparse
import json
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
    destination = Path(destination).resolve()
    # Never clear or overwrite an existing directory (especially the source checkout).
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "assets").mkdir()
    (destination / "data").mkdir()
    for filename in ("index.html", "assets/app.js", "assets/style.css"):
        shutil.copyfile(ROOT / filename, destination / filename)
    source = json.loads((ROOT / "data/catalog.json").read_text())
    (destination / "data/catalog.json").write_text(
        json.dumps(public_catalog(source), ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    print(f"Public site: {destination} ({len(source['books'])} books)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "dist/public-site"))
    build(parser.parse_args().output)
