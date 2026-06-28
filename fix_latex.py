import re
import sys


def _find_matching_brace(text, start):
    """Return index after matching '}' for '{' at position start."""
    if text[start] != "{":
        return start + 1
    depth = 1
    i = start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return i


def fix_text_commands(content):
    """Move any LaTeX command (\\cmd) from inside \\text{} to outside."""
    result = []
    i = 0

    while i < len(content):
        m = re.search(r"\\text\{", content[i:])
        if not m:
            result.append(content[i:])
            break

        result.append(content[i : i + m.start()])

        text_start = i + m.start() + len(r"\text{")
        text_end = _find_matching_brace(content, text_start - 1) - 1
        inner = content[text_start:text_end]

        # Scan inner: split into text and command segments
        segs = []
        p = 0
        while p < len(inner):
            if inner[p] == "\\" and p + 1 < len(inner) and inner[p + 1].isalpha():
                cm = re.match(r"\\([a-zA-Z]+)", inner[p:])
                cmd_end = p + cm.end()
                while cmd_end < len(inner) and inner[cmd_end] == "{":
                    cmd_end = _find_matching_brace(inner, cmd_end)
                segs.append(("cmd", inner[p:cmd_end]))
                p = cmd_end
            else:
                start_text = p
                p += 1
                while p < len(inner) and not (
                    inner[p] == "\\" and p + 1 < len(inner) and inner[p + 1].isalpha()
                ):
                    p += 1
                segs.append(("text", inner[start_text:p]))

        # Rebuild: text in \text{}, commands outside
        fixed = ""
        for typ, val in segs:
            if typ == "cmd":
                fixed += val
            elif val:
                fixed += "\\text{" + val + "}"

        # Remove truly empty \text{} (zero-length content only)
        fixed = re.sub(r"\\text\{\}", "", fixed)

        # Merge adjacent \text{...}\text{...}
        prev = None
        while prev != fixed:
            prev = fixed
            fixed = re.sub(
                r"\\text\{([^}]*)\}\\text\{([^}]*)\}", r"\\text{\1\2}", fixed
            )

        result.append(fixed)
        i = text_end + 1

    return "".join(result)


def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = fix_text_commands(content)
    content = re.sub(r"\\text\{\}", "", content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 fix_latex.py <archivo.tex> [archivo2.tex ...]")
        sys.exit(1)

    for arg in sys.argv[1:]:
        fix_file(arg)
        print(f"Fixed: {arg}")
    print("Done")
