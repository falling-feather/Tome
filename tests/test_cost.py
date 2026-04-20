"""v2.11: per-model usage tracking + cost computation."""
import json

from backend.app.config import settings
from backend.app.services import cost as cost_mod


def setup_function(_):
    cost_mod.reset_usage()


def test_record_and_compute_known_model():
    cost_mod.record_usage("gpt-4o", 1000, 500)
    cost_mod.record_usage("gpt-4o", 2000, 1000)
    report = cost_mod.compute_cost_report(usd_to_cny=7.0)
    assert report["total_input_tokens"] == 3000
    assert report["total_output_tokens"] == 1500
    # gpt-4o = (3000/1000)*0.005 + (1500/1000)*0.015 = 0.015 + 0.0225 = 0.0375
    assert abs(report["total_cost_usd"] - 0.0375) < 1e-6
    assert abs(report["total_cost_cny"] - 0.0375 * 7.0) < 1e-6
    row = report["models"][0]
    assert row["model"] == "gpt-4o"
    assert row["priced"] is True
    assert row["requests"] == 2


def test_unknown_model_marked_unpriced():
    cost_mod.record_usage("totally-novel-model-xyz", 500, 500)
    report = cost_mod.compute_cost_report()
    assert len(report["models"]) == 1
    assert report["models"][0]["priced"] is False
    assert report["models"][0]["cost_usd"] == 0.0
    assert report["total_cost_usd"] == 0.0


def test_pricing_override_via_settings(monkeypatch):
    monkeypatch.setattr(
        settings,
        "LLM_PRICING_JSON",
        json.dumps({"my-custom-model": [0.001, 0.002]}),
    )
    cost_mod.record_usage("my-custom-model", 1000, 1000)
    report = cost_mod.compute_cost_report(usd_to_cny=7.0)
    # 1000/1000*0.001 + 1000/1000*0.002 = 0.003
    assert abs(report["total_cost_usd"] - 0.003) < 1e-6


def test_loose_match_for_versioned_model():
    cost_mod.record_usage("deepseek-chat-v2.5", 1000, 1000)
    report = cost_mod.compute_cost_report()
    assert report["models"][0]["priced"] is True
    # deepseek-chat = 0.00027 + 0.0011 = 0.00137 → rounded to 4dp = 0.0014
    assert report["total_cost_usd"] == 0.0014
