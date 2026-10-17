"""Logic behind the pci-shield-verify MCP server. Standard library only (PyYAML
optional, for YAML OpenAPI specs) so it can be unit-tested without the MCP SDK."""
import glob
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

MONEY_PATH = re.compile(r"(?i)payment|checkout|charge|refund|transfer|payout|top-?up|capture|withdraw|order|invoice")


# ---------------------------------------------------------------------------
# docker_status


def docker_status():
    """Whether a Docker daemon is reachable (Testcontainers needs one)."""
    if not shutil.which("docker"):
        return {"available": False, "detail": "docker CLI not found on PATH"}
    try:
        res = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                             capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"available": False, "detail": "docker version timed out"}
    if res.returncode == 0 and res.stdout.strip():
        return {"available": True, "server_version": res.stdout.strip()}
    return {"available": False, "detail": (res.stderr or res.stdout).strip()[:300]}


# ---------------------------------------------------------------------------
# openapi_idempotency_check


def _load_spec(source):
    if re.match(r"https?://", source):
        with urllib.request.urlopen(source, timeout=20) as resp:
            text = resp.read().decode("utf-8")
    else:
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
    try:
        return json.loads(text)
    except ValueError:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError("spec is not JSON and PyYAML is not installed for YAML specs") from exc
        return yaml.safe_load(text)


def _resolve(spec, node):
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return node
        target = spec
        for part in ref[2:].split("/"):
            target = target.get(part.replace("~1", "/").replace("~0", "~"), {})
        node = target
    return node


def _has_idempotency_header(spec, params):
    for p in params or []:
        p = _resolve(spec, p)
        if p.get("in") == "header" and str(p.get("name", "")).lower() == "idempotency-key":
            return True
    return False


def openapi_idempotency_check(source):
    """Money-moving POST/PATCH operations that don't declare an Idempotency-Key header."""
    spec = _load_spec(source)
    checked, missing = [], []
    for path, item in (spec.get("paths") or {}).items():
        item = _resolve(spec, item)
        for method in ("post", "patch"):
            op = item.get(method)
            if not op:
                continue
            text = " ".join([path, op.get("operationId", ""), op.get("summary", ""), " ".join(op.get("tags", []))])
            if not MONEY_PATH.search(text):
                continue
            entry = f"{method.upper()} {path}"
            checked.append(entry)
            if not (_has_idempotency_header(spec, item.get("parameters"))
                    or _has_idempotency_header(spec, op.get("parameters"))):
                missing.append(entry)
    return {"checked": checked, "missing_idempotency_key": missing, "ok": not missing}


# ---------------------------------------------------------------------------
# concurrency_probe


def concurrency_probe(url, body, method="POST", headers=None, concurrency=10, id_field="id", timeout_s=30.0):
    """Send `concurrency` identical requests at the same moment. A correct idempotent
    endpoint (same Idempotency-Key in `headers`) creates exactly one resource."""
    headers = {"Content-Type": "application/json", **(headers or {})}
    data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
    barrier = threading.Barrier(concurrency)

    def fire(_):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        barrier.wait()
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                status, payload = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            status, payload = err.code, err.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError) as err:
            status, payload = None, str(err)
        return status, payload, round((time.monotonic() - start) * 1000)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(fire, range(concurrency)))

    ids = set()
    for status, payload, _ in results:
        if status and 200 <= status < 300:
            try:
                value = json.loads(payload).get(id_field)
            except (ValueError, AttributeError):
                value = None
            if value is not None:
                ids.add(str(value))
    successes = sum(1 for s, _, _ in results if s and 200 <= s < 300)
    if successes == 0:
        verdict = "NO_SUCCESS"
    elif len(ids) > 1:
        verdict = "DUPLICATES_CREATED"
    elif len(ids) == 1:
        verdict = "SINGLE_RESOURCE"
    else:
        verdict = "UNKNOWN (no id field in 2xx responses)"
    return {
        "verdict": verdict,
        "requests": concurrency,
        "status_counts": {str(k): v for k, v in Counter(s for s, _, _ in results).items()},
        "distinct_resource_ids": sorted(ids),
        "distinct_bodies": len({p for _, p, _ in results}),
        "max_latency_ms": max(ms for _, _, ms in results),
        "sample_error": next((p[:300] for s, p, _ in results if not s or s >= 500), None),
    }


# ---------------------------------------------------------------------------
# run_integration_tests


def _parse_junit_reports(patterns):
    totals = Counter()
    failures = []
    for pattern in patterns:
        for path in glob.glob(pattern, recursive=True):
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
            for suite in suites:
                for key in ("tests", "failures", "errors", "skipped"):
                    totals[key] += int(suite.get(key, 0) or 0)
                for case in suite.findall("testcase"):
                    for kind in ("failure", "error"):
                        node = case.find(kind)
                        if node is not None:
                            failures.append({
                                "test": f"{case.get('classname')}.{case.get('name')}",
                                "kind": kind,
                                "message": (node.get("message") or node.text or "")[:500],
                            })
    return dict(totals), failures


def run_integration_tests(project_dir, test_pattern=None, java_home=None, timeout_s=900):
    """Run the project's tests (Maven or Gradle) and return parsed JUnit results."""
    project_dir = os.path.abspath(project_dir)
    env = dict(os.environ)
    if java_home:
        env["JAVA_HOME"] = java_home
    if os.path.exists(os.path.join(project_dir, "pom.xml")):
        mvn = "./mvnw" if os.path.exists(os.path.join(project_dir, "mvnw")) else "mvn"
        cmd = [mvn, "-B", "verify"]
        if test_pattern:
            cmd += [f"-Dtest={test_pattern}", f"-Dit.test={test_pattern}",
                    "-Dsurefire.failIfNoSpecifiedTests=false", "-Dfailsafe.failIfNoSpecifiedTests=false"]
        reports = [os.path.join(project_dir, "target", d, "*.xml") for d in ("surefire-reports", "failsafe-reports")]
        clean = [os.path.join(project_dir, "target", d) for d in ("surefire-reports", "failsafe-reports")]
    elif any(os.path.exists(os.path.join(project_dir, f)) for f in ("build.gradle", "build.gradle.kts")):
        gradle = "./gradlew" if os.path.exists(os.path.join(project_dir, "gradlew")) else "gradle"
        cmd = [gradle, "test"] + (["--tests", test_pattern] if test_pattern else [])
        reports = [os.path.join(project_dir, "build", "test-results", "**", "*.xml")]
        clean = [os.path.join(project_dir, "build", "test-results")]
    else:
        return {"ok": False, "error": "no pom.xml or build.gradle(.kts) in " + project_dir}

    for d in clean:
        shutil.rmtree(d, ignore_errors=True)  # don't report stale results from an earlier run
    docker = docker_status()
    try:
        res = subprocess.run(cmd, cwd=project_dir, env=env, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout_s}s", "command": " ".join(cmd)}
    totals, failures = _parse_junit_reports(reports)
    out = {
        "ok": res.returncode == 0 and not failures,
        "command": " ".join(cmd),
        "exit_code": res.returncode,
        "totals": totals,
        "failures": failures,
        "docker_available": docker["available"],
    }
    if not docker["available"] and totals.get("skipped"):
        out["note"] = ("Docker is not available, so Testcontainers tests were probably skipped "
                       "(disabledWithoutDocker). Skipped tests prove nothing about rollback or idempotency.")
    if res.returncode != 0 and not failures:
        out["output_tail"] = (res.stdout + res.stderr)[-2000:]
    return out
