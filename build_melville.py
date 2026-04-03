#!/usr/bin/env python3
"""Build Contabulate JSON data files for Melville's prose fiction corpus."""

import json
import os
import re
from collections import Counter, defaultdict


CATALOG_PATH = "CATALOG.json"
OUT_DIR = os.path.join("docs", "data")
LINES_DIR = os.path.join("docs", "lines")

START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK"
END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK"

WORK_ABBRS = {
    "typee": "TYPE",
    "omoo": "OMOO",
    "mardi": "MARD",
    "redburn": "REDB",
    "white-jacket": "WJ",
    "moby-dick": "MD",
    "pierre": "PIER",
    "bartleby": "BART",
    "israel-potter": "IP",
    "confidence-man": "CM",
    "billy-budd": "BB",
}

ROMAN_VALUES = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}

WORD_NUMBERS = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
    "TEN": 10,
    "ELEVEN": 11,
    "TWELVE": 12,
    "THIRTEEN": 13,
    "FOURTEEN": 14,
    "FIFTEEN": 15,
    "SIXTEEN": 16,
    "SEVENTEEN": 17,
    "EIGHTEEN": 18,
    "NINETEEN": 19,
    "TWENTY": 20,
    "TWENTY-ONE": 21,
    "TWENTY-TWO": 22,
    "TWENTY-THREE": 23,
    "TWENTY-FOUR": 24,
    "TWENTY-FIVE": 25,
    "TWENTY-SIX": 26,
    "TWENTY-SEVEN": 27,
    "TWENTY-EIGHT": 28,
    "TWENTY-NINE": 29,
    "THIRTY": 30,
    "THIRTY-ONE": 31,
    "THIRTY-TWO": 32,
    "THIRTY-THREE": 33,
    "THIRTY-FOUR": 34,
}


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def read_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def strip_gutenberg(text):
    start = text.find(START_MARKER)
    if start != -1:
        start = text.find("\n", start)
        start = len(text) if start == -1 else start + 1
    else:
        start = 0

    end = text.find(END_MARKER)
    if end == -1:
        end = len(text)

    return text[start:end].strip()


def roman_to_int(value):
    total = 0
    prev = 0
    for ch in reversed(value.upper()):
        current = ROMAN_VALUES.get(ch)
        if current is None:
            raise ValueError(f"Invalid Roman numeral: {value}")
        if current < prev:
            total -= current
        else:
            total += current
            prev = current
    return total


def chapter_number_from_token(token):
    token = token.strip().strip(".").upper()
    if token.isdigit():
        return int(token)
    if token in WORD_NUMBERS:
        return WORD_NUMBERS[token]
    if re.fullmatch(r"[IVXLCDM]+", token):
        return roman_to_int(token)
    raise ValueError(f"Unsupported chapter token: {token}")


def clean_paragraph(text):
    return re.sub(r"\s+", " ", text).strip()


def paragraphs_from_text(text):
    return [clean_paragraph(p) for p in re.split(r"\n\s*\n", text) if clean_paragraph(p)]


def tokenize(text):
    return re.findall(r"[a-zA-Z']+(?:-[a-zA-Z']+)*", text.lower())


def build_ngrams(tokens, n):
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def next_nonempty(lines, start_idx):
    for idx in range(start_idx, len(lines)):
        if lines[idx].strip():
            return idx, lines[idx].strip()
    return None, None


def collect_title_lines(lines, start_idx, end_idx):
    title_lines = []
    idx = start_idx
    while idx < end_idx:
        raw = lines[idx]
        line = raw.strip()
        if not line:
            break
        if not looks_like_title(line):
            break
        title_lines.append(line.rstrip("."))
        idx += 1
    return " ".join(title_lines).strip(), idx


def looks_like_title(line):
    if not line:
        return False
    if re.fullmatch(r"[IVXLCDM]+\.?", line):
        return False
    if re.match(r"^(CHAPTER|Chapter|BOOK|PART)\b", line):
        return False
    letters = re.findall(r"[A-Za-z]", line)
    if not letters:
        return False
    uppercase_letters = [ch for ch in letters if ch.isupper()]
    return len(uppercase_letters) / len(letters) >= 0.7


