#!/usr/bin/env python3
"""spring-payment-pci-shield: deterministic checks for Spring Boot payment code.

Two entry points:
  pci_shield.py --hook          PostToolUse hook. Reads the hook JSON on stdin and
                                scans the file that was just written or edited.
  pci_shield.py [PATH ...]      CLI. Scans files and directories (default: .).

Rules (error blocks the agent, warn is passed back as context):
  PCI001 error  sensitive card/PII value reaches a log call or exception message
  PCI002 error  DTO/record/Lombok toString() would print a sensitive field
  PCI003 warn   request-logging filter configured to include payloads
  MON001 error  double/float used for a monetary value
  MON002 error  new BigDecimal(<double>) (binary floating point leaks in)
  MON003 error  BigDecimal.divide without RoundingMode/MathContext
  MON004 error  BigDecimal.setScale without RoundingMode
  MON005 error  deprecated BigDecimal.ROUND_* int constants
  MON006 warn   BigDecimal converted back to double/float
  CFG001 warn   spring.jpa.show-sql enabled
  CFG002 error  Hibernate bind-parameter logging at TRACE (logs bound PAN/CVV)
  CFG003 error  HTTP wire/body logging (Apache HC, Reactor Netty, Feign FULL, ...)
  CFG004 error  spring.mvc/codec log-request-details enabled
  CFG005 warn   root logger at DEBUG/TRACE
  CFG006 warn   server.error.include-stacktrace=always

Suppress a finding with a comment on the same or previous line:
  // pci-shield:ignore MON001 -- reason
Python 3.8+, standard library only.
"""
import json
import os
import re
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Findings


@dataclass
class Finding:
    rule: str
    severity: str  # "error" | "warn"
    path: str
    line: int
    message: str

    def format(self):
        return f"{self.path}:{self.line} [{self.rule}] {self.message}"


HINTS = {
    "PCI001": "Never log raw PAN/CVV/PIN/track data (PCI-DSS 3.3/3.4). Log a masked value "
              "(first6/last4 at most) via a masking helper, a token, or drop the field.",
    "PCI002": "Generated toString() includes every field, so `log.info(\"{}\", dto)` leaks it. "
              "Add @ToString.Exclude (Lombok) or override toString() in the record to mask it.",
    "PCI003": "CommonsRequestLoggingFilter with includePayload logs request bodies, including card data.",
    "MON001": "Use BigDecimal (or long minor units) for money. double/float cannot represent 0.10 exactly.",
    "MON002": "new BigDecimal(0.1) == 0.1000000000000000055511151231257827... "
              "Use new BigDecimal(\"0.10\") or BigDecimal.valueOf(x).",
    "MON003": "divide() without a RoundingMode throws ArithmeticException on 1/3 and gives "
              "unpredictable scale. Use divide(x, scale, RoundingMode.HALF_EVEN) or a MathContext.",
    "MON004": "setScale(n) without RoundingMode throws when rounding is needed. "
              "Use setScale(n, RoundingMode.HALF_EVEN) (or the mode your ledger specifies).",
    "MON005": "BigDecimal.ROUND_* int constants are deprecated since Java 9. Use java.math.RoundingMode.",
    "MON006": "Converting money back to double reintroduces rounding error. Keep it BigDecimal end to end.",
    "CFG001": "show-sql prints every statement to stdout outside your log masking. Disable it outside local dev.",
    "CFG002": "Bind-parameter TRACE logging writes every bound value (PAN, CVV, names) to the log.",
    "CFG003": "Wire/body logging writes full HTTP payloads to/from the payment gateway into logs.",
    "CFG004": "log-request-details logs request parameters and headers, including card data and auth headers.",
    "CFG005": "Root DEBUG/TRACE turns on body/parameter logging in many libraries at once.",
    "CFG006": "Stack traces in error responses leak internals. Use on_param or never.",
}

# ---------------------------------------------------------------------------
# Identifier classification

