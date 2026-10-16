#!/usr/bin/env python3
"""GDScript style gate for the changed lines of `.gd` files, per `.claude/rules/gdscript.md`.

Suppress a justified exception on the same line or the line above:

    # gdstyle-ignore[rule-a,rule-b]: reason
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
STYLE_ROOTS = ("src",)
LOAD_EXEMPT_PREFIXES = ("src/editor/",)

RULES: dict[str, str] = {
    "logical-ops": "use &&, ||, ! instead of and, or, not",
    "dollar-node": "use %UniqueName instead of $Path",
    "get-node-literal": "use %UniqueName instead of get_node() with a literal path",
    "null-compare": "use is_instance_valid(obj) / !is_instance_valid(obj) instead of == null / != null",
    "load": "load()/preload()/ResourceLoader.load() only as a justified last resort",
    "untyped-var": "variable declared without a type",
    "untyped-const": "constant declared without a type",
    "infer-call": "':=' with a function call result: write the type explicitly",
    "infer-collection-literal": "':=' with an [] / {} literal infers an untyped collection",
    "infer-node-path": "':=' with %Node / $Node infers only Node: write the type explicitly",
    "untyped-param": "function parameter without a type",
    "missing-return-type": "function without a return type",
    "untyped-collection": "untyped Array / Dictionary: add element types",
    "visible-literal": "use show() / hide() instead of visible = true / false",
    "private-access": "calling another object's _private method",
}

IGNORE_MARKER = re.compile(r"gdstyle-ignore\[([\w,\s-]+)\]\s*:\s*\S")

CONVERSION_FUNCTIONS = frozenset({"str", "int", "float", "bool"})

RE_LOGICAL = re.compile(r"\b(and|or|not)\b")
RE_IS_NOT = re.compile(r"\bis\s+not\b")
RE_DOLLAR = re.compile(r"\$(?!%)[\w\"'/.]")
# Receiver-less only: `state_machine.get_node("idle")` / `root.get_node("Main")` are other APIs.
RE_GET_NODE_LITERAL = re.compile(r"(?<![\w.])get_node(?:_or_null)?\s*\(\s*[&^]?[\"'](?!%)")
RE_NULL_COMPARE = re.compile(r"[!=]=\s*null\b|\bnull\s*[!=]=")
RE_LOAD = re.compile(r"(?<![\w.])(?:pre)?load\s*\(|\bResourceLoader\s*\.\s*load\s*\(")
RE_VAR = re.compile(r"\bvar\s+(\w+)\s*(.*)$")
RE_CONST = re.compile(r"\bconst\s+(\w+)\s*(.*)$")
RE_UNTYPED_COLLECTION = re.compile(r"(?::|->)\s*(Array|Dictionary)\b(?!\s*\[)")
RE_VISIBLE_LITERAL = re.compile(r"\bvisible\s*=\s*(true|false)\b")
RE_PRIVATE_ACCESS = re.compile(r"(\w*)(?<=[\w)\]])(?<!\bself)(?<!\bsuper)\._\w+\s*\(")
RE_CLASS_NAME = re.compile(r"^\s*class_name\s+(\w+)")
RE_METHOD_START = re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?func\s+\w+\s*\(")
RE_LAMBDA_START = re.compile(r"\bfunc\s*\(")
RE_CALL = re.compile(r"(\.?)\s*\b([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*\(")
RE_CAST_SUFFIX = re.compile(r"\bas\s+[\w.]+(\s*\[[^\]]*\])?$")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    code: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {RULES[self.rule]}: {self.code.strip()}"


# --------------------------------------------------------------------------------------------
# Source preparation
# --------------------------------------------------------------------------------------------

def strip_code(line: str) -> str:
    """Remove the comment and empty every string literal, keeping its delimiters and prefix."""
    out: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if line.startswith(quote, index):
                out.append(quote)
                index += len(quote)
                quote = None
                continue
            index += 1
            continue
        if char in "\"'":
            quote = line[index:index + 3] if line.startswith(char * 3, index) else char
            out.append(quote)
            index += len(quote)
            continue
        if char == "#":
            break
        out.append(char)
        index += 1
    return "".join(out)


def suppressed_rules(raw_lines: list[str], index: int) -> set[str]:
    rules: set[str] = set()
    for candidate in (index, index - 1):
        if 0 <= candidate < len(raw_lines):
            for match in IGNORE_MARKER.finditer(raw_lines[candidate]):
                rules.update(part.strip() for part in match.group(1).split(",") if part.strip())
    return rules


# --------------------------------------------------------------------------------------------
# Expression helpers
# --------------------------------------------------------------------------------------------

def matching_paren(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] in "([{":
            depth += 1
        elif text[index] in ")]}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def split_top_level(text: str, separator: str = ",") -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == separator and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return parts


def is_constructor_name(name: str) -> bool:
    # `Vector3(`, `RDUniform(` — but not ALL_CAPS helpers like `LOG_ONCE(`.
    return name[0].isupper() and any(char.islower() for char in name)


def is_allowed_call(name: str, is_member: bool) -> bool:
    if is_member:
        return name == "new"
    return name in CONVERSION_FUNCTIONS or is_constructor_name(name)


def inferred_rhs_rule(rhs: str) -> str | None:
    """Return the violated rule for `name := rhs`, or None when the type is obvious."""
    expression = rhs.strip().rstrip(";").strip()
    if expression.endswith(":"):
        expression = expression[:-1].rstrip()  # `var x := 1:` followed by a setter block
    if not expression:
        return None
    if expression[0] in "[{":
        return "infer-collection-literal"
    if expression[0] in "%$":
        return "infer-node-path"
    if expression.startswith("func") or RE_CAST_SUFFIX.search(expression):
        return None
    if re.match(r"[&^]?(\"\"|'')\s*%", expression):
        return None  # "format" % [...] is always a String

    # The whole expression is a single allowed call: `Type.new(...)`, `Vector3(...)`, `str(...)`.
    whole_call = re.match(r"([\w.]+?)\s*(\[[^\]]*\])?\s*\(", expression)
    if whole_call and matching_paren(expression, whole_call.end() - 1) == len(expression) - 1:
        dotted = whole_call.group(1)
        name = dotted.rsplit(".", 1)[-1]
        if is_allowed_call(name, "." in dotted):
            return None

    for match in RE_CALL.finditer(expression):
        name = match.group(2)
        if name in {"if", "else", "and", "or", "not", "in", "is", "as", "await", "func"}:
            continue
        # A preceding `.` (possibly after `]`/`)`) marks a member call.
        prefix = expression[:match.start(2)].rstrip()
        is_member = prefix.endswith(".")
        if not is_allowed_call(name, is_member):
            return "infer-call"
    return None


def parse_signature(code_lines: list[str], line_index: int, start_column: int) -> tuple[str, str, int] | None:
    """Collect `(params) -> Return:` starting at the `(` found from start_column.

    Returns (params_text, after_params_text, last_line_index) or None if unbalanced.
    """
    text = ""
    open_index: int | None = None
    for current in range(line_index, min(line_index + 30, len(code_lines))):
        segment = code_lines[current][start_column:] if current == line_index else code_lines[current]
        text += segment + " "
        if open_index is None:
            open_index = text.find("(")
            if open_index < 0:
                return None
        close_index = matching_paren(text, open_index)
        if close_index >= 0:
            after = text[close_index + 1:]
            colon = after.find(":")
            if colon < 0:
                # `-> Type` may continue on the next line only in pathological formatting.
                return text[open_index + 1:close_index], after, current
            return text[open_index + 1:close_index], after[:colon], current
    return None


def signature_findings(params_text: str, after_params: str, is_lambda: bool) -> list[str]:
    rules: list[str] = []
    if params_text.strip():
        for parameter in split_top_level(params_text):
            parameter = parameter.strip()
            if not parameter:
                continue
            parameter = parameter.removeprefix("...")
            name_match = re.match(r"(\w+)\s*(.*)$", parameter, re.S)
            if not name_match:
                continue
            name, rest = name_match.group(1), name_match.group(2).strip()
            typed = rest.startswith(":")  # `: Type` or `:= default`
            if typed:
                continue
            if is_lambda and name.startswith("_"):
                continue
            rules.append("untyped-param")
            break
    if "->" not in after_params:
        rules.append("missing-return-type")
    return rules


# --------------------------------------------------------------------------------------------
# File check
# --------------------------------------------------------------------------------------------

def check_lines(relative_path: str, raw_lines: list[str], changed: set[int] | None = None) -> list[Finding]:
    """Check a file. `changed` holds 1-based line numbers to report; None means every line."""
    code_lines = [strip_code(line) for line in raw_lines]
    findings: list[Finding] = []
    load_exempt = relative_path.startswith(LOAD_EXEMPT_PREFIXES)
    own_class_names = {match.group(1) for match in map(RE_CLASS_NAME.match, code_lines) if match}

    def report(index: int, rule: str) -> None:
        if changed is not None and index + 1 not in changed:
            return
        if rule in suppressed_rules(raw_lines, index):
            return
        finding = Finding(relative_path, index + 1, rule, raw_lines[index])
        if finding not in findings:
            findings.append(finding)

    for index, (raw, code) in enumerate(zip(raw_lines, code_lines)):
        signature_line = changed is None or index + 1 in changed
        if not code.strip():
            continue

        if RE_LOGICAL.search(RE_IS_NOT.sub(" ", code)):
            report(index, "logical-ops")
        if RE_DOLLAR.search(code):
            report(index, "dollar-node")
        # Strings are emptied in `code`, so the literal path is inspected on the raw line.
        if "get_node" in code and RE_GET_NODE_LITERAL.search(raw):
            report(index, "get-node-literal")
        if RE_NULL_COMPARE.search(code):
            report(index, "null-compare")
        if not load_exempt and RE_LOAD.search(code) and not re.match(r"\s*(static\s+)?func\s", code):
            report(index, "load")
        if RE_UNTYPED_COLLECTION.search(code):
            report(index, "untyped-collection")
        if RE_VISIBLE_LITERAL.search(code):
            report(index, "visible-literal")
        # `OwnClass._static_helper()` is still a call from inside the class.
        if any(match.group(1) not in own_class_names for match in RE_PRIVATE_ACCESS.finditer(code)):
            report(index, "private-access")

        for regex, untyped_rule in ((RE_VAR, "untyped-var"), (RE_CONST, "untyped-const")):
            match = regex.search(code)
            if not match or re.match(r"\s*for\b", code):
                continue
            rest = match.group(2).strip().rstrip(";").strip()
            if rest.startswith(":="):
                rule = inferred_rhs_rule(rest[2:])
                if rule:
                    report(index, rule)
            elif rest == "" or rest == ":" or rest.startswith("="):
                report(index, untyped_rule)

        if not signature_line:
            continue
        starts: list[tuple[int, bool]] = []
        method_match = RE_METHOD_START.match(code)
        if method_match:
            starts.append((method_match.end() - 1, False))
        for lambda_match in RE_LAMBDA_START.finditer(code):
            starts.append((lambda_match.end() - 1, True))
        for column, is_lambda in starts:
            parsed = parse_signature(code_lines, index, column)
            if not parsed:
                continue
            params_text, after_params, _ = parsed
            for rule in signature_findings(params_text, after_params, is_lambda):
                report(index, rule)

    return findings


# --------------------------------------------------------------------------------------------
# Git plumbing
# --------------------------------------------------------------------------------------------

def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def changed_lines(base: str) -> dict[str, set[int] | None]:
    """Map repo-relative `.gd` paths to changed 1-based line numbers (None = whole file)."""
    changes: dict[str, set[int] | None] = {}
    diff = run_git("diff", "-U0", "--no-color", "--no-ext-diff", "-M", base, "--", *STYLE_ROOTS)
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = target[2:] if target.startswith("b/") and target.endswith(".gd") else None
            if current is not None:
                changes.setdefault(current, set())
            continue
        if current is None or not line.startswith("@@"):
            continue
        hunk = re.search(r"\+(\d+)(?:,(\d+))?", line)
        if not hunk:
            continue
        start = int(hunk.group(1))
        count = int(hunk.group(2)) if hunk.group(2) is not None else 1
        lines = changes[current]
        assert lines is not None
        lines.update(range(start, start + count))

    untracked = run_git("ls-files", "--others", "--exclude-standard", "-z", "--", *STYLE_ROOTS)
    for path in untracked.split("\0"):
        if path.endswith(".gd"):
            changes[path] = None
    return changes


def check_changes(base: str = "HEAD") -> list[Finding]:
    findings: list[Finding] = []
    for relative_path, lines in sorted(changed_lines(base).items()):
        if lines is not None and not lines:
            continue
        path = REPO_ROOT / relative_path
        if not path.is_file():
            continue
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        findings.extend(check_lines(relative_path, raw_lines, lines))
    return findings


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="HEAD", help="git ref to diff against (default: HEAD)")
    parser.add_argument("files", nargs="*", help="check these files fully instead of a git diff")
    args = parser.parse_args()

    if args.files:
        findings = []
        for file in args.files:
            path = Path(file).resolve()
            relative = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else file
            findings.extend(check_lines(relative, path.read_text(encoding="utf-8", errors="replace").splitlines()))
    else:
        findings = check_changes(args.base)

    for finding in findings:
        print(finding)
    print(f"{'FAIL' if findings else 'PASS'} gdscript-style ({len(findings)} finding(s))")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
