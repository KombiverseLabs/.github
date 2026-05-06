import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "kombi-local-gate.mjs"
BOOTSTRAP = ROOT / "scripts" / "kombi-bootstrap-local.ps1"
REHEARSAL = ROOT / "scripts" / "kombi-dress-rehearsal.ps1"
MANIFEST = ROOT / "local-dev" / "kombify-gates.json"
DOCS = ROOT / "docs" / "local-development-deployment.md"
GITIGNORE = ROOT / ".gitignore"
SIMULATE_MISE = ROOT.parent / "kombify-simulate" / "mise.toml"
SIMULATE_SECRET_HELPER = ROOT.parent / "kombify-simulate" / "scripts" / "mise-env-secret.mjs"
BLOG_MISE = ROOT.parent / "kombify-Blog" / "mise.toml"
CLOUD_MISE = ROOT.parent / "kombify-Cloud" / "mise.toml"
AI_MISE = ROOT.parent / "kombify-AI" / "mise.toml"
CORE_ASPIRE_APPHOST = ROOT.parent / "kombify-Core" / "aspire" / "apphost.cs"
CLOUD_ASPIRE_APPHOST = ROOT.parent / "kombify-Cloud" / "aspire" / "apphost.cs"
CLOUD_INITIAL_MIGRATION = ROOT.parent / "kombify-Cloud" / "prisma" / "migrations" / "0_init" / "migration.sql"
CLOUD_PREVIEW_DOCKERFILE = ROOT.parent / "kombify-Cloud" / "Dockerfile.preview"
CLOUD_REFRESH_TOKEN_MIGRATION = (
    ROOT.parent / "kombify-Cloud" / "prisma" / "migrations" / "20260325_add_refresh_tokens" / "migration.sql"
)
CLOUD_TOOL_ENTITLEMENT_MIGRATION = (
    ROOT.parent
    / "kombify-Cloud"
    / "prisma"
    / "migrations"
    / "20260325_add_tool_entitlements_and_device_codes"
    / "migration.sql"
)
CLOUD_ACTIVITY_ACTOR_MIGRATION = (
    ROOT.parent
    / "kombify-Cloud"
    / "prisma"
    / "migrations"
    / "20260504_add_activity_actor_fields"
    / "migration.sql"
)


REQUIRED_TASKS = [
    "setup",
    "doctor",
    "build",
    "test",
    "check",
    "health",
    "preview:local",
    "preflight:quick",
    "preflight:release",
    "preflight:deploy",
    "aspire:start",
    "aspire:full",
]


def node_bin() -> str:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not available")
    return node


def pwsh_bin() -> str:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        raise unittest.SkipTest("PowerShell is not available")
    return pwsh


def write_manifest(path: pathlib.Path, repo_path: str = "kombify-demo") -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "requiredMiseTasks": REQUIRED_TASKS,
                "aspireProfiles": {
                    "local": "local-minimal",
                    "saas": "local-saas-like",
                    "selfhosted": "local-minimal",
                    "hybrid": "local-hybrid",
                    "integration": "integration-ghcr",
                },
                "repos": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "path": repo_path,
                        "components": [
                            {
                                "id": "app",
                                "packaging": "standalone",
                                "runtime": "source",
                                "modes": ["local", "saas", "selfhosted", "hybrid"],
                                "healthUrls": ["http://127.0.0.1:65535/health"],
                                "gates": {
                                    "quick": {"miseTask": "preflight:quick"},
                                    "standard": {"miseTask": "preflight:release"},
                                    "full": {"aspireProfile": "local-hybrid"},
                                },
                                "aspire": {
                                    "focusService": "demo",
                                    "tasks": {"hybrid": "aspire:hybrid"},
                                },
                            }
                        ],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def beads_active_repos() -> list[pathlib.Path]:
    return sorted(
        [
            child
            for child in ROOT.parent.iterdir()
            if child.is_dir() and (child / ".beads" / "issues.jsonl").exists()
            and not (child / ".git").is_file()
        ],
        key=lambda path: path.name.lower(),
    )


