import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-coolify.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


class DeployCoolifyContractTest(unittest.TestCase):
    def test_job_timeout_is_capped_at_three_minutes(self) -> None:
        self.assertIn("timeout-minutes: 3", TEXT)

    def test_deployment_wait_loop_stays_under_three_minutes(self) -> None:
        self.assertNotIn('echo "Waiting 20s for Coolify to pull image and restart..."', TEXT)
        self.assertNotIn("sleep 20", TEXT)
        self.assertIn("sleep 3", TEXT)
        self.assertIn("for i in $(seq 1 18); do", TEXT)
        self.assertIn("sleep 5", TEXT)

    def test_health_check_uses_short_retry_budget(self) -> None:
        self.assertRegex(TEXT, r"for i in 1 2 3; do")
        self.assertIn("--max-time 10", TEXT)


if __name__ == "__main__":
    unittest.main()