def normalize_starts(starts):
    one_positions = [idx for idx, item in enumerate(starts) if item[1] == 1]
    if one_positions:
        starts = starts[one_positions[-1]:]
    return starts


def build_sections_from_starts(lines, starts):
    starts = normalize_starts(starts)
    sections = []
    for idx, item in enumerate(starts):
        if len(item) == 4:
            line_idx, number, label_prefix, inline_title = item
        else:
            line_idx, number, label_prefix = item
            inline_title = ""
        end_idx = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        body_start = line_idx + 1
        title = inline_title.strip().rstrip(".")
        title_idx, title_line = next_nonempty(lines, body_start)
        if not title and title_idx is not None and title_idx < end_idx and looks_like_title(title_line):
            title, body_start = collect_title_lines(lines, title_idx, end_idx)
        body = "\n".join(lines[body_start:end_idx]).strip()
        paragraphs = paragraphs_from_text(body)
        if not paragraphs:
            continue
        label = f"{label_prefix} {number}"
        sections.append(
            {
                "number": number,
                "label": label,
                "title": title,
                "paragraphs": paragraphs,
            }
        )
    return sections


def parse_standard_chapters(text):
    lines = text.splitlines()
    starts = []
    patterns = [
        (re.compile(r"^CHAPTER\s+([IVXLCDM]+|\d+)\.\s*$"), "Chapter"),
        (re.compile(r"^CHAPTER\s+([IVXLCDM]+|\d+)\.\s+(.+?)\s*$"), "Chapter"),
        (re.compile(r"^CHAPTER\s+([IVXLCDM]+|\d+)\s+[\.\u2014-]\s+(.+?)\s*$"), "Chapter"),
        (re.compile(r"^Chapter\s+([IVXLCDM]+|\d+)\s*$"), "Chapter"),
        (re.compile(r"^Chapter\s+([IVXLCDM]+|\d+)\s+(.+?)\s*$"), "Chapter"),
    ]
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        for pattern, label_prefix in patterns:
            match = pattern.match(line)
            if not match:
                continue
            number = chapter_number_from_token(match.group(1))
            inline_title = match.group(2).strip() if match.lastindex and match.lastindex > 1 else ""
            starts.append((idx, number, label_prefix, inline_title))
            break
    return build_sections_from_starts(lines, starts)


def parse_typee_chapters(text):
    lines = text.splitlines()
    starts = []
    pattern = re.compile(r"^CHAPTER\s+([A-Z-]+)\s*$")
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        match = pattern.match(line)
        if not match:
            continue
        token = match.group(1)
        if token not in WORD_NUMBERS:
            continue
        starts.append((idx, WORD_NUMBERS[token], "Chapter", ""))
    return build_sections_from_starts(lines, starts)


def parse_pierre_books(text):
    lines = text.splitlines()
    starts = []
    pattern = re.compile(r"^BOOK\s+([IVXLCDM]+)\.\s*(.*?)\s*$")
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        match = pattern.match(line)
        if not match:
            continue
        number = roman_to_int(match.group(1))
        starts.append((idx, number, "Book", match.group(2)))
    return build_sections_from_starts(lines, starts)


def extract_billy_budd(text):
    start_match = re.search(r"(?m)^\s*BILLY BUDD, FORETOPMAN\s*$", text)
    if not start_match:
        raise ValueError("Could not find Billy Budd start marker")
    end_match = re.search(r"(?m)^\s*DANIEL ORME\s*$", text[start_match.end():])
    if not end_match:
        raise ValueError("Could not find Billy Budd end marker")
    return text[start_match.start():start_match.end() + end_match.start()].strip()


