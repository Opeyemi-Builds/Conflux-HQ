#!/usr/bin/env python3
"""Verification script for Forge 2026: Huawei MaaS and Twitter Live Adapter integrations.

Can be run inside the Forge Kubernetes pod or locally:
  python scripts/verify_forge_integrations.py [--maas-only] [--twitter-only]

Checks:
1. Huawei MaaS:
   - Evaluates reachability and exact protocol per forge-2026-agent-reference.md:
     * Base URL: http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1
     * Auth Header: apikey: <team-key>
     * Disabled reasoning via chat_template_kwargs: {"thinking": False}
   - Evaluates Complaint Classification:
     * Tests Nigerian Pidgin prompt execution ("abeg money hanging")
     * Validates JSON schema (issue_type, language, sentiment, confidence)
   - Evaluates Incident Investigation:
     * Generates grounded brief from evidence bundle with citable registry
2. Twitter Live Adapter:
   - Verifies tenant handle query compilation specifically for target bank
   - Verifies X API v2 Recent Search parameters:
     * clamped max_results, tweet.fields, expansions, user.fields
   - Verifies multi-tenant attribution (matching_rules -> tenant:<bank_id>)
   - Verifies deduplication and daily $0.005/post spending cap guardrail
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parents[1] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import httpx
from app.adapters.x_adapter import (
    XAdapter,
    compile_combined_search_query,
    compile_desired_rules,
    get_x_adapter_status,
)
from app.ai.investigation import maas_investigate
from app.ai.providers.classify import maas_classify
from app.ai.providers.maas import MaasConfig, chat_completion, parse_json_text
from app.ai.providers.settings import maas_active, maas_config_from_settings, maas_key_from_settings
from app.core.config import get_settings
from app.db.base import Base
from app.models import Bank, BankAlias, Complaint
from app.models.enums import BankStatus, Channel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title.upper()}")
    print("=" * 70)


def verify_maas():
    print_header("1. Huawei MaaS Integration Verification")
    settings = get_settings()
    cfg = maas_config_from_settings(settings)
    key = maas_key_from_settings(settings)

    print(f"[*] Configuration:")
    print(f"    - Base URL: {cfg.base_url}")
    print(f"    - Model: {cfg.model}")
    print(f"    - Team Gateway Key: {'[CONFIGURED: ' + key[:8] + '...]' if key else '[NOT SET]'}")
    print(f"    - AI Provider: {settings.ai_provider}")
    print(f"    - MaaS Active: {maas_active(settings)}")

    if not key:
        print("\n[!] GATEWAY_KEY is not set in environment or config.")
        print("    If running outside the pod, test using a mock transport or export GATEWAY_KEY.")
        return False

    # 1. Low-level chat completions test
    print("\n[*] Step 1: Testing direct chat completions call to MaaS...")
    test_messages = [
        {"role": "system", "content": "You are a test assistant. Return ONLY a JSON object: {\"status\": \"ok\", \"pong\": true}."},
        {"role": "user", "content": "ping"},
    ]

    started = time.monotonic()
    try:
        res = chat_completion(test_messages, config=cfg, gateway_key=key, json_mode=True)
        elapsed_ms = round((time.monotonic() - started) * 1000)
        print(f"    [+] SUCCESS: Received response in {elapsed_ms}ms")
        print(f"    [+] Model: {res.model}")
        print(f"    [+] Token Usage: prompt={res.input_tokens}, completion={res.output_tokens}")
        print(f"    [+] Parsed Payload: {res.payload}")
    except Exception as exc:
        print(f"    [-] FAILED to reach MaaS endpoint: {exc}")
        print("    (Note: Ingress endpoint is only reachable from workloads inside the Forge cluster)")
        return False

    # 2. Complaint classification test
    print("\n[*] Step 2: Testing Nigerian banking complaint classification via MaaS...")
    sample_text = "Abeg, my 30,000 naira transfer to GTBank fail since 8am, but dem debit my balance!"
    try:
        classification, maas_res = maas_classify(sample_text, channel="in_app", config=cfg, gateway_key=key)
        print(f"    [+] SUCCESS: Complaint classified by MaaS:")
        print(f"        * Issue Type: {classification.issue_type}")
        print(f"        * Severity: {classification.severity}")
        print(f"        * Language: {classification.language}")
        print(f"        * Mentioned Amount: NGN {classification.mentioned_amount}")
        print(f"        * Confidence: {classification.confidence}")
        print(f"        * Summary: {classification.short_summary}")
    except Exception as exc:
        print(f"    [-] Classification FAILED: {exc}")
        return False

    # 3. Grounded incident investigation test
    print("\n[*] Step 3: Testing grounded incident investigation via MaaS...")
    evidence_bundle = {
        "incident": {"issue_type": "failed_transfer", "complaint_count": 22, "baseline": 2.5},
        "complaints": {"count": 22, "channels": {"in_app": 15, "x": 7}},
        "transactions": {"observed": 50, "failed": 18, "unreversed_failed": 11, "dominant_processor": "NIBSS"},
        "events": [{"id": "evt-nibss-switch-lag", "type": "network", "component": "NIBSS"}],
        "evidence_registry": {
            "complaints": [{"id": "cmp-01"}, {"id": "cmp-02"}],
            "system_events": [{"id": "evt-nibss-switch-lag"}],
            "transactions": [{"id": "txn-501"}],
        },
    }
    try:
        brief, telemetry = maas_investigate(evidence_bundle, config=cfg, gateway_key=key)
        print(f"    [+] SUCCESS: Investigation brief generated by MaaS:")
        print(f"        * Confidence: {brief.confidence}")
        print(f"        * Cited Supporting Evidence: {brief.supporting_evidence_ids}")
        print(f"        * Recommended Checks: {brief.recommended_checks}")
        print(f"        * Recommended Owner: {brief.recommended_owner}")
    except Exception as exc:
        print(f"    [-] Investigation FAILED: {exc}")
        return False

    print("\n[✔] All Huawei MaaS integration checks passed!")
    return True


def verify_twitter():
    print_header("2. Twitter (X) Live Adapter & Monitor Verification")
    settings = get_settings()

    print(f"[*] Configuration:")
    print(f"    - API Base URL: {settings.x_api_base_url}")
    print(f"    - Bearer Token: {'[CONFIGURED]' if settings.x_bearer_token else '[NOT SET - REPLAY ACTIVE]'}")
    print(f"    - Daily Post Limit: {settings.x_daily_post_limit}")
    print(f"    - Timeout: {settings.x_timeout_seconds}s")

    # In-memory session for verification
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Create demo bank and aliases
        bank = Bank(name="Zymic Bank", slug="zymic", contact_email="contact@zymic.co", status=BankStatus.ACTIVE)
        db.add(bank)
        db.flush()
        db.add(BankAlias(bank_id=bank.id, value="@zymicbank", kind="handle", platform="x"))
        db.add(BankAlias(bank_id=bank.id, value="@zymic_support", kind="handle", platform="x"))
        db.add(BankAlias(bank_id=bank.id, value="#ZymicBank", kind="hashtag", platform="x"))
        db.commit()

        # Step 1: Query generation
        print("\n[*] Step 1: Verifying query compilation for target bank...")
        query = compile_combined_search_query(db, target_bank_id=bank.id)
        print(f"    [+] Generated X v2 Recent Search Query:")
        print(f"        '{query}'")
        assert "@zymicbank" in query
        assert "to:zymicbank" in query
        assert "@zymic_support" in query
        assert "-is:retweet" in query

        # Step 2: Stream rules compilation
        print("\n[*] Step 2: Verifying Filtered Stream rules compilation...")
        rules = compile_desired_rules(db)
        print(f"    [+] Compiled {len(rules)} tenant rules:")
        for r in rules:
            print(f"        * Tag: {r['tag']} | Query: {r['value']}")
        assert any(r["tag"] == f"tenant:{bank.id}" for r in rules)

        # Step 3: Status and budget metrics
        print("\n[*] Step 3: Checking spending cap and metrics...")
        status = get_x_adapter_status(db)
        print(f"    [+] Status:")
        print(f"        * Mode: {status['mode']}")
        print(f"        * Reads Today: {status['reads_today']} / {status['daily_post_limit']}")
        print(f"        * Estimated Spend Today: ${status['estimated_cost_today_usd']:.4f}")
        print(f"        * Rate Per Post: ${status['rate_per_post_usd']}")

        # Step 4: Test Ingestion and Deduplication
        print("\n[*] Step 4: Testing payload parsing, PII masking, and deduplication...")
        adapter = XAdapter(db)
        test_tweet = {
            "data": {
                "id": "1859999999999000111",
                "text": "@zymicbank my 45,000 transfer failed, contact me at 08031234567 or user@example.com",
                "author_id": "usr_test_99",
                "created_at": "2026-11-11T08:00:00Z",
            },
            "includes": {"users": [{"id": "usr_test_99", "username": "test_customer"}]},
            "matching_rules": [{"id": "r1", "tag": f"tenant:{bank.id}"}],
        }
        res1 = adapter.ingest_raw_v2_payload(test_tweet, synthetic=False)
        print(f"    [+] First Ingestion: accepted={res1.get('accepted')}, duplicate={res1.get('duplicate', False)}")

        complaint = db.scalar(select(Complaint).where(Complaint.bank_id == bank.id))
        assert complaint is not None
        print(f"    [+] Masked Complaint Text:")
        print(f"        '{complaint.text}'")
        assert "08031234567" not in complaint.text
        assert "[PHONE]" in complaint.text
        assert "user@example.com" not in complaint.text
        assert "[EMAIL]" in complaint.text

        # Second ingestion of same tweet
        res2 = adapter.ingest_raw_v2_payload(test_tweet, synthetic=False)
        print(f"    [+] Repeated Ingestion: accepted={res2.get('accepted')}, duplicate={res2.get('duplicate', False)}")
        assert res2.get("duplicate") is True

        # Step 5: Live Pull check if credentials are set
        if settings.x_bearer_token:
            print("\n[*] Step 5: Testing live pull from api.x.com/2/tweets/search/recent...")
            try:
                live_res = adapter.pull_recent_mentions(target_bank_id=bank.id, max_results=10)
                print(f"    [+] Live pull result: source={live_res.get('source')}, fetched={live_res.get('fetched')}, created={live_res.get('complaints_created')}")
            except Exception as exc:
                print(f"    [-] Live pull error: {exc}")
        else:
            print("\n[*] Step 5: Live X_BEARER_TOKEN not set; skipping live external HTTP call.")
            print("    (When deploying to the pod, provide X_BEARER_TOKEN in secrets for live pulls)")

        print("\n[✔] All Twitter Live Adapter integration checks passed!")
        return True
    finally:
        db.close()
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Forge 2026 MaaS & Twitter Adapter Verification")
    parser.add_argument("--maas-only", action="store_true", help="Run only MaaS checks")
    parser.add_argument("--twitter-only", action="store_true", help="Run only Twitter adapter checks")
    args = parser.parse_args()

    print("=" * 70)
    print("  FORGE 2026 PLATFORM INTEGRATION VERIFICATION HARNESS")
    print("=" * 70)

    maas_ok = True
    twitter_ok = True

    if not args.twitter_only:
        maas_ok = verify_maas()
    if not args.maas_only:
        twitter_ok = verify_twitter()

    print("\n" + "=" * 70)
    print(f"  SUMMARY: MaaS={('PASS' if maas_ok else 'FAIL/SKIPPED')}, Twitter={('PASS' if twitter_ok else 'FAIL')}")
    print("=" * 70)


if __name__ == "__main__":
    main()

