import tiktoken

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SEPARATORS = ["\n\n", "\n", ". ", " "]

_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))


def split_text(text: str) -> list[dict]:
    raw_chunks = _recursive_split(text, SEPARATORS, CHUNK_SIZE, CHUNK_OVERLAP)
    result = []
    for i, chunk in enumerate(raw_chunks):
        chunk = chunk.strip()
        if not chunk:
            continue
        result.append({
            "content": chunk,
            "chunk_index": i,
            "token_count": count_tokens(chunk),
        })
    return result


def _recursive_split(
    text: str, separators: list[str], chunk_size: int, overlap: int
) -> list[str]:
    if count_tokens(text) <= chunk_size:
        return [text] if text.strip() else []

    separator = separators[0] if separators else ""
    remaining_separators = separators[1:] if len(separators) > 1 else []

    if separator:
        parts = text.split(separator)
    else:
        parts = list(text)

    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = current + separator + part if current else part
        if count_tokens(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                if remaining_separators and count_tokens(current) > chunk_size:
                    chunks.extend(_recursive_split(current, remaining_separators, chunk_size, overlap))
                else:
                    chunks.append(current)

                overlap_text = _get_overlap(current, separator, overlap)
                current = overlap_text + separator + part if overlap_text else part
            else:
                if remaining_separators:
                    chunks.extend(_recursive_split(part, remaining_separators, chunk_size, overlap))
                else:
                    chunks.append(part)
                current = ""

    if current and current.strip():
        if remaining_separators and count_tokens(current) > chunk_size:
            chunks.extend(_recursive_split(current, remaining_separators, chunk_size, overlap))
        else:
            chunks.append(current)

    return chunks


def _get_overlap(text: str, separator: str, overlap_tokens: int) -> str:
    if not overlap_tokens:
        return ""

    if separator:
        parts = text.split(separator)
    else:
        parts = list(text)

    overlap_parts: list[str] = []
    total = 0
    for part in reversed(parts):
        tokens = count_tokens(part)
        if total + tokens > overlap_tokens:
            break
        overlap_parts.insert(0, part)
        total += tokens

    return separator.join(overlap_parts) if overlap_parts else ""
