import pytest

from backend.services.engine.research.external_submit_guard import (
    EXTERNAL_SUBMIT_ENV,
    ExternalSubmitDisabledError,
    assert_external_submit_allowed,
    assert_quantgpt_endpoint_allowed,
    get_external_submit_policy,
)


def test_external_submit_policy_is_disabled_by_default_even_with_wq_credentials():
    env = {
        "WQ_BRAIN_EMAIL": "configured@example.com",
        "WQ_BRAIN_PASSWORD": "secret",
    }

    policy = get_external_submit_policy(env)

    assert policy.enabled is False
    assert policy.allowed_targets == ()


def test_external_submit_policy_requires_explicit_quantmind_allow_flag():
    env = {
        "WQ_BRAIN_EMAIL": "configured@example.com",
        "WQ_BRAIN_PASSWORD": "secret",
        EXTERNAL_SUBMIT_ENV: "true",
    }

    policy = get_external_submit_policy(env)

    assert policy.enabled is True
    assert policy.allowed_targets == ("cloud_submit", "wq_brain")
    assert_external_submit_allowed("wq_brain", env=env)
    assert_external_submit_allowed("cloud-submit", env=env)


def test_quantgpt_wq_brain_submit_endpoint_is_blocked_by_default():
    with pytest.raises(ExternalSubmitDisabledError, match=EXTERNAL_SUBMIT_ENV):
        assert_quantgpt_endpoint_allowed(
            "/api/v1/wq-brain/submit",
            env={"WQ_BRAIN_EMAIL": "configured@example.com"},
        )


def test_quantgpt_safe_research_endpoints_remain_allowed_by_default():
    env = {}

    assert_quantgpt_endpoint_allowed("/api/v1/health", env=env)
    assert_quantgpt_endpoint_allowed("/api/v1/auto_backtest", env=env)
    assert_quantgpt_endpoint_allowed("/api/v1/factor_values", env=env)
    assert_quantgpt_endpoint_allowed("/api/v1/tasks/task-1", env=env)
