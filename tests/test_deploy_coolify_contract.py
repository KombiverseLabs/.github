import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-coolify.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")


class DeployCoolifyContractTest(unittest.TestCase):
    def test_resource_uuid_input_is_optional(self) -> None:
        self.assertIn("resource-uuid:", TEXT)
        self.assertIn("required: false", TEXT)

    def test_workflow_accepts_resource_secret_name_input(self) -> None:
        self.assertIn("resource-secret-name:", TEXT)
        self.assertIn("default: 'COOLIFY_RESOURCE_UUID'", TEXT)

    def test_workflow_accepts_deploy_doppler_token_secret(self) -> None:
        self.assertIn("DEPLOY_DOPPLER_TOKEN:", TEXT)
        self.assertIn("required: false", TEXT)

    def test_resource_uuid_can_fall_back_to_doppler_secret(self) -> None:
        self.assertIn("COOLIFY_RESOURCE_UUID", TEXT)
        self.assertIn("resolved-resource-uuid", TEXT)

    def test_resource_uuid_resolution_prefers_input_then_named_doppler_secret(self) -> None:
        pattern = re.compile(
            r"resolved_uuid = input_uuid or str\(secret_map.get\(resource_secret_name, ''\)\).strip\(\)"
        )
        self.assertRegex(TEXT, pattern)

    def test_workflow_resolves_coolify_api_token_from_deploy_doppler(self) -> None:
        self.assertIn("secret_map.get('COOLIFY_API_TOKEN', '') or secret_map.get('COOLIFY_API_KEY', '')", TEXT)
        self.assertIn("steps.resolved-resource-uuid.outputs.coolify_api_token", TEXT)

    def test_workflow_fails_clearly_when_resource_uuid_is_missing(self) -> None:
        self.assertIn("Coolify resource UUID is required", TEXT)

    def test_job_timeout_is_capped_at_three_minutes(self) -> None:
        self.assertIn("timeout-minutes: 3", TEXT)

    def test_default_runner_uses_oci_capacity(self) -> None:
        self.assertIn("default: 'oci-build-labs'", TEXT)

    def test_deployment_wait_loop_stays_under_three_minutes(self) -> None:
        self.assertNotIn('echo "Waiting 20s for Coolify to pull image and restart..."', TEXT)
        self.assertNotIn("sleep 20", TEXT)
        self.assertIn("sleep 3", TEXT)
        self.assertIn("for attempt in range(1, 19):", TEXT)
        self.assertIn("time.sleep(5)", TEXT)
        self.assertIn("print('✅ Resource is ready')", TEXT)

    def test_health_check_uses_short_retry_budget(self) -> None:
        self.assertRegex(TEXT, r"for i in 1 2 3; do")
        self.assertIn("--max-time 10", TEXT)

    def test_service_resources_update_their_compose_image_tags(self) -> None:
        self.assertIn("if: inputs.image-tag != 'latest'", TEXT)
        self.assertIn("if resource_type != 'service':", TEXT)
        self.assertIn("request('GET', f'services/{uuid}')", TEXT)
        self.assertIn("'docker_compose_raw': updated", TEXT)
        self.assertIn("no static image lines found in service docker compose", TEXT)
        self.assertIn("skipping image tag mutation and relying on the configured service image source", TEXT)
        self.assertIn("image-repository:", TEXT)
        self.assertIn("ghcr.io/{owner}/{repo.lower()}", TEXT)
        self.assertIn("if image_repository and image_ref.lower() != image_repository:", TEXT)


if __name__ == "__main__":
    unittest.main()