SENSITIVE_WORDS = {"pan", "cvv", "cvc", "cvv2", "cvc2", "cvn", "ssn", "pin", "pinblock", "iban",
                   "track1", "track2"}
SENSITIVE_PAIRS = [("card", "number"), ("account", "number"), ("routing", "number"),
                   ("security", "code"), ("track", "data"), ("card", "expiry"),
                   ("card", "expiration"), ("social", "security"), ("card", "verification"),
                   ("primary", "account")]
# Words that mean the value is already safe to show (masked, tokenized, partial).
SAFE_WORDS = {"mask", "masked", "masking", "redact", "redacted", "last", "hash", "hashed", "token",
              "tokenized", "fingerprint", "bin", "length", "len", "valid", "present", "type",
              "brand", "encrypted", "ref", "reference"}
MONEY_WORDS = {"amount", "amounts", "price", "subtotal", "fee", "fees", "cost", "money", "charge",
               "refund", "payment", "payout", "settlement", "surcharge", "fare", "salary", "wage"}
# Only money when the file is clearly about money (`totalWeight`, `balanceFactor` are not).
WEAK_MONEY_WORDS = {"total", "balance", "tax", "tip", "discount", "cash", "principal"}
NOT_MONEY_WORDS = {"factor", "weight", "percentage", "percent", "pct", "ratio", "count", "size", "time",
                   "seconds", "millis", "ms", "memory", "score", "load", "bytes"}
_MONEY_CONTEXT = re.compile(r"BigDecimal|Currency|MonetaryAmount|\bMoney\b|[Pp]ayment|[Ii]nvoice|[Ll]edger")


def is_money_name(ident, money_context):
    w = set(words(ident))
    if w & NOT_MONEY_WORDS:
        return False
    return bool(w & MONEY_WORDS or (money_context and w & WEAK_MONEY_WORDS))

_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


def words(ident):
    return [w.lower() for w in _WORD.findall(ident)]


def is_sensitive_ident(ident):
    w = set(words(ident))
    if w & SAFE_WORDS:
        return False
    if w & SENSITIVE_WORDS:
        return True
    return any(a in w and b in w for a, b in SENSITIVE_PAIRS)


def is_sensitive_chain(chain):
    """`req.getCardNumber`, `card.number`, `pan` -> True; `card.maskedNumber` -> False."""
    segs = [s.strip() for s in chain.split(".")]
    if set(words(segs[-1])) & SAFE_WORDS:
        return False
    if any(is_sensitive_ident(s) for s in segs):
        return True
    return any(is_sensitive_ident(a + "_" + b) for a, b in zip(segs, segs[1:]))


# ---------------------------------------------------------------------------
# Java text helpers. Everything works on a "blanked" copy of the source where
# comments and string contents are spaces, so offsets and line numbers match.


def blank_code(src):
    out = list(src)
    n = len(src)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    while i < n:
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif src.startswith('"""', i):
            j = src.find('"""', i + 3)
            if j < 0:
                blank(i + 3, n)
                i = n
            else:
                blank(i + 3, j)
                i = j + 3
        elif src[i] in "\"'":
            q = src[i]
            j = i + 1
            while j < n and src[j] != q and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            blank(i + 1, j)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def match_close(text, i, open_c="(", close_c=")"):
    """Index of the bracket closing text[i], or -1."""
    depth = 0
    for k in range(i, len(text)):
        if text[k] == open_c:
            depth += 1
        elif text[k] == close_c:
            depth -= 1
            if depth == 0:
                return k
    return -1


def split_args(text):
    """Split on top-level commas (ignores commas inside (), <>, [], {})."""
    args, depth, start = [], 0, 0
    for k, c in enumerate(text):
        if c in "(<[{":
            depth += 1
        elif c in ")>]}":
            depth -= 1
        elif c == "," and depth == 0:
            args.append(text[start:k])
            start = k + 1
    tail = text[start:]
    if tail.strip() or args:
        args.append(tail)
    return [a.strip() for a in args]


