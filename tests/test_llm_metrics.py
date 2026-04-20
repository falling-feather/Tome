"""P2-21: validate that LLM token/char counters are surfaced via health_metrics."""
from backend.app.services.resilience import health_metrics


def test_llm_counters_increment_and_appear_in_report():
    before_in = health_metrics._counters.get("llm_input_chars", 0)
    before_out = health_metrics._counters.get("llm_output_chars", 0)
    before_tok = health_metrics._counters.get("llm_tokens_est", 0)

    health_metrics.inc("llm_input_chars", 120)
    health_metrics.inc("llm_output_chars", 240)
    health_metrics.inc("llm_tokens_est", 180)

    report = health_metrics.get_report()
    counters = report["counters"]
    assert counters["llm_input_chars"] >= before_in + 120
    assert counters["llm_output_chars"] >= before_out + 240
    assert counters["llm_tokens_est"] >= before_tok + 180
