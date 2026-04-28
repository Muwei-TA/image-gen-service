from __future__ import annotations

import re


RESULT_PATTERN = re.compile(r"(?:file://)?(/[^\s\x1b]+generated_images/[^\s\x1b]+\.png)")


def extract_result_paths(output: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for match in RESULT_PATTERN.finditer(output):
        path = match.group(1)
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return paths