def statement_end(text, i):
    """End of the statement starting at i (first ';' at bracket depth 0)."""
    depth = 0
    for k in range(i, len(text)):
        c = text[k]
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth -= 1
            if depth < 0:
                return k
        elif c == ";" and depth == 0:
            return k
    return len(text)


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


_MASK_CALL = re.compile(r"(?i)(?<![\w$])[\w$.]*?(?:mask|redact|obfuscat|last4|lastfour|truncat|tokeni[sz])[\w$]*\s*\(")
_CHAIN = re.compile(r"[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*")


def sensitive_refs(expr):
    """Sensitive identifier chains in a Java expression, ignoring masking-helper calls."""
    expr = re.sub(r"\(\s*\)", "", expr)
    while True:
        m = _MASK_CALL.search(expr)
        if not m:
            break
        close = match_close(expr, m.end() - 1)
        end = len(expr) if close < 0 else close + 1
        expr = expr[: m.start()] + " " * (end - m.start()) + expr[end:]
    chains = (re.sub(r"\s+", "", c) for c in _CHAIN.findall(expr))
    return [c for c in chains if is_sensitive_chain(c)]


# ---------------------------------------------------------------------------
# Java rules

_LOG_CALL = re.compile(
    r"\b(?:log|logger|LOG|LOGGER|[A-Za-z_$][\w$]*Logger|[A-Za-z_$][\w$]*Log|[A-Z_]*_LOG(?:GER)?)\s*\.\s*"
    r"(?:trace|debug|info|warn|error|atTrace|atDebug|atInfo|atWarn|atError|atLevel)\s*\("
    r"|\bSystem\s*\.\s*(?:out|err)\s*\.\s*(?:println|printf|print|format)\s*\("
)
_EXC_NEW = re.compile(r"\bnew\s+[A-Z][\w$.]*(?:Exception|Error)\s*\(")


def check_sensitive_sinks(code, add):
    for regex, sink in ((_LOG_CALL, "log statement"), (_EXC_NEW, "exception message")):
        for m in regex.finditer(code):
            end = statement_end(code, m.start())
            refs = sensitive_refs(code[m.end() - 1:end])
            if refs:
                add("PCI001", "error", line_of(code, m.start()),
                    f"sensitive value `{refs[0]}` passed to {sink}")


_TYPE_DECL = re.compile(r"\b(class|record)\s+([A-Za-z_$][\w$]*)\s*(<[^>{]*>)?\s*")
_TOSTRING = re.compile(r"\bString\s+toString\s*\(\s*\)\s*(?:throws[^{]*)?\{")
_ANNOTATION = re.compile(r"@[\w$.]+(?:\s*\([^()]*(?:\([^()]*\)[^()]*)*\))?")
_MODIFIERS = re.compile(r"\b(?:private|protected|public|static|final|transient|volatile)\b")


def class_members(code, open_brace, close_brace):
    """(start, end) spans of depth-1 statements (fields) in a class body. Method,
    initializer and nested-type bodies are skipped along with their headers."""
    spans, seg, i = [], open_brace + 1, open_brace + 1
    while i < close_brace:
        c = code[i]
        if c == "{":
            j = match_close(code, i, "{", "}")
            i = (close_brace if j < 0 else j) + 1
            seg = i
            continue
        if c == "(":
            j = match_close(code, i)
            i = (close_brace if j < 0 else j) + 1
            continue
        if c == ";":
            spans.append((seg, i))
            seg = i + 1
        i += 1
    return spans


def field_name(stmt):
    stmt = _MODIFIERS.sub(" ", _ANNOTATION.sub(" ", stmt))
    decl = stmt.split("=", 1)[0]
    if "(" in decl:
        return None
    m = re.match(r"^\s*[\w$<>\[\],.?\s]+?\s+([A-Za-z_$][\w$]*)\s*$", decl, re.S)
    return m.group(1) if m else None


