import unittest
import os
import base64
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from app.codex_runner import build_prompt, command_string
from app.config import Settings
from app.manager import JobManager
from app.pty_worker import TERMINAL_RESPONSES
from app.result_parser import RESULT_PATTERN, extract_result_paths
from app.store import StateStore
from app.tmux_runner import TerminalRunner, TerminalSnapshot, TerminalTarget
from app.uploads import create_upload


class ServiceTests(unittest.TestCase):
    def test_prompt_contains_image_gen(self):
        prompt = build_prompt("Image Gen", "batch_abc", 0, "draw a cat")
        self.assertIn("Image Gen", prompt)
        self.assertIn("draw a cat", prompt)

    def test_prompt_contains_reference_images(self):
        prompt = build_prompt("$imagegen", "batch_abc", 0, "draw a cat", ["/tmp/ref.png", "https://example.test/ref.jpg"])
        self.assertIn("Reference images:", prompt)
        self.assertIn("- /tmp/ref.png", prompt)
        self.assertIn("- https://example.test/ref.jpg", prompt)

    def test_command_string_quotes(self):
        settings = Settings.load()
        job = type("J", (), {
            "batch_id": "batch_1",
            "index": 0,
            "prompt": "hello world",
            "workdir": str(settings.default_workdir),
        })()
        cmd = command_string(job, settings)
        self.assertIn("codex", cmd)
        self.assertIn("hello world", cmd)
        self.assertIn("HOME=", cmd)
        self.assertIn("CODEX_HOME=", cmd)
        self.assertIn(str(settings.codex_user_home), cmd)
        self.assertIn(str(settings.codex_home), cmd)
        self.assertIn("TERM=xterm-256color", cmd)

    def test_terminal_names(self):
        settings = Settings.load()
        runner = TerminalRunner(settings)
        names = runner.names_for("batch_1234567890", 2)
        self.assertTrue(names.session_name.startswith("image-gen-"))
        self.assertEqual(names.window_name, "img-3")

    def test_terminal_runner_uses_pty_worker(self):
        if os.name != "posix":
            self.skipTest("PTY worker test requires a POSIX host")
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = Settings(
                root=tmp_path,
                data_dir=tmp_path / "data",
                codex_bin=Path(sys.executable),
                codex_home=tmp_path / "codex-home",
                codex_user_home=tmp_path,
                terminal_bin="python3",
                tmux_bin="tmux",
                host="127.0.0.1",
                port=0,
                batch_prefix="$imagegen",
                default_workdir=tmp_path,
                job_timeout_seconds=30,
                max_concurrency=2,
                cors_origin="*",
                frontend_dist_dir=tmp_path / "frontend" / "dist",
                file_roots=(tmp_path / "data", tmp_path, tmp_path / "codex-home" / "generated_images"),
                generated_images_dir=tmp_path / "codex-home" / "generated_images",
                results_dir=tmp_path / "data" / "results",
            )
            settings.ensure_dirs()
            runner = TerminalRunner(settings)
            log_path = settings.data_dir / "test-pty.log"
            proc = runner.start(
                runner.names_for("batch_pty", 0),
                settings.root,
                "printf 'hello from pty'",
                log_path,
            )
            self.assertEqual(proc.wait(timeout=5), 0)
            self.assertIn("hello from pty", log_path.read_text())

    def test_result_pattern_matches_generated_image_path(self):
        output = "file:///tmp/codex-home/generated_images/abc/ig_test.png"
        self.assertIsNotNone(RESULT_PATTERN.search(output))
        self.assertEqual(extract_result_paths(output), ["/tmp/codex-home/generated_images/abc/ig_test.png"])

    def test_pty_worker_handles_keyboard_protocol_query(self):
        self.assertEqual(TERMINAL_RESPONSES[b"\x1b[?u"], b"\x1b[?0u")

    def test_discover_generated_images_fallback(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = Settings(
                root=tmp_path,
                data_dir=tmp_path / "data",
                codex_bin=Path(sys.executable),
                codex_home=tmp_path / "codex-home",
                codex_user_home=tmp_path,
                terminal_bin="python3",
                tmux_bin="tmux",
                host="127.0.0.1",
                port=0,
                batch_prefix="$imagegen",
                default_workdir=tmp_path,
                job_timeout_seconds=30,
                max_concurrency=2,
                cors_origin="*",
                frontend_dist_dir=tmp_path / "frontend" / "dist",
                file_roots=(tmp_path / "data", tmp_path, tmp_path / "codex-home" / "generated_images"),
                generated_images_dir=tmp_path / "codex-home" / "generated_images",
                results_dir=tmp_path / "data" / "results",
            )
            settings.ensure_dirs()
            settings.codex_home.mkdir(parents=True, exist_ok=True)
            (settings.codex_home / "auth.json").write_text("{}", encoding="utf-8")
            generated_dir = settings.generated_images_dir / "019dd316-6e53-70b1-a44a-b24ef9fa33dc"
            generated_dir.mkdir(parents=True, exist_ok=True)
            image_path = generated_dir / "ig_test.png"
            image_path.write_bytes(b"fake-png-bytes")
            manager = JobManager(settings, StateStore(settings.data_dir / "state.json"))
            job = {
                "started_at": "2026-04-28T08:00:00+00:00",
            }
            self.assertIn(str(image_path), manager._discover_generated_images(job))

    def test_batch_with_multiple_prompts_creates_multiple_jobs(self):
        class FakeProc:
            returncode = 0

            def poll(self):
                return 0

        class FakeTerminal:
            def __init__(self):
                self.started = []

            def names_for(self, batch_id, index):
                return TerminalTarget(session_name=f"fake-{batch_id}-{index}", window_name=f"img-{index + 1}")

            def start(self, target, cwd, command, log_path):
                self.started.append((target, cwd, command, log_path))
                return FakeProc()

            def capture(self, log_path):
                return TerminalSnapshot(output="")

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = Settings(
                root=tmp_path,
                data_dir=tmp_path / "data",
                codex_bin=Path(sys.executable),
                codex_home=tmp_path / ".codex",
                codex_user_home=tmp_path,
                terminal_bin="python3",
                tmux_bin="tmux",
                host="127.0.0.1",
                port=0,
                batch_prefix="$imagegen",
                default_workdir=tmp_path,
                job_timeout_seconds=30,
                max_concurrency=4,
                cors_origin="*",
                frontend_dist_dir=tmp_path / "frontend" / "dist",
                file_roots=(tmp_path / "data", tmp_path, tmp_path / ".codex" / "generated_images"),
                generated_images_dir=tmp_path / ".codex" / "generated_images",
                results_dir=tmp_path / "data" / "results",
            )
            settings.ensure_dirs()
            settings.codex_home.mkdir(parents=True, exist_ok=True)
            (settings.codex_home / "auth.json").write_text("{}", encoding="utf-8")
            manager = JobManager(settings, StateStore(settings.data_dir / "state.json"))
            fake_terminal = FakeTerminal()
            manager.terminal = fake_terminal
            manager._watch_job = lambda job_id, proc: None
            batch = manager.submit_batch({"prompts": ["draw a cat", "draw a dog"], "workdir": str(tmp_path)})

            self.assertEqual(batch["total"], 2)
            self.assertEqual(len(batch["jobs"]), 2)
            self.assertEqual(len(fake_terminal.started), 2)
            self.assertNotEqual(batch["jobs"][0]["session_name"], batch["jobs"][1]["session_name"])
            self.assertIn("draw a cat", batch["jobs"][0]["command"])
            self.assertIn("draw a dog", batch["jobs"][1]["command"])

    def test_upload_and_shared_reference_images(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            settings = Settings(
                root=tmp_path,
                data_dir=tmp_path / "data",
                codex_bin=Path(sys.executable),
                codex_home=tmp_path / ".codex",
                codex_user_home=tmp_path,
                terminal_bin="python3",
                tmux_bin="tmux",
                host="127.0.0.1",
                port=0,
                batch_prefix="$imagegen",
                default_workdir=tmp_path,
                job_timeout_seconds=30,
                max_concurrency=4,
                cors_origin="*",
                frontend_dist_dir=tmp_path / "frontend" / "dist",
                file_roots=(tmp_path / "data", tmp_path, tmp_path / ".codex" / "generated_images"),
                generated_images_dir=tmp_path / ".codex" / "generated_images",
                results_dir=tmp_path / "data" / "results",
            )
            settings.ensure_dirs()
            settings.codex_home.mkdir(parents=True, exist_ok=True)
            (settings.codex_home / "auth.json").write_text("{}", encoding="utf-8")
            store = StateStore(settings.data_dir / "state.json")
            upload = create_upload(
                {
                    "filename": "ref.png",
                    "mime_type": "image/png",
                    "data": base64.b64encode(b"fake-png-bytes").decode(),
                },
                settings,
                store,
            )
            manager = JobManager(settings, store)
            manager.terminal = type(
                "FakeTerminal",
                (),
                {
                    "names_for": lambda self, batch_id, index: TerminalTarget(f"fake-{batch_id}-{index}", f"img-{index + 1}"),
                    "start": lambda self, target, cwd, command, log_path: type("FakeProc", (), {"poll": lambda self: 0, "returncode": 0})(),
                    "capture": lambda self, log_path: TerminalSnapshot(output=""),
                },
            )()
            manager._watch_job = lambda job_id, proc: None
            batch = manager.submit_batch(
                {
                    "prompts": ["use the reference style", "use the same composition"],
                    "workdir": str(tmp_path),
                    "reference_image_ids": [upload["image_id"]],
                    "reference_images": ["https://example.test/extra-ref.jpg"],
                }
            )

            for job in batch["jobs"]:
                self.assertIn(upload["path"], job["reference_images"])
                self.assertIn("https://example.test/extra-ref.jpg", job["reference_images"])
                self.assertIn(upload["path"], job["command"])
                self.assertIn("https://example.test/extra-ref.jpg", job["command"])


if __name__ == "__main__":
    unittest.main()
