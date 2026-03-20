import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "vps-bootstrap" / "scripts" / "bootstrap-build-host.sh").read_text(encoding="utf-8")
INSTALL_RUNNER = (ROOT / "vps-bootstrap" / "scripts" / "install-runner.sh").read_text(encoding="utf-8")
INSTALL_HEALTH = (ROOT / "vps-bootstrap" / "scripts" / "install-runner-health-monitor.sh").read_text(encoding="utf-8")
RUNNER_HEALTH = (ROOT / "vps-bootstrap" / "scripts" / "runner-health-check.sh").read_text(encoding="utf-8")


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


if __name__ == "__main__":
    unittest.main()