def annotation_prefix(raw, code, decl_start):
    """Raw text of the annotations/modifiers right before a type declaration."""
    k = decl_start - 1
    while k >= 0 and code[k] not in ";{}":
        k -= 1
    return raw[k + 1:decl_start]


def check_tostring_leaks(raw, code, add):
    for m in _TYPE_DECL.finditer(code):
        kind, name = m.group(1), m.group(2)
        pos = m.end()
        components = []
        if kind == "record":
            if pos >= len(code) or code[pos] != "(":
                continue
            close = match_close(code, pos)
            if close < 0:
                continue
            for comp in split_args(code[pos + 1:close]):
                cm = re.search(r"([A-Za-z_$][\w$]*)\s*$", _ANNOTATION.sub(" ", comp))
                if cm:
                    components.append(cm.group(1))
            pos = close + 1
        body_open = code.find("{", pos)
        if body_open < 0:
            continue
        body_close = match_close(code, body_open, "{", "}")
        if body_close < 0:
            body_close = len(code)
        body = code[body_open:body_close]

        explicit = None
        for tm in _TOSTRING.finditer(body):
            # only the type's own toString(), not one in a nested type
            if body.count("{", 0, tm.start()) - body.count("}", 0, tm.start()) == 1:
                explicit = tm
                break
        if explicit:
            ts_open = body_open + explicit.end() - 1
            ts_close = match_close(code, ts_open, "{", "}")
            refs = sensitive_refs(code[ts_open:ts_close if ts_close > 0 else body_close])
            if refs:
                add("PCI002", "error", line_of(code, ts_open),
                    f"{name}.toString() prints sensitive value `{refs[0]}`")
            continue

        if kind == "record":
            for comp in components:
                if is_sensitive_ident(comp):
                    add("PCI002", "error", line_of(code, m.start()),
                        f"record {name} has sensitive component `{comp}` and no toString() override")
            continue

        prefix = annotation_prefix(raw, code, m.start())
        if not re.search(r"@(?:lombok\.)?(?:Data|Value|ToString)\b", prefix):
            continue
        if re.search(r"onlyExplicitlyIncluded\s*=\s*true", prefix):
            continue
        for s, e in class_members(code, body_open, body_close):
            fname = field_name(code[s:e])
            if not fname or not is_sensitive_ident(fname):
                continue
            if "@ToString.Exclude" in raw[s:e] or re.search(
                    r"exclude\s*=\s*\{?[^)]*\"" + re.escape(fname) + "\"", prefix):
                continue
            stmt = code[s:e]
            add("PCI002", "error", line_of(code, s + len(stmt) - len(stmt.lstrip())),
                f"Lombok toString() on {name} includes sensitive field `{fname}`")


def check_request_logging(code, add):
    for m in re.finditer(r"\.\s*setIncludePayload\s*\(\s*true\s*\)", code):
        add("PCI003", "warn", line_of(code, m.start()), "request logging filter includes payloads")