def parse_billy_budd(text):
    lines = text.splitlines()
    starts = []
    body_started = False
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line == "BILLY BUDD, FORETOPMAN":
            body_started = True
            continue
        if not body_started:
            continue
        if re.fullmatch(r"[IVXLCDM]+", line):
            number = roman_to_int(line)
            starts.append((idx, number, "Chapter", ""))
    return build_sections_from_starts(lines, starts)


def parse_work_sections(work):
    work_id = work["id"]
    if work_id == "mardi":
        combined = []
        section_offset = 0
        for path in work["files"]:
            body = strip_gutenberg(read_file(path))
            sections = parse_standard_chapters(body)
            if not sections:
                raise ValueError(f"No chapters found in {path}")
            for section in sections:
                next_section = dict(section)
                next_section["number"] += section_offset
                next_section["label"] = f"Chapter {next_section['number']}"
                combined.append(next_section)
            section_offset = combined[-1]["number"]
        return combined
    if work_id == "bartleby":
        body = strip_gutenberg(read_file(work["file"]))
        return [{"number": 1, "label": "Chapter 1", "title": "", "paragraphs": paragraphs_from_text(body)}]
    if work_id == "billy-budd":
        body = strip_gutenberg(read_file(work["file"]))
        sections = parse_billy_budd(extract_billy_budd(body))
        if not sections:
            raise ValueError("No Billy Budd chapters found")
        return sections
    if work_id == "typee":
        body = strip_gutenberg(read_file(work["file"]))
        sections = parse_typee_chapters(body)
        if not sections:
            raise ValueError("No Typee chapters found")
        return sections
    if work_id == "pierre":
        body = strip_gutenberg(read_file(work["file"]))
        sections = parse_pierre_books(body)
        if not sections:
            raise ValueError("No Pierre book sections found")
        return sections

    body = strip_gutenberg(read_file(work["file"]))
    sections = parse_standard_chapters(body)
    if not sections:
        return [{"number": 1, "label": "Chapter 1", "title": "", "paragraphs": paragraphs_from_text(body)}]
    return sections


def dump_json(path, value):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))


