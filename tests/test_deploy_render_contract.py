import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRECT_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-render.yml"
STAGED_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-render-staged.yml"
RENDER_BOOTSTRAP_ACTION = ROOT / ".github" / "actions" / "render-cli-bootstrap" / "action.yml"
DIRECT_TEXT = DIRECT_WORKFLOW.read_text(encoding="utf-8")
STAGED_TEXT = STAGED_WORKFLOW.read_text(encoding="utf-8")
RENDER_BOOTSTRAP_TEXT = RENDER_BOOTSTRAP_ACTION.read_text(encoding="utf-8") if RENDER_BOOTSTRAP_ACTION.exists() else ""


class DeployRenderContractTest(unittest.TestCase):
    def test_direct_workflow_accepts_runtime_env_sync_inputs(self) -> None:
        self.assertIn("runtime-env-project:", DIRECT_TEXT)
        self.assertIn("runtime-env-config:", DIRECT_TEXT)
        self.assertIn("preserve-runtime-env-extras:", DIRECT_TEXT)
        self.assertIn("default: false", DIRECT_TEXT)

    def test_direct_workflow_syncs_render_env_from_doppler(self) -> None:
        self.assertIn("doppler secrets download \\", DIRECT_TEXT)
        self.assertIn('--format json \\', DIRECT_TEXT)
        self.assertIn('--project "${{ inputs.runtime-env-project }}" \\', DIRECT_TEXT)
        self.assertIn('--config "${{ inputs.runtime-env-config }}" \\', DIRECT_TEXT)
        self.assertIn('base_url = f"https://api.render.com/v1/services/{service_id}/env-vars"', DIRECT_TEXT)
        self.assertIn('request("GET", f"{base_url}?limit=100")', DIRECT_TEXT)
        self.assertIn('request("PUT", f"{base_url}/{encoded_key}", {"value": str(value)})', DIRECT_TEXT)
        self.assertIn('if value is None or str(value) == "":', DIRECT_TEXT)
        self.assertIn('request("DELETE", f"{base_url}/{encoded_key}")', DIRECT_TEXT)

    def test_staged_workflow_accepts_runtime_env_sync_inputs(self) -> None:
        self.assertIn("runtime-env-project:", STAGED_TEXT)
        self.assertIn("runtime-env-config:", STAGED_TEXT)
        self.assertIn("render-credentials-project:", STAGED_TEXT)
        self.assertIn("render-credentials-config:", STAGED_TEXT)
        self.assertIn("preserve-runtime-env-extras:", STAGED_TEXT)

    def test_staged_workflow_syncs_before_each_render_deploy(self) -> None:
        self.assertEqual(STAGED_TEXT.count("Sync runtime environment from Doppler"), 2)
        self.assertGreaterEqual(STAGED_TEXT.count("doppler secrets download \\"), 2)
        self.assertGreaterEqual(STAGED_TEXT.count('request("PUT", base_url, payload)'), 2)
        self.assertGreaterEqual(STAGED_TEXT.count('if value is None or str(value) == "":'), 2)
        self.assertGreaterEqual(STAGED_TEXT.count("stale_keys = sorted(set(current_values) - set(desired))"), 2)
        self.assertGreaterEqual(STAGED_TEXT.count("if preserve_extras:"), 2)
        self.assertGreaterEqual(STAGED_TEXT.count('payload.append({"key": key, "value": current_values[key]})'), 2)
        self.assertGreaterEqual(STAGED_TEXT.count("removed {len(stale_keys)} stale direct vars"), 2)

    def test_staged_workflow_uses_render_token_for_render_credentials(self) -> None:
        matches = re.findall(
            r"- name: Resolve Render credentials.*?DOPPLER_TOKEN: \$\{\{ secrets\.DOPPLER_TOKEN_RENDER \}\}",
            STAGED_TEXT,
            flags=re.DOTALL,
        )
        self.assertEqual(len(matches), 2)

    def test_staged_workflow_uses_runtime_token_only_for_runtime_env_sync(self) -> None:
        matches = re.findall(
            r"- name: Sync runtime environment from Doppler.*?DOPPLER_TOKEN: \$\{\{ secrets\.DOPPLER_TOKEN_RUNTIME \|\| secrets\.DOPPLER_TOKEN_RENDER \}\}",
            STAGED_TEXT,
            flags=re.DOTALL,
        )
        self.assertEqual(len(matches), 2)

    def test_staged_workflow_scopes_render_secret_reads_explicitly(self) -> None:
        self.assertEqual(
            STAGED_TEXT.count("DOPPLER_SCOPE_ARGS=("),
            2,
        )
        self.assertEqual(
            STAGED_TEXT.count('--project "${{ inputs.render-credentials-project }}"'),
            2,
        )
        self.assertEqual(
            STAGED_TEXT.count('--config "${{ inputs.render-credentials-config }}"'),
            2,
        )

    def test_render_deploy_concurrency_is_service_scoped(self) -> None:
        self.assertIn(
            "inputs.service-id || inputs.service-id-key || inputs.image-repository",
            DIRECT_TEXT,
        )
        self.assertIn("inputs.service-name", STAGED_TEXT)
        self.assertIn("inputs.service-id-key-production", STAGED_TEXT)
        self.assertNotIn(
            "group: ${{ github.workflow }}-${{ github.ref }}\n",
            DIRECT_TEXT,
        )
        self.assertNotIn(
            "group: ${{ github.workflow }}-${{ github.ref }}\n",
            STAGED_TEXT,
        )

    def test_render_workflows_use_shared_cli_bootstrap_actions(self) -> None:
        self.assertNotIn("- name: Install Doppler CLI", DIRECT_TEXT)
        self.assertNotIn("- name: Install Doppler CLI", STAGED_TEXT)
        self.assertIn("KombiverseLabs/.github/.github/actions/doppler-bootstrap@main", DIRECT_TEXT)
        self.assertEqual(
            STAGED_TEXT.count("KombiverseLabs/.github/.github/actions/doppler-bootstrap@main"),
            2,
        )
        self.assertNotIn("- name: Install Render CLI", DIRECT_TEXT)
        self.assertIn("KombiverseLabs/.github/.github/actions/render-cli-bootstrap@main", DIRECT_TEXT)

    def test_render_cli_bootstrap_action_is_cached_and_idempotent(self) -> None:
        self.assertIn("Render CLI Bootstrap", RENDER_BOOTSTRAP_TEXT)
        self.assertIn("actions/cache@v4", RENDER_BOOTSTRAP_TEXT)
        self.assertIn("command -v render", RENDER_BOOTSTRAP_TEXT)
        self.assertIn("raw.githubusercontent.com/render-oss/cli", RENDER_BOOTSTRAP_TEXT)


if __name__ == "__main__":
    unittest.main()