def check_money(code, add):
    money_context = bool(_MONEY_CONTEXT.search(code))
    for m in re.finditer(r"\b(double|float|Double|Float)\s+([A-Za-z_$][\w$]*)\s*[=;,)(:]", code):
        if is_money_name(m.group(2), money_context):
            add("MON001", "error", line_of(code, m.start()),
                f"monetary value `{m.group(2)}` declared as {m.group(1)}")

    if "BigDecimal" not in code:
        return

    for m in re.finditer(r"\bnew\s+(?:java\.math\.)?BigDecimal\s*\(", code):
        close = match_close(code, m.end() - 1)
        args = split_args(code[m.end():close if close > 0 else m.end()])
        first = args[0] if args else ""
        if re.fullmatch(r"-?(?:\d+\.\d*|\.\d+|\d+(?:\.\d+)?[eE][+-]?\d+|\d+(?:\.\d+)?[dDfF])", first) \
                or re.search(r"\.\s*(?:doubleValue|floatValue)\b", first):
            add("MON002", "error", line_of(code, m.start()), f"new BigDecimal({first}) uses a binary double")

    for m in re.finditer(r"\.\s*(divide|setScale)\s*\(", code):
        close = match_close(code, m.end() - 1)
        args = split_args(code[m.end():close if close > 0 else m.end()])
        if any("ROUND_" in a for a in args):
            continue  # reported as MON005
        if any(re.search(r"RoundingMode|MathContext|\bmc\b|(?i:rounding)", a) for a in args[1:]):
            continue
        rule = "MON003" if m.group(1) == "divide" else "MON004"
        add(rule, "error", line_of(code, m.start()), f"{m.group(1)}() called without a RoundingMode")

    for m in re.finditer(r"\bROUND_(?:UP|DOWN|CEILING|FLOOR|HALF_UP|HALF_DOWN|HALF_EVEN|UNNECESSARY)\b", code):
        add("MON005", "error", line_of(code, m.start()), "deprecated BigDecimal.ROUND_* constant")

    for m in re.finditer(r"([A-Za-z_$][\w$]*)\s*(?:\(\s*\))?\s*\.\s*(doubleValue|floatValue)\s*\(\s*\)", code):
        if is_money_name(m.group(1), True):
            add("MON006", "warn", line_of(code, m.start()), f"`{m.group(1)}` converted with {m.group(2)}()")


def scan_java(path, raw):
    code = blank_code(raw)
    findings = []

    def add(rule, sev, line, msg):
        findings.append(Finding(rule, sev, path, line, msg))

    check_sensitive_sinks(code, add)
    check_tostring_leaks(raw, code, add)
    check_request_logging(code, add)
    check_money(code, add)
    return findings


# ---------------------------------------------------------------------------
# Spring config rules (application*.yml / .yaml / .properties)


def flatten_yaml(text):
    """Yield (dotted.key, value, line) for scalar leaves. Enough for Spring config;
    lists and flow mappings are skipped."""
    stack = []
    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s in ("---", "..."):
            stack = []
            continue
        if s.startswith("-"):
            continue
        m = re.match(r"^(\s*)(?:\"([^\"]+)\"|'([^']+)'|([^:#\s][^:#]*?))\s*:(?:\s+(.*))?$", line)
        if not m:
            continue
        indent = len(m.group(1))
        key = (m.group(2) or m.group(3) or m.group(4)).strip().strip("[]")
        val = re.sub(r"\s+#.*$", "", m.group(5) or "").strip().strip("\"'")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if val in ("", "|", ">"):
            stack.append((indent, key))
        else:
            yield ".".join([k for _, k in stack] + [key]), val, no


