"""
Turn reference PDFs into searchable chunks.

The chunker is optimised for Philippine legal documents — IRRs, circulars,
resolutions and procurement manuals — where headings matter because a finding
that cites "Section 23.1" must actually be able to quote from that section.

extract_text(..., markers=True) inserts "[page N]" lines, which the chunker
reads to know what page each chunk starts on, then strips out so the text
carried into a prompt is clean. The page number lives in the Chunk.page field
and the section in Chunk.section; both become part of the citation.
"""

import re

from knowledge.schema import Chunk

# Target size balanced between "enough context to be self-contained" and "short
# enough to retrieve precisely". The chunker overshoots slightly when necessary
# to finish a paragraph rather than break mid-sentence.
TARGET_CHARS = 1200
OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 100
MAX_CHUNK_CHARS = 2500

# Philippine legal documents use a variety of heading styles. These patterns
# are deliberately strict — an undetected heading results in an empty section
# field (which is fine), whereas a WRONG section makes a finding uncitable.
# Patterns are tried in order; the first match wins.
#
# The flag says whether the pattern may carry a title. A line opening with a
# keyword — "Section 23.1 Eligibility" — announces itself as a heading, so the
# rest of the line is one. A line opening with a bare number does not: the IRR
# runs its provisions straight into their text, so "40.2 Procuring Entities
# are authorized to..." is a paragraph. For those, only the number is kept.
_TITLED, _NUMBER_ONLY = True, False

HEADING_PATTERNS = [
    # "Section 23.1 — Title" or "SECTION 5. Title"
    (
        re.compile(r"^(SECTION\s+\d+(?:\.\d+)?(?:\s*[—\-\.]\s*.*)?)", re.IGNORECASE),
        _TITLED,
    ),
    # "Rule IV" or "RULE 4 — Title"
    (re.compile(r"^(RULE\s+[IVXLCDM\d]+(?:\s*[—\-\.]\s*.*)?)", re.IGNORECASE), _TITLED),
    # "ARTICLE VI" or "Article 3 — Title"
    (
        re.compile(r"^(ARTICLE\s+[IVXLCDM\d]+(?:\s*[—\-\.]\s*.*)?)", re.IGNORECASE),
        _TITLED,
    ),
    # "Annex A" or "ANNEX B — Title"
    (re.compile(r"^(ANNEX\s+[A-Z0-9]+(?:\s*[—\-\.]\s*.*)?)", re.IGNORECASE), _TITLED),
    # "23.1 ..." or "8.5.2 ..." — a dot is required. A line opening with a
    # bare integer is far more often a list item or a stray page number than
    # a provision, and guessing wrong puts a false citation on a finding.
    (re.compile(r"^(\d+(?:\.\d+)+)\.?\s+[A-Z]"), _NUMBER_ONLY),
    # "(a) Title" or "(1) Title" — subsections
    (re.compile(r"^(\([a-z0-9]+\))\s+[A-Z]"), _NUMBER_ONLY),
]

#: Past this a title is being quoted rather than named, so it is cut at a word
#: boundary. Long enough for the longest real section title in the corpus.
HEADING_MAX_CHARS = 90


#: A heading that says nothing on its own. "40.2" implies Section 40 and can
#: be cited as it stands, but "(a)" needs the section above it or a reader
#: cannot find the passage at all.
_NEEDS_PARENT = re.compile(r"^\(\w+\)$")

#: The identifier at the front of a titled heading, without its title:
#: "Section 2. Declaration of Policy" -> "Section 2".
_PARENT_IDENTIFIER = re.compile(
    r"^((?:SECTION|RULE|ARTICLE|ANNEX)\s+[IVXLCDM\dA-Z]+(?:\.\d+)*)", re.IGNORECASE
)


def qualify(heading: str, parent: str) -> str:
    """
    Attach the enclosing section to a subsection that cannot stand alone.

    A citation exists so a reader can find the passage. "(a)" sends them
    nowhere; "Section 24 (a)" sends them to one place.
    """
    if not heading or not parent or not _NEEDS_PARENT.match(heading):
        return heading
    match = _PARENT_IDENTIFIER.match(parent)
    return f"{match.group(1)} {heading}" if match else heading


def _detect_heading(line: str) -> tuple[str, bool]:
    """
    Return the heading and whether it carried its own title, or ("", False).

    Philippine legal documents mix numbered sections, articles, rules and
    annexes. The patterns above are tuned to the corpus we actually index.

    Length cannot be used to tell a heading from body text here: PDF
    extraction preserves the original hard wrapping at roughly seventy
    characters, so every line in the document looks short. What distinguishes
    them is how the line opens, which is what the flag on each pattern records.
    """
    stripped = " ".join(line.split())
    for pattern, titled in HEADING_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        heading = " ".join(match.group(1).split())
        if not titled:
            return heading.rstrip("."), False
        if len(heading) <= HEADING_MAX_CHARS:
            return heading, True
        cut = heading[:HEADING_MAX_CHARS].rsplit(" ", 1)[0]
        return f"{cut}…", True
    return "", False


