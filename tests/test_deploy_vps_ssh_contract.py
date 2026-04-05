import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-vps-ssh.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


class DeployVpsSshContractTest(unittest.TestCase):
    def test_workflow_exposes_overridable_ssh_secret_keys(self) -> None:
        self.assertIn("ssh-host-key:", TEXT)
        self.assertIn('default: "IONOS_VPS_HOST"', TEXT)
        self.assertIn("ssh-user-key:", TEXT)
        self.assertIn('default: "IONOS_VPS_USER"', TEXT)
        self.assertIn("ssh-private-key-key:", TEXT)
        self.assertIn('default: "IONOS_SSH_PRIVATE_KEY"', TEXT)
        self.assertIn("ssh-port-key:", TEXT)

    def test_workflow_fails_clearly_when_doppler_token_is_missing(self) -> None:
        self.assertIn('echo "::error::DOPPLER_TOKEN is empty"', TEXT)

    def test_workflow_uses_explicit_doppler_token_flag(self) -> None:
        self.assertIn('--token "$DOPPLER_TOKEN"', TEXT)
        self.assertIn("--no-read-env", TEXT)
        self.assertIn('SSH_PORT="${SSH_PORT:-22}"', TEXT)
        self.assertIn('-p "$SSH_PORT" \\', TEXT)
        self.assertNotIn('echo "::add-mask::$SSH_KEY"', TEXT)

    def test_workflow_resolves_expected_vps_secrets_via_helper(self) -> None:
        self.assertIn("doppler_secret() {", TEXT)
        self.assertIn("doppler_secret_optional() {", TEXT)
        self.assertIn('VPS_HOST=$(doppler_secret "${{ inputs.ssh-host-key }}")', TEXT)
        self.assertIn('VPS_USER=$(doppler_secret "${{ inputs.ssh-user-key }}")', TEXT)
        self.assertIn('SSH_KEY=$(doppler_secret "${{ inputs.ssh-private-key-key }}")', TEXT)
        self.assertIn('SSH_PORT=$(doppler_secret_optional "${{ inputs.ssh-port-key }}")', TEXT)


if __name__ == "__main__":
    unittest.main()