def build_json_corpus(catalog):
    plays = []
    chunks = []
    lines = []
    tokens1 = defaultdict(list)
    tokens2 = defaultdict(list)
    tokens3 = defaultdict(list)
    per_work_stats = []

    total_words = 0
    total_paragraphs = 0
    unique_unigrams = set()
    unique_bigrams = set()
    unique_trigrams = set()

    scene_id = 0

    for play_id, work in enumerate(catalog, start=1):
        sections = parse_work_sections(work)
        if not sections:
            raise ValueError(f"No sections found for {work['title']}")

        play_abbr = WORK_ABBRS.get(work["id"], re.sub(r"[^A-Z]", "", work["title"].upper())[:6] or f"W{play_id}")
        play_location = f"{play_id:02d}.{play_abbr}"
        work_total_words = 0
        work_total_lines = 0

        for section in sections:
            section_num = section["number"]
            act_label = section["title"] or section["label"]

            for para_idx, para in enumerate(section["paragraphs"], start=1):
                scene_id += 1
                words = tokenize(para)
                unigram_counts = Counter(words)
                bigram_counts = Counter(build_ngrams(words, 2))
                trigram_counts = Counter(build_ngrams(words, 3))
                word_count = len(words)

                canonical_id = f"{play_abbr}.{section_num}.{para_idx}"
                location = f"{play_location}.{section_num:03d}.{para_idx:04d}"
                scene_label = f"\u00b6{para_idx}"

                chunks.append(
                    {
                        "scene_id": scene_id,
                        "canonical_id": canonical_id,
                        "location": location,
                        "play_id": play_id,
                        "play_title": work["title"],
                        "play_abbr": play_abbr,
                        "genre": work["genre"],
                        "act": section_num,
                        "scene": para_idx,
                        "heading": f"{act_label}, {scene_label}",
                        "total_words": word_count,
                        "unique_words": len(unigram_counts),
                        "num_speeches": 0,
                        "num_lines": 1,
                        "characters_present_count": 0,
                        "act_label": act_label,
                        "scene_label": scene_label,
                    }
                )
                lines.append(
                    {
                        "play_id": play_id,
                        "canonical_id": canonical_id,
                        "location": location,
                        "act": section_num,
                        "scene": para_idx,
                        "line_num": para_idx,
                        "speaker": "",
                        "text": para,
                        "act_label": act_label,
                        "scene_label": scene_label,
                    }
                )

                for token, count in unigram_counts.items():
                    tokens1[token].append([scene_id, count])
                for token, count in bigram_counts.items():
                    tokens2[token].append([scene_id, count])
                for token, count in trigram_counts.items():
                    tokens3[token].append([scene_id, count])

                unique_unigrams.update(unigram_counts)
                unique_bigrams.update(bigram_counts)
                unique_trigrams.update(trigram_counts)

                work_total_words += word_count
                work_total_lines += 1
                total_words += word_count
                total_paragraphs += 1

        plays.append(
            {
                "play_id": play_id,
                "location": play_location,
                "title": work["title"],
                "abbr": play_abbr,
                "genre": work["genre"],
                "first_performance_year": work["year"],
                "num_acts": len(sections),
                "num_scenes": work_total_lines,
                "num_speeches": 0,
                "total_words": work_total_words,
                "total_lines": work_total_lines,
            }
        )
        per_work_stats.append(
            {
                "title": work["title"],
                "year": work["year"],
                "chapters": len(sections),
                "paragraphs": work_total_lines,
                "words": work_total_words,
            }
        )

    return {
        "plays": plays,
        "chunks": chunks,
        "lines": lines,
        "tokens": dict(tokens1),
        "tokens2": dict(tokens2),
        "tokens3": dict(tokens3),
        "per_work_stats": per_work_stats,
        "totals": {
            "works": len(plays),
            "paragraphs": total_paragraphs,
            "lines": len(lines),
            "words": total_words,
            "unique_unigrams": len(unique_unigrams),
            "unique_bigrams": len(unique_bigrams),
            "unique_trigrams": len(unique_trigrams),
        },
    }


def write_outputs(data):
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(LINES_DIR, exist_ok=True)

    dump_json(os.path.join(OUT_DIR, "plays.json"), data["plays"])
    dump_json(os.path.join(OUT_DIR, "chunks.json"), data["chunks"])
    dump_json(os.path.join(OUT_DIR, "tokens.json"), data["tokens"])
    dump_json(os.path.join(OUT_DIR, "tokens2.json"), data["tokens2"])
    dump_json(os.path.join(OUT_DIR, "tokens3.json"), data["tokens3"])
    dump_json(os.path.join(OUT_DIR, "characters.json"), [])
    dump_json(os.path.join(OUT_DIR, "tokens_char.json"), {})
    dump_json(os.path.join(OUT_DIR, "tokens_char2.json"), {})
    dump_json(os.path.join(OUT_DIR, "tokens_char3.json"), {})
    dump_json(os.path.join(OUT_DIR, "character_name_filter_config.json"), {"plays": {}})
    dump_json(os.path.join(LINES_DIR, "all_lines.json"), data["lines"])


def main():
    catalog = load_catalog()
    data = build_json_corpus(catalog)
    write_outputs(data)

    for work in data["per_work_stats"]:
        print(
            f"{work['title']} ({work['year']}): "
            f"{work['chapters']} chapters, "
            f"{work['paragraphs']} paragraphs, "
            f"{work['words']:,} words"
        )

    totals = data["totals"]
    print(f"Works: {totals['works']}")
    print(f"Paragraphs: {totals['paragraphs']}")
    print(f"Lines: {totals['lines']}")
    print(f"Total words: {totals['words']:,}")
    print(f"Unique unigrams: {totals['unique_unigrams']:,}")
    print(f"Unique bigrams: {totals['unique_bigrams']:,}")
    print(f"Unique trigrams: {totals['unique_trigrams']:,}")


if __name__ == "__main__":
    main()
