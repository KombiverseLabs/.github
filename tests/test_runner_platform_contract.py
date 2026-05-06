import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "vps-bootstrap" / "scripts" / "bootstrap-build-host.sh").read_text(encoding="utf-8")
INSTALL_RUNNER = (ROOT / "vps-bootstrap" / "scripts" / "install-runner.sh").read_text(encoding="utf-8")
INSTALL_HEALTH = (ROOT / "vps-bootstrap" / "scripts" / "install-runner-health-monitor.sh").read_text(encoding="utf-8")
RUNNER_HEALTH = (ROOT / "vps-bootstrap" / "scripts" / "runner-health-check.sh").read_text(encoding="utf-8")
PICK_RUNNER_WORKFLOW = (ROOT / ".github" / "workflows" / "pick-runner-v2.yml").read_text(encoding="utf-8")
BUILD_AND_PUSH_WORKFLOW = (ROOT / ".github" / "workflows" / "build-and-push.yml").read_text(encoding="utf-8")
SETUP_RUNNER_TWO_WORKFLOW = (ROOT / ".github" / "workflows" / "setup-runner-2.yml").read_text(encoding="utf-8")
VALIDATE_REUSABLE_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "validate-reusable-workflows.yml"
).read_text(encoding="utf-8")


class RunnerPlatformContractTest(unittest.TestCase):
    def test_bootstrap_installs_three_named_runners(self) -> None:
        self.assertIn('install_runner "oci-build-core-1"', BOOTSTRAP)
        self.assertIn('install_runner "oci-build-core-2"', BOOTSTRAP)
        self.assertIn('install_runner "oci-build-tools-1"', BOOTSTRAP)

    def test_bootstrap_enables_docker_live_restore(self) -> None:
        self.assertIn('"live-restore": true', BOOTSTRAP)

    def test_bootstrap_installs_runner_health_monitor(self) -> None:
        self.assertIn('install-runner-health-monitor.sh', BOOTSTRAP)
        self.assertIn('kombify-runner-health.timer', BOOTSTRAP)

    def test_bootstrap_installs_doppler_cli(self) -> None:
        self.assertIn('install-doppler.sh', BOOTSTRAP)

    def test_runner_installer_uses_current_runner_version(self) -> None:
        self.assertIn('RUNNER_VERSION="${RUNNER_VERSION:-2.332.0}"', INSTALL_RUNNER)

    def test_health_monitor_installs_service_and_timer(self) -> None:
        self.assertIn("kombify-runner-health.service", INSTALL_HEALTH)
        self.assertIn("kombify-runner-health.timer", INSTALL_HEALTH)
        self.assertIn("OnUnitActiveSec=5min", INSTALL_HEALTH)

    def test_health_check_self_heals_docker_and_runner_services(self) -> None:
        self.assertIn("ensure_docker_healthy", RUNNER_HEALTH)
        self.assertIn("ensure_service_active", RUNNER_HEALTH)
        self.assertIn("docker builder prune -af", RUNNER_HEALTH)

    def test_pick_runner_uses_probe_runner_for_real_fallback(self) -> None:
        self.assertIn("fallback:", PICK_RUNNER_WORKFLOW)
        self.assertIn("last-resort:", PICK_RUNNER_WORKFLOW)
        self.assertIn("probe-runner:", PICK_RUNNER_WORKFLOW)
        self.assertIn("runs-on: ${{ inputs.probe-runner || 'ubuntu-latest' }}", PICK_RUNNER_WORKFLOW)
        self.assertNotIn("runs-on: ${{ inputs.preferred", PICK_RUNNER_WORKFLOW)

    def test_pick_runner_checks_self_hosted_availability(self) -> None:
        self.assertIn("/actions/runners", PICK_RUNNER_WORKFLOW)
        self.assertIn("status') == 'online'", PICK_RUNNER_WORKFLOW)
        self.assertIn("runner.get('busy')", PICK_RUNNER_WORKFLOW)
        self.assertIn("labels", PICK_RUNNER_WORKFLOW)

    def test_build_and_push_has_portable_buildx_path(self) -> None:
        self.assertIn("build-engine:", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("docker/setup-buildx-action@v3", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("docker/build-push-action@v6", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("useblacksmith/build-push-action@v2", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("build-output", BUILD_AND_PUSH_WORKFLOW)

    def test_build_and_push_uses_persistent_buildkit_cache(self) -> None:
        self.assertIn("cache-scope:", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("cache-from:", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("cache-to:", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("type=gha,scope=${{ inputs.cache-scope", BUILD_AND_PUSH_WORKFLOW)
        self.assertIn("type=gha,mode=max,scope=${{ inputs.cache-scope", BUILD_AND_PUSH_WORKFLOW)

    def test_setup_runner_two_uses_updateable_current_runner_version(self) -> None:
        self.assertIn("runner-version:", SETUP_RUNNER_TWO_WORKFLOW)
        self.assertIn('default: "2.333.0"', SETUP_RUNNER_TWO_WORKFLOW)
        self.assertIn('RUNNER_VERSION="${RUNNER_VERSION:-2.333.0}"', SETUP_RUNNER_TWO_WORKFLOW)

    def test_reusable_workflow_validator_installs_actionlint_directly(self) -> None:
        self.assertNotIn("rhysd/actionlint@v1", VALIDATE_REUSABLE_WORKFLOWS)
        self.assertIn("go install github.com/rhysd/actionlint/cmd/actionlint@", VALIDATE_REUSABLE_WORKFLOWS)
        self.assertIn("cache: false", VALIDATE_REUSABLE_WORKFLOWS)
        self.assertIn("          actionlint", VALIDATE_REUSABLE_WORKFLOWS)


if __name__ == "__main__":
    unittest.main()