def flatten_properties(text):
    for no, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*([^#!\s=:][^=:]*?)\s*[=:]\s*(.*?)\s*$", line)
        if m:
            yield m.group(1).replace("[", "").replace("]", ""), m.group(2), no


BIND_LOGGERS = ("org.hibernate.orm.jdbc.bind", "org.hibernate.type.descriptor", "org.hibernate.type")
WIRE_LOGGERS = ("org.apache.http.wire", "org.apache.http.headers", "org.apache.hc.client5.http.wire",
                "org.apache.hc.client5.http.headers", "reactor.netty.http.client", "reactor.netty.http.server",
                "org.zalando.logbook", "okhttp3", "org.springframework.web.client",
                "org.springframework.web.reactive.function.client")
VERBOSE = ("debug", "trace", "all")


def scan_config(path, raw):
    rows = flatten_properties(raw) if path.endswith(".properties") else flatten_yaml(raw)
    findings = []
    for key, val, no in rows:
        k, v = key.lower(), val.lower()

        def add(rule, sev, msg):
            findings.append(Finding(rule, sev, path, no, msg))

        if re.search(r"(?:^|\.)show[-_]?sql$", k) and v == "true":
            add("CFG001", "warn", f"{key}: {val}")
        elif re.search(r"log[-_]?request[-_]?details$", k) and v == "true":
            add("CFG004", "error", f"{key}: {val}")
        elif re.search(r"(?:^|\.)(?:feign|openfeign)\.client\.config\..*\.logger[-_]?level$", k) and v == "full":
            add("CFG003", "error", f"Feign logger level FULL logs request/response bodies ({key})")
        elif k == "server.error.include-stacktrace" and v == "always":
            add("CFG006", "warn", f"{key}: {val}")
        elif k.startswith("logging.level."):
            logger = k[len("logging.level."):]
            if logger == "root":
                if v in VERBOSE:
                    add("CFG005", "warn", f"root logger at {val}")
            elif v in ("trace", "all") and any(logger.startswith(b) for b in BIND_LOGGERS):
                add("CFG002", "error", f"{key}: {val} logs bound SQL parameter values")
            elif v in VERBOSE and any(logger.startswith(w) for w in WIRE_LOGGERS):
                add("CFG003", "error", f"{key}: {val} logs HTTP bodies/headers")
            elif v in VERBOSE and logger.count(".") >= 2 and any(w.startswith(logger + ".") for w in WIRE_LOGGERS):
                add("CFG003", "warn", f"{key}: {val} also enables body logging in child loggers")
    return findings


# ---------------------------------------------------------------------------
# Driver

CONFIG_NAME = re.compile(r"^(?:application|bootstrap)(?:[-.][\w.-]+)?\.(?:ya?ml|properties)$")
_IGNORE = re.compile(r"pci-shield:ignore\b([\s:,]*(?:[A-Z]{3}\d{3}[\s,]*)*)")
SKIP_DIRS = {".git", "target", "build", "out", "node_modules", ".gradle", ".idea", ".mvn"}


def applies_to(path):
    base = os.path.basename(path)
    return base.endswith(".java") or bool(CONFIG_NAME.match(base))


def suppressed(lines, f):
    for idx in (f.line - 1, f.line - 2):
        if 0 <= idx < len(lines):
            m = _IGNORE.search(lines[idx])
            if m:
                rules = re.findall(r"[A-Z]{3}\d{3}", m.group(1))
                if not rules or f.rule in rules:
                    return True
    return False


def scan_file(path):
    if not applies_to(path):
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return []
    findings = scan_java(path, raw) if path.endswith(".java") else scan_config(path, raw)
    lines = raw.splitlines()
    seen, out = set(), []
    for f in sorted(findings, key=lambda f: (f.line, f.rule)):
        key = (f.rule, f.line)
        if key not in seen and not suppressed(lines, f):
            seen.add(key)
            out.append(f)
    return out


def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in sorted(files):
                    full = os.path.join(root, name)
                    if applies_to(full):
                        yield full
        else:
            yield p


def render(findings):
    lines = [f.format() for f in findings]
    rules = list(dict.fromkeys(f.rule for f in findings))
    lines.append("")
    lines += [f"  {r}: {HINTS[r]}" for r in rules]
    return "\n".join(lines)


def hook_main():
    if os.environ.get("PCI_SHIELD_DISABLE") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    path = (payload.get("tool_input") or {}).get("file_path")
    if not path:
        return 0
    if not os.path.isabs(path):
        path = os.path.join(payload.get("cwd") or os.getcwd(), path)
    findings = scan_file(path)
    errors = [f for f in findings if f.severity == "error"]
    if errors:
        sys.stderr.write(
            f"pci-shield: {len(errors)} blocking issue(s) in {path}. Fix them now. If one is a "
            "false positive, add `// pci-shield:ignore <RULE> -- <reason>` on that line.\n\n"
            + render(findings) + "\n")
        return 2
    if findings:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "pci-shield warnings (non-blocking):\n" + render(findings)}}))
    return 0


def cli_main(argv):
    findings = [f for p in iter_files(argv or ["."]) for f in scan_file(p)]
    if findings:
        print(render(findings))
    errors = sum(f.severity == "error" for f in findings)
    print(f"\npci-shield: {errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    sys.exit(hook_main() if args[:1] == ["--hook"] else cli_main(args))