def _normalise(text: str) -> str:
    """
    Clean up extracted text for inclusion in a prompt.

    PyMuPDF sometimes produces runs of whitespace or stray newlines inside a
    paragraph. Collapse them so the chunk reads naturally when quoted.
    """
    return " ".join(text.split())


def chunk_document(doc_id: str, doc_title: str, text: str) -> list[Chunk]:
    """
    Split a document into overlapping chunks that carry their own citations.

    Each chunk knows its page and section, so a finding can cite "IRR of RA
    12009 — Section 23.1" with confidence that the reader will find exactly the
    passage the analysis rests on.

    The input text is what extract_text(..., markers=True) produces: page
    markers as separate lines, then the text of that page. A marker looks like
    "[page 42]". The chunker tracks the current page as it walks the text, and
    every chunk records the page it starts on.
    """
    if not text.strip():
        return []

    lines = text.splitlines()
    chunks: list[Chunk] = []
    current_page = 0
    current_section = ""
    current_parent = ""  # most recent heading that carried its own title

    # Accumulate text until it reaches the target size, then emit a chunk. Keep
    # a sliding window of the tail so the next chunk starts with overlap.
    buffer: list[str] = []
    buffer_page = 0  # the page the buffer started on
    buffer_section = ""

    for line in lines:
        # Track page markers but do not include them in the chunk text.
        page_match = re.match(r"^\[page\s+(\d+)\]", line.strip())
        if page_match:
            current_page = int(page_match.group(1))
            continue

        # Check whether this line is a heading. If so, remember it as the
        # section for all following text until another heading appears.
        heading, titled = _detect_heading(line)
        if heading:
            if titled:
                current_parent = heading
            current_section = qualify(heading, current_parent)

        # Start the first chunk or reset the page/section after emitting one.
        if not buffer:
            buffer_page = current_page or buffer_page
            buffer_section = current_section

        buffer.append(line)

        # Estimate the buffer size. Joining is cheap and avoids miscounting.
        buffer_text = "\n".join(buffer)
        if len(buffer_text) >= TARGET_CHARS:
            # Prefer to finish the paragraph we are in rather than break mid-
            # sentence. Look ahead up to a reasonable distance for a blank line.
            lookahead = []
            remaining = lines[lines.index(line) + 1 :]
            for next_line in remaining[:20]:  # do not look too far ahead
                if re.match(r"^\[page\s+\d+\]", next_line.strip()):
                    continue
                lookahead.append(next_line)
                if not next_line.strip():  # blank line = paragraph break
                    break
                if len("\n".join(lookahead)) > 400:  # do not overshoot badly
                    break

            buffer.extend(lookahead)
            chunk_text = _normalise("\n".join(buffer))

            # Emit the chunk if it is at least the minimum size, otherwise wait
            # for more text. This avoids tiny chunks at the end of a document.
            if len(chunk_text) >= MIN_CHUNK_CHARS:
                chunks.append(
                    Chunk(
                        id=f"{doc_id}#{len(chunks):04d}",
                        doc_id=doc_id,
                        doc_title=doc_title,
                        section=buffer_section,
                        page=buffer_page,
                        text=chunk_text[:MAX_CHUNK_CHARS],
                    )
                )

                # Start the next chunk with overlap from the tail of this one.
                # Split on whitespace to avoid breaking mid-word.
                words = chunk_text.split()
                overlap = []
                overlap_len = 0
                for word in reversed(words):
                    if overlap_len + len(word) + 1 > OVERLAP_CHARS:
                        break
                    overlap.insert(0, word)
                    overlap_len += len(word) + 1

                buffer = [" ".join(overlap)] if overlap else []
                buffer_page = current_page or buffer_page
                buffer_section = current_section
            else:
                # Not enough text yet; keep accumulating.
                pass

    # Emit any remaining text as a final chunk.
    if buffer:
        chunk_text = _normalise("\n".join(buffer))
        if len(chunk_text) >= MIN_CHUNK_CHARS:
            chunks.append(
                Chunk(
                    id=f"{doc_id}#{len(chunks):04d}",
                    doc_id=doc_id,
                    doc_title=doc_title,
                    section=buffer_section,
                    page=buffer_page,
                    text=chunk_text[:MAX_CHUNK_CHARS],
                )
            )

    return chunks