class LocalGateContractTest(unittest.TestCase):
    def run_cli(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [node_bin(), str(CLI), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )

    def run_pwsh(self, script: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [pwsh_bin(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_doctor_reports_missing_mise_clearly(self) -> None:
        env = os.environ.copy()
        env["PATH"] = str(pathlib.Path(node_bin()).parent)

        result = self.run_cli("doctor", "--json", env=env)

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        mise = next(tool for tool in payload["tools"] if tool["name"] == "mise")
        self.assertFalse(mise["found"])
        self.assertTrue(mise["required"])
        self.assertIn("mise", mise["installHint"].lower())
        dotnet = next(tool for tool in payload["tools"] if tool["name"] == ".NET SDK")
        self.assertFalse(dotnet["found"])
        self.assertTrue(dotnet["required"])
        self.assertIn("aspire", dotnet["installHint"].lower())
        doppler = next(tool for tool in payload["tools"] if tool["name"] == "Doppler CLI")
        self.assertFalse(doppler["found"])
        self.assertTrue(doppler["required"])
        self.assertIn("doppler", doppler["installHint"].lower())

    def test_report_redacts_secret_like_environment_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = pathlib.Path(tmp) / "doctor-report.json"
            env = os.environ.copy()
            env["PATH"] = str(pathlib.Path(node_bin()).parent)
            env["KOMBIFY_TEST_SECRET"] = "super-secret-value"

            self.run_cli("doctor", "--json", "--report", str(report), env=env)

            report_text = report.read_text(encoding="utf-8")
            self.assertNotIn("super-secret-value", report_text)
            self.assertIn('"KOMBIFY_TEST_SECRET": "[REDACTED]"', report_text)

    def test_gate_report_includes_local_preflight_receipt(self) -> None:
        if not shutil.which("git"):
            raise unittest.SkipTest("git is not available")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            (repo / "mise.toml").write_text(
                '[tasks."preflight:quick"]\nrun = "echo quick"\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "init"], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            subprocess.run(["git", "config", "user.email", "local@example.test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Local Test"], cwd=repo, check=True)
            subprocess.run(["git", "add", "mise.toml"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            manifest = workspace / "manifest.json"
            write_manifest(manifest)
            report = workspace / "reports" / "quick-receipt.json"

            result = self.run_cli(
                "run",
                "demo",
                "--gate",
                "quick",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--report",
                str(report),
                "--json",
            )
            receipt = json.loads(report.read_text(encoding="utf-8"))["receipt"]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(receipt["schema"], "kombify-local-preflight-receipt")
        self.assertEqual(receipt["repo"], "demo")
        self.assertEqual(receipt["gate"], "quick")
        self.assertEqual(receipt["status"], "dry-run")
        self.assertRegex(receipt["git"]["sha"], r"^[0-9a-f]{40}$")
        self.assertFalse(receipt["git"]["dirty"])

    def test_audit_catches_missing_required_mise_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            (repo / "mise.toml").write_text(
                '[tasks.build]\nrun = "echo build"\n\n[tasks.test]\nrun = "echo test"\n',
                encoding="utf-8",
            )
            manifest = workspace / "manifest.json"
            write_manifest(manifest)

            result = self.run_cli(
                "audit",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["repos"][0]["id"], "demo")
        self.assertIn("setup", payload["repos"][0]["missingTasks"])
        self.assertIn("preflight:deploy", payload["repos"][0]["missingTasks"])

    def test_run_quick_gate_dry_run_delegates_to_mise_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            (repo / "mise.toml").write_text(
                '[tasks."preflight:quick"]\nrun = "echo quick"\n',
                encoding="utf-8",
            )
            manifest = workspace / "manifest.json"
            write_manifest(manifest)

            result = self.run_cli(
                "run",
                "demo",
                "--gate",
                "quick",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "dry-run")
        self.assertEqual(payload["source"], "mise")
        self.assertEqual(payload["command"], ["mise", "run", "preflight:quick"])

    def test_human_dry_run_formats_command_without_duplicate_source_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            (repo / "mise.toml").write_text(
                '[tasks."preflight:quick"]\nrun = "echo quick"\n',
                encoding="utf-8",
            )
            manifest = workspace / "manifest.json"
            write_manifest(manifest)

            result = self.run_cli(
                "run",
                "demo",
                "--gate",
                "quick",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry-run: mise run preflight:quick", result.stdout)
        self.assertNotIn("dry-run: mise mise run", result.stdout)

    def test_up_hybrid_dry_run_uses_repo_aspire_alias_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            (repo / "mise.toml").write_text(
                '[tasks."aspire:hybrid"]\nrun = "echo hybrid"\n',
                encoding="utf-8",
            )
            manifest = workspace / "manifest.json"
            write_manifest(manifest)

            result = self.run_cli(
                "up",
                "demo",
                "--mode",
                "hybrid",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "mise")
        self.assertEqual(payload["mode"], "hybrid")
        self.assertEqual(payload["command"], ["mise", "run", "aspire:hybrid"])

    def test_up_saas_dry_run_uses_central_aspire_start_for_aspire_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            (repo / "mise.toml").write_text(
                '[tasks."aspire:full"]\nrun = "echo old alias"\n',
                encoding="utf-8",
            )
            manifest = workspace / "manifest.json"
            write_manifest(manifest)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["aspireAppHost"] = "kombify-core/aspire/apphost.cs"
            apphost = workspace / "kombify-core" / "aspire"
            apphost.mkdir(parents=True)
            (apphost / "apphost.cs").write_text("// apphost", encoding="utf-8")
            component = payload["repos"][0]["components"][0]
            component["runtime"] = "aspire"
            component["aspire"]["profiles"] = {"saas": "local-saas-like"}
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_cli(
                "up",
                "demo",
                "--mode",
                "saas",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "aspire")
        self.assertEqual(payload["command"], ["dotnet", "run", "apphost.cs", "--no-restore"])
        self.assertEqual(payload["restoreCommand"], ["aspire", "restore", "--apphost", "apphost.cs", "--non-interactive"])
        self.assertEqual(payload["env"]["KOMBIFY_ASPIRE_PROFILE"], "local-saas-like")

    def test_up_integration_dry_run_uses_integration_ghcr_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            manifest = workspace / "manifest.json"
            write_manifest(manifest)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["aspireAppHost"] = "kombify-core/aspire/apphost.cs"
            apphost = workspace / "kombify-core" / "aspire"
            apphost.mkdir(parents=True)
            (apphost / "apphost.cs").write_text("// apphost", encoding="utf-8")
            payload["repos"][0]["components"][0]["runtime"] = "aspire"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_cli(
                "up",
                "demo",
                "--mode",
                "integration",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "aspire")
        self.assertEqual(payload["mode"], "integration")
        self.assertEqual(payload["env"]["KOMBIFY_ASPIRE_PROFILE"], "integration-ghcr")

    def test_up_local_dry_run_prefers_compose_for_docker_compose_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            (repo / "mise.toml").write_text(
                '[tasks."aspire:start"]\nrun = "echo aspire"\n',
                encoding="utf-8",
            )
            manifest = workspace / "manifest.json"
            write_manifest(manifest)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            component = payload["repos"][0]["components"][0]
            component["runtime"] = "docker-compose"
            component["composeFile"] = "docker-compose.yml"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_cli(
                "up",
                "demo",
                "--mode",
                "local",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "docker-compose")
        self.assertEqual(payload["command"], ["docker", "compose", "-f", "docker-compose.yml", "up", "-d", "--build", "--remove-orphans"])

    def test_down_aspire_dry_run_uses_central_aspire_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            manifest = workspace / "manifest.json"
            write_manifest(manifest)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["aspireAppHost"] = "kombify-core/aspire/apphost.cs"
            apphost = workspace / "kombify-core" / "aspire"
            apphost.mkdir(parents=True)
            (apphost / "apphost.cs").write_text("// apphost", encoding="utf-8")
            payload["repos"][0]["components"][0]["runtime"] = "aspire"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_cli(
                "down",
                "demo",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["source"], "aspire")
        self.assertEqual(payload["command"], ["aspire", "stop", "--apphost", "apphost.cs", "--non-interactive"])

    def test_smoke_dry_run_uses_manifest_health_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            manifest = workspace / "manifest.json"
            write_manifest(manifest)

            result = self.run_cli(
                "smoke",
                "demo",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "dry-run")
        self.assertEqual(payload["source"], "smoke")
        self.assertEqual(payload["urls"], ["http://127.0.0.1:65535/health"])

    def test_smoke_dry_run_uses_mode_specific_health_urls_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            manifest = workspace / "manifest.json"
            write_manifest(manifest)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            component = payload["repos"][0]["components"][0]
            component["healthUrlsByMode"] = {
                "local": ["http://127.0.0.1:5290/health"],
                "saas": ["http://127.0.0.1:5173/health"],
            }
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_cli(
                "smoke",
                "demo",
                "--mode",
                "saas",
                "--dry-run",
                "--workspace-root",
                str(workspace),
                "--manifest",
                str(manifest),
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "saas")
        self.assertEqual(payload["urls"], ["http://127.0.0.1:5173/health"])

    def test_smoke_runner_uses_node_http_client_without_abort_controller(self) -> None:
        cli = CLI.read_text(encoding="utf-8")
        self.assertIn('import http from "node:http"', cli)
        self.assertIn('import https from "node:https"', cli)
        self.assertNotIn("new AbortController", cli)

    def test_bootstrap_script_dry_run_prepares_repos_through_mise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            repo = workspace / "kombify-demo"
            repo.mkdir()
            manifest = workspace / "manifest.json"
            write_manifest(manifest)
            report = workspace / "bootstrap-report.json"

            result = self.run_pwsh(
                BOOTSTRAP,
                "-DryRun",
                "-SkipDoctor",
                "-SkipAudit",
                "-WorkspaceRoot",
                str(workspace),
                "-Manifest",
                str(manifest),
                "-Repo",
                "demo",
                "-ReportPath",
                str(report),
            )
            report_exists = report.exists()
            report_payload = json.loads(report.read_text(encoding="utf-8")) if report_exists else {}

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report_exists)
        commands = [" ".join(step["command"]) for step in report_payload["steps"]]
        self.assertIn("mise trust", commands)
        self.assertIn("mise install", commands)
        self.assertIn("mise run setup", commands)

    def test_dress_rehearsal_dry_run_records_core_probes_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            (workspace / "kombify-Blog").mkdir()
            (workspace / "kombify-Cloud").mkdir()
            (workspace / "kombify-Techstack").mkdir()
            manifest = workspace / "manifest.json"
            write_manifest(manifest, repo_path="kombify-Blog")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["repos"][0]["id"] = "kombify-blog"
            payload["repos"][0]["name"] = "Blog"
            payload["repos"].extend(
                [
                    {
                        "id": "kombify-cloud",
                        "name": "Cloud",
                        "path": "kombify-Cloud",
                        "components": [
                            {
                                "id": "portal",
                                "runtime": "aspire",
                                "packaging": "embedded",
                                "modes": ["saas"],
                                "healthUrls": ["http://127.0.0.1:65535/cloud"],
                                "gates": {"quick": {"miseTask": "preflight:quick"}},
                            }
                        ],
                    },
                    {
                        "id": "kombify-techstack",
                        "name": "Techstack",
                        "path": "kombify-Techstack",
                        "components": [
                            {
                                "id": "api-ui",
                                "runtime": "docker-compose",
                                "packaging": "standalone",
                                "modes": ["hybrid"],
                                "composeFile": "docker-compose.yml",
                                "healthUrls": ["http://127.0.0.1:65535/stack"],
                                "gates": {"standard": {"miseTask": "preflight:release"}},
                            }
                        ],
                    },
                ]
            )
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            report = workspace / "dress-rehearsal-report.json"

            result = self.run_pwsh(
                REHEARSAL,
                "-DryRun",
                "-SkipDoctor",
                "-SkipAudit",
                "-WorkspaceRoot",
                str(workspace),
                "-Manifest",
                str(manifest),
                "-ReportPath",
                str(report),
            )
            report_payload = json.loads(report.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        step_names = [step["name"] for step in report_payload["steps"]]
        self.assertIn("quick gate kombify-blog", step_names)
        self.assertIn("standard gate kombify-techstack", step_names)
        self.assertIn("saas up kombify-cloud", step_names)
        self.assertIn("local smoke kombify-blog", step_names)
        commands = [" ".join(step.get("command", [])) for step in report_payload["steps"]]
        self.assertTrue(any("run kombify-blog --gate quick --dry-run" in command for command in commands))
        self.assertTrue(any("smoke kombify-blog --dry-run" in command for command in commands))

    def test_windows_bootstrap_contracts_are_non_interactive(self) -> None:
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        rehearsal = REHEARSAL.read_text(encoding="utf-8")
        self.assertIn('$psi.Environment["CI"] = "true"', bootstrap)
        self.assertIn('$psi.Environment["MISE_YES"] = "1"', bootstrap)
        self.assertIn('$psi.Environment["CI"] = "true"', rehearsal)
        self.assertIn('$psi.Environment["MISE_YES"] = "1"', rehearsal)
        self.assertIn("GITHUB_PAT", bootstrap)
        self.assertIn('$psi.Environment["GITHUB_TOKEN"]', bootstrap)
        self.assertIn("GITHUB_PAT", rehearsal)
        self.assertIn('$psi.Environment["GITHUB_TOKEN"]', rehearsal)
        self.assertIn('-split ","', bootstrap)
        self.assertIn('"live Aspire {0} up kombify-cloud"', rehearsal)
        self.assertIn('"live Aspire {0} smoke kombify-cloud"', rehearsal)
        self.assertIn('"live Aspire {0} down kombify-cloud"', rehearsal)
        self.assertNotIn("Pass -StartAspire -Keep", rehearsal)
        self.assertIn("$LiveAspireModes", rehearsal)
        self.assertIn('"--mode", $aspireMode', rehearsal)

    def test_simulate_mise_secret_resolution_is_windows_safe(self) -> None:
        mise_toml = SIMULATE_MISE.read_text(encoding="utf-8")
        helper = SIMULATE_SECRET_HELPER.read_text(encoding="utf-8")
        self.assertNotIn('test "${CI:-}"', mise_toml)
        self.assertIn("node scripts/mise-env-secret.mjs GITHUB_PAT", mise_toml)
        self.assertIn('process.env.CI === "true"', helper)
        self.assertIn('"doppler"', helper)

    def test_repo_setup_tasks_avoid_known_windows_bootstrap_breaks(self) -> None:
        blog = BLOG_MISE.read_text(encoding="utf-8")
        cloud = CLOUD_MISE.read_text(encoding="utf-8")
        ai = AI_MISE.read_text(encoding="utf-8")
        self.assertIn("node scripts/ensure-env-file.mjs", blog)
        self.assertNotIn("test -f .env", blog)
        self.assertNotIn("secrets:pull && mise run compose:up", blog)
        self.assertNotIn("if [ -f compose/dev.yml", blog)
        self.assertIn("node scripts/compose-local.mjs down", blog)
        self.assertIn('[tasks."test:unit"]', blog)
        self.assertIn('depends = ["lint", "test:unit"]', blog)
        self.assertIn('node ../.github/scripts/kombi-local-gate.mjs smoke kombify-blog', blog)
        self.assertNotIn("go mod download || true", cloud)
        self.assertIn('pnpm = "10.33.2"', ai)

    def test_cloud_aspire_profiles_apply_migrations_for_local_databases(self) -> None:
        core_apphost = CORE_ASPIRE_APPHOST.read_text(encoding="utf-8")
        cloud_apphost = CLOUD_ASPIRE_APPHOST.read_text(encoding="utf-8")
        self.assertNotIn('WithEnvironment("SKIP_MIGRATIONS", "true")', core_apphost)
        self.assertNotIn('WithEnvironment("SKIP_MIGRATIONS", "true")', cloud_apphost)
        self.assertIn('Path.Combine(reposRoot, "kombify-Cloud")', core_apphost)
        self.assertIn('Path.Combine(reposRoot, "kombify-simulate")', core_apphost)
        self.assertIn('Path.Combine(reposRoot, "kombify-Techstack")', core_apphost)
        self.assertIn('"backend/deployments/docker/Dockerfile.server"', core_apphost)
        self.assertNotIn('Path.Combine(reposRoot, "kombify Cloud")', core_apphost)
        self.assertNotIn('Path.Combine(reposRoot, "kombify-Simulate")', core_apphost)
        self.assertNotIn('Path.Combine(reposRoot, "kombify-TechStack")', core_apphost)
        self.assertNotIn('"kombify-AI/deployments/docker/Dockerfile.server"', core_apphost)
        self.assertIn('builder.AddDockerfile("kombify-cloud", cloudPath, "Dockerfile.preview")', core_apphost)
        self.assertIn('WithEnvironment("AUTH0_CLIENT_SECRET", auth0ClientSecret)', core_apphost)

    def test_cloud_initial_migration_contains_only_sql(self) -> None:
        migration = CLOUD_INITIAL_MIGRATION.read_text(encoding="utf-8")
        self.assertTrue(migration.lstrip().startswith("-- CreateSchema"))
        self.assertNotIn("Loaded Prisma config", migration)

    def test_cloud_preview_dockerfile_avoids_recursive_runtime_chown(self) -> None:
        dockerfile = CLOUD_PREVIEW_DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("--chown=sveltekit:nodejs", dockerfile)
        self.assertIn("--chmod=755", dockerfile)
        self.assertNotIn("chown -R sveltekit:nodejs /app", dockerfile)

    def test_cloud_tool_name_enum_exists_before_refresh_token_table(self) -> None:
        refresh = CLOUD_REFRESH_TOKEN_MIGRATION.read_text(encoding="utf-8")
        tool_entitlements = CLOUD_TOOL_ENTITLEMENT_MIGRATION.read_text(encoding="utf-8")
        self.assertLess(refresh.index('CREATE TYPE "ToolName"'), refresh.index('CREATE TABLE "refresh_tokens"'))
        self.assertIn("WHEN duplicate_object THEN NULL", tool_entitlements)

    def test_cloud_activity_actor_fields_have_migration(self) -> None:
        migration = CLOUD_ACTIVITY_ACTOR_MIGRATION.read_text(encoding="utf-8")
        self.assertIn('CREATE TYPE "activity_actor_type"', migration)
        self.assertIn('ADD COLUMN IF NOT EXISTS "actor_type"', migration)
        self.assertIn('ADD COLUMN IF NOT EXISTS "actor_label"', migration)
        self.assertIn('ALTER COLUMN "user_id" DROP NOT NULL', migration)
        self.assertIn("ON DELETE SET NULL", migration)

    def test_shared_files_define_local_private_boundaries(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["aspireProfiles"]["saas"], "local-saas-like")
        self.assertEqual(manifest["aspireProfiles"]["hybrid"], "local-hybrid")
        cloud = next(repo for repo in manifest["repos"] if repo["id"] == "kombify-cloud")
        cloud_component = cloud["components"][0]
        self.assertIn("integration", cloud_component["modes"])
        self.assertEqual(cloud_component["healthUrlsByMode"]["local"], ["http://localhost:5290/health"])
        self.assertEqual(cloud_component["healthUrlsByMode"]["saas"], ["http://localhost:5173/health"])
        self.assertTrue(any(repo["id"] == "kombify-cloud" for repo in manifest["repos"]))

        docs = DOCS.read_text(encoding="utf-8")
        self.assertIn("mise run preflight:quick", docs)
        self.assertIn("kombi-bootstrap-local.ps1", docs)
        self.assertIn("kombi-dress-rehearsal.ps1", docs)
        self.assertIn("smoke", docs)
        self.assertIn("local-saas-like", docs)
        self.assertIn("kombify-gates.local.json", docs)
        self.assertIn("Preflight receipts", docs)
        self.assertIn("--mode integration", docs)

        gitignore = GITIGNORE.read_text(encoding="utf-8")
        self.assertIn("local-dev/kombify-gates.local.json", gitignore)
        self.assertIn("local-dev/.env*.local", gitignore)
        self.assertIn("local-dev/reports/", gitignore)
        self.assertIn("local-dev/logs/", gitignore)
        self.assertIn("local-dev/state/", gitignore)

    def test_every_repo_has_local_testing_standard_doc(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for repo in manifest["repos"]:
            with self.subTest(repo=repo["id"]):
                doc = ROOT.parent / repo["path"] / "docs" / "LOCAL_TESTING.md"
                self.assertTrue(doc.exists(), f"{repo['id']} is missing docs/LOCAL_TESTING.md")
                text = doc.read_text(encoding="utf-8")
                self.assertIn(repo["id"], text)
                self.assertIn("mise run preflight:quick", text)
                self.assertIn("mise run preflight:release", text)
                self.assertIn("mise run preflight:deploy", text)
                self.assertIn("kombi-local-gate.mjs", text)
                self.assertIn("--report", text)
                self.assertIn("before remote CI or deploy", text)

    def test_repo_entrypoint_docs_link_to_local_testing_standard(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entrypoint_names = ["README.md", "docs/DEVELOPMENT.md", "docs/TESTING.md", "docs/DEPLOYMENT.md"]
        for repo in manifest["repos"]:
            repo_root = ROOT.parent / repo["path"]
            for relative_name in entrypoint_names:
                doc = repo_root / relative_name
                if not doc.exists():
                    continue
                with self.subTest(repo=repo["id"], doc=relative_name):
                    text = doc.read_text(encoding="utf-8")
                    self.assertIn("LOCAL_TESTING.md", text)

    def test_entrypoint_docs_do_not_advertise_obsolete_local_testing_paths(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        obsolete_patterns = [
            "cd ../kombify-DB && docker compose up -d",
            "bun dev          # Start dev server",
            "Bun                | 1.1.8",
            "Node.js            | 22",
            "Go                 | 1.24",
            "bun run test:ci",
            "mise run stage",
            "mise run prod",
        ]
        entrypoint_names = ["README.md", "docs/DEVELOPMENT.md", "docs/TESTING.md", "docs/DEPLOYMENT.md"]
        for repo in manifest["repos"]:
            repo_root = ROOT.parent / repo["path"]
            for relative_name in entrypoint_names:
                doc = repo_root / relative_name
                if not doc.exists():
                    continue
                text = doc.read_text(encoding="utf-8")
                for pattern in obsolete_patterns:
                    with self.subTest(repo=repo["id"], doc=relative_name, pattern=pattern):
                        self.assertNotIn(pattern, text)

    def test_beads_track_local_testing_standard_where_active(self) -> None:
        expected_title = "Adopt Kombify local testing standard"
        for repo_root in beads_active_repos():
            beads = repo_root / ".beads" / "issues.jsonl"
            with self.subTest(repo=repo_root.name):
                issues = [json.loads(line) for line in beads.read_text(encoding="utf-8").splitlines() if line.strip()]
                matches = [issue for issue in issues if issue.get("title") == expected_title]
                self.assertTrue(matches, f"{repo_root.name} is missing Beads task: {expected_title}")
                task_blob = json.dumps(matches[0], sort_keys=True)
                self.assertIn("docs/LOCAL_TESTING.md", task_blob)
                self.assertIn("preflight:release", task_blob)
                self.assertIn("preflight:deploy", task_blob)

    def test_beads_runtime_state_stays_local_where_active(self) -> None:
        for repo_root in beads_active_repos():
            with self.subTest(repo=repo_root.name):
                beads_gitignore = (repo_root / ".beads" / ".gitignore").read_text(encoding="utf-8")
                beads_config = (repo_root / ".beads" / "config.yaml").read_text(encoding="utf-8")
                self.assertIn("embeddeddolt/", beads_gitignore)
                self.assertIn("backup/", beads_gitignore)
                self.assertIn("export-state.json", beads_gitignore)
                self.assertIn("dolt-server.lock", beads_gitignore)
                self.assertIn(".local_version", beads_gitignore)
                self.assertIn("last-touched", beads_gitignore)
                self.assertIn("export.git-add: false", beads_config)


if __name__ == "__main__":
    unittest.main()
