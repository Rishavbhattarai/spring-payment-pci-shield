"""Run: python3 -m unittest discover -s tests"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "mcp"))

import verify_tools  # noqa: E402

SPEC = os.path.join(HERE, "fixtures", "openapi.json")
JDK25 = "/Library/Java/JavaVirtualMachines/jdk-25.jdk/Contents/Home"


class IntegrationTestEnvTest(unittest.TestCase):
    """run_integration_tests inherits the environment instead of passing a copy of it,
    and builds a modified one only when JAVA_HOME is overridden."""

    def _captured_env(self, **kwargs):
        seen = {}
        def fake_run(cmd, **kw):
            seen["env"] = kw.get("env", "unset")
            class R: returncode, stdout, stderr = 0, "", ""
            return R()
        project = tempfile.mkdtemp()
        open(os.path.join(project, "pom.xml"), "w").close()
        original = verify_tools.subprocess.run
        verify_tools.subprocess.run = fake_run
        try:
            verify_tools.run_integration_tests(project, **kwargs)
        finally:
            verify_tools.subprocess.run = original
            shutil.rmtree(project, ignore_errors=True)
        return seen["env"]

    def test_inherits_environment_by_default(self):
        self.assertIsNone(self._captured_env())

    def test_java_home_override_sets_only_that_variable(self):
        env = self._captured_env(java_home="/opt/jdk")
        self.assertEqual(env["JAVA_HOME"], "/opt/jdk")
        self.assertEqual(env.get("PATH"), os.environ.get("PATH"))


class IntegrationTestSkipTest(unittest.TestCase):
    """A run where every test was skipped must not report ok, even when Docker is reachable."""

    def _run(self, skipped, docker_up):
        project = tempfile.mkdtemp()
        open(os.path.join(project, "pom.xml"), "w").close()
        report_dir = os.path.join(project, "target", "failsafe-reports")
        def fake_run(cmd, **kw):
            os.makedirs(report_dir, exist_ok=True)
            with open(os.path.join(report_dir, "TEST-x.xml"), "w") as fh:
                fh.write(f'<testsuite tests="2" failures="0" errors="0" skipped="{skipped}"></testsuite>')
            class R: returncode, stdout, stderr = 0, "", "Could not find a valid Docker environment"
            return R()
        saved = verify_tools.subprocess.run, verify_tools.docker_status
        verify_tools.subprocess.run = fake_run
        verify_tools.docker_status = lambda: {"available": docker_up}
        try:
            return verify_tools.run_integration_tests(project)
        finally:
            verify_tools.subprocess.run, verify_tools.docker_status = saved
            shutil.rmtree(project, ignore_errors=True)

    def test_all_skipped_with_docker_up_is_not_ok(self):
        out = self._run(skipped=2, docker_up=True)
        self.assertFalse(out["ok"])
        self.assertIn("Testcontainers may not reach it", out["note"])
        self.assertIn("Could not find a valid Docker environment", out["output_tail"])

    def test_all_skipped_without_docker_is_not_ok(self):
        out = self._run(skipped=2, docker_up=False)
        self.assertFalse(out["ok"])
        self.assertIn("Docker is not available", out["note"])

    def test_nothing_skipped_is_ok(self):
        out = self._run(skipped=0, docker_up=True)
        self.assertTrue(out["ok"])
        self.assertNotIn("note", out)

class OpenApiTest(unittest.TestCase):
    def test_flags_money_posts_without_header(self):
        res = verify_tools.openapi_idempotency_check(SPEC)
        self.assertEqual(res["missing_idempotency_key"], ["POST /payments"])
        self.assertIn("POST /payments/{id}/refunds", res["checked"])  # header via path-level $ref
        self.assertIn("POST /checkout", res["checked"])               # case-insensitive header name
        self.assertNotIn("POST /users", res["checked"])               # not money-moving
        self.assertFalse(res["ok"])

    def test_yaml_spec(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        with open(SPEC) as fh:
            spec = json.load(fh)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            yaml.safe_dump(spec, fh)
        try:
            self.assertEqual(verify_tools.openapi_idempotency_check(fh.name)["missing_idempotency_key"],
                             ["POST /payments"])
        finally:
            os.unlink(fh.name)


def serve(idempotent):
    """Tiny payments API. Naive mode creates a new id per request; idempotent mode
    keys on the Idempotency-Key header."""
    store, lock = {}, threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            key = self.headers.get("Idempotency-Key")
            with lock:
                if idempotent and key in store:
                    pid = store[key]
                else:
                    pid = str(uuid.uuid4())
                    store[key] = pid
            body = json.dumps({"id": pid, "status": "CAPTURED"}).encode()
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class ConcurrencyProbeTest(unittest.TestCase):
    def probe(self, idempotent):
        server = serve(idempotent)
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/payments"
            return verify_tools.concurrency_probe(url, {"amount": "19.99"}, headers={"Idempotency-Key": "k-1"},
                                                  concurrency=8)
        finally:
            server.shutdown()
            server.server_close()

    def test_naive_endpoint_creates_duplicates(self):
        res = self.probe(idempotent=False)
        self.assertEqual(res["verdict"], "DUPLICATES_CREATED")
        self.assertEqual(len(res["distinct_resource_ids"]), 8)
        self.assertEqual(res["status_counts"], {"201": 8})

    def test_idempotent_endpoint_creates_one(self):
        res = self.probe(idempotent=True)
        self.assertEqual(res["verdict"], "SINGLE_RESOURCE")

    def test_unreachable(self):
        res = verify_tools.concurrency_probe("http://127.0.0.1:9/payments", "{}", concurrency=2, timeout_s=2)
        self.assertEqual(res["verdict"], "NO_SUCCESS")


class IntegrationTestRunnerTest(unittest.TestCase):
    def test_no_build_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(verify_tools.run_integration_tests(d)["ok"])

    @unittest.skipUnless(shutil.which("mvn") and os.environ.get("PCI_SHIELD_SLOW_TESTS") == "1",
                         "set PCI_SHIELD_SLOW_TESTS=1 to run Maven against the sample app")
    def test_sample_app(self):
        with tempfile.TemporaryDirectory() as d:
            app = os.path.join(d, "payment-service")
            shutil.copytree(os.path.join(ROOT, "examples", "payment-service"), app,
                            ignore=shutil.ignore_patterns("target"))
            res = verify_tools.run_integration_tests(app, java_home=JDK25 if os.path.isdir(JDK25) else None)
        self.assertTrue(res["ok"], res)
        self.assertGreaterEqual(res["totals"]["tests"], 5)
        if not res["docker_available"]:
            self.assertIn("note", res)


class DockerStatusTest(unittest.TestCase):
    def test_shape(self):
        self.assertIn("available", verify_tools.docker_status())


if __name__ == "__main__":
    unittest.main()
