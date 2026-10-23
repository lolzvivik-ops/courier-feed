"""
C3 — TRON TRC-20 USDT transaction verification via TronGrid API.

verify_trc20_tx(tx_hash, expected_cents, to_address)  → VerifyResult

No web3 library — raw HTTPS to TronGrid REST API.
USDT contract on TRON mainnet: TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t

Entry points:
  verify_trc20_tx(tx_hash, expected_cents, to_address)
  save_payout_check(payout_id, tx_hash, ...)            → DB row
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TRONGRID_API   = "https://api.trongrid.io"
_USDT_CONTRACT  = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
_USDT_DECIMALS  = 6          # USDT TRC-20 uses 6 decimals
_CONFIRMATIONS  = 20         # required confirmations
_TOLERANCE_PCT  = 0.01       # 1% tolerance on amount mismatch


@dataclass
class VerifyResult:
    tx_hash:       str
    status:        str          # verified | needs_human | failed | pending
    expected_cents: int
    actual_cents:  Optional[int]
    confirmations: Optional[int]
    to_address:    Optional[str]
    from_address:  Optional[str]
    discrepancy:   Optional[dict]
    raw_tx:        Optional[dict]


def _usdt_to_cents(raw_amount: int) -> int:
    """Convert raw TRC-20 amount (6 decimals) to USD cents."""
    return int(raw_amount / 10 ** (_USDT_DECIMALS - 2))   # / 10^4 → cents


def _get_tx(tx_hash: str, api_key: str = "") -> Optional[dict]:
    """Fetch transaction info from TronGrid REST."""
    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["TRON-PRO-API-KEY"] = api_key

    url = f"{_TRONGRID_API}/v1/transactions/{tx_hash}"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("TronGrid tx fetch failed: %s", exc)
        return None


def _get_trc20_info(tx_hash: str, api_key: str = "") -> Optional[dict]:
    """Fetch TRC-20 token transfer info."""
    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["TRON-PRO-API-KEY"] = api_key

    url = f"{_TRONGRID_API}/v1/transactions/{tx_hash}/trc20transfers"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        transfers = data.get("data", [])
        for t in transfers:
            if t.get("token_info", {}).get("address","").upper() == _USDT_CONTRACT.upper():
                return t
        return transfers[0] if transfers else None
    except Exception as exc:
        logger.warning("TronGrid TRC-20 fetch failed: %s", exc)
        return None


def verify_trc20_tx(
    tx_hash:        str,
    expected_cents: int,
    to_address:     str,
    api_key:        str = "",
    max_wait_secs:  int = 120,
) -> VerifyResult:
    """
    Verify a TRON TRC-20 USDT transaction.
    Polls until confirmed or timeout.

    Rules (from TZ §C3):
      - Wrong address → needs_human
      - Amount mismatch > 1% → needs_human
      - Confirmations < 20 → poll/wait
      - All OK → verified
    """
    if not api_key:
        api_key = os.getenv("TRONGRID_API_KEY", "")

    deadline   = time.time() + max_wait_secs
    raw_tx     = None
    transfer   = None
    confs      = None

    while time.time() < deadline:
        raw_tx   = _get_tx(tx_hash, api_key)
        transfer = _get_trc20_info(tx_hash, api_key)

        if raw_tx and raw_tx.get("data"):
            tx_data = raw_tx["data"][0] if isinstance(raw_tx.get("data"), list) else raw_tx
            confs   = tx_data.get("confirmations", 0)
            if confs >= _CONFIRMATIONS:
                break
        time.sleep(10)

    if not transfer:
        return VerifyResult(
            tx_hash=tx_hash, status="failed",
            expected_cents=expected_cents, actual_cents=None,
            confirmations=confs, to_address=None, from_address=None,
            discrepancy={"reason": "transfer_not_found"}, raw_tx=raw_tx,
        )

    actual_raw    = int(transfer.get("value", 0))
    actual_cents  = _usdt_to_cents(actual_raw)
    actual_to     = transfer.get("to", "")
    actual_from   = transfer.get("from", "")

    # address check
    if actual_to.lower() != to_address.lower():
        return VerifyResult(
            tx_hash=tx_hash, status="needs_human",
            expected_cents=expected_cents, actual_cents=actual_cents,
            confirmations=confs, to_address=actual_to, from_address=actual_from,
            discrepancy={"field":"address","expected":to_address,"actual":actual_to},
            raw_tx=transfer,
        )

    # amount check
    if expected_cents > 0:
        diff_pct = abs(actual_cents - expected_cents) / expected_cents
        if diff_pct > _TOLERANCE_PCT:
            return VerifyResult(
                tx_hash=tx_hash, status="needs_human",
                expected_cents=expected_cents, actual_cents=actual_cents,
                confirmations=confs, to_address=actual_to, from_address=actual_from,
                discrepancy={
                    "field":    "amount",
                    "expected": expected_cents,
                    "actual":   actual_cents,
                    "diff_pct": round(diff_pct * 100, 2),
                },
                raw_tx=transfer,
            )

    # confirmations check
    if confs is not None and confs < _CONFIRMATIONS:
        return VerifyResult(
            tx_hash=tx_hash, status="pending",
            expected_cents=expected_cents, actual_cents=actual_cents,
            confirmations=confs, to_address=actual_to, from_address=actual_from,
            discrepancy=None, raw_tx=transfer,
        )

    return VerifyResult(
        tx_hash=tx_hash, status="verified",
        expected_cents=expected_cents, actual_cents=actual_cents,
        confirmations=confs, to_address=actual_to, from_address=actual_from,
        discrepancy=None, raw_tx=transfer,
    )


def save_payout_check(
    payout_id:      str,
    tx_hash:        str,
    network:        str,
    expected_cents: int,
    result:         VerifyResult,
    wallet_id:      Optional[str] = None,
) -> dict:
    """Persist verification result to payout_checks table."""
    import json
    from ..engine.db import execute
    import uuid as _uuid

    row = execute(
        """INSERT INTO payout_checks
           (id, payout_id, tx_hash, network, wallet_id,
            expected_cents, actual_cents, confirmations, status,
            discrepancy, raw_tx)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (tx_hash, network) DO UPDATE SET
             actual_cents=EXCLUDED.actual_cents,
             confirmations=EXCLUDED.confirmations,
             status=EXCLUDED.status,
             discrepancy=EXCLUDED.discrepancy,
             raw_tx=EXCLUDED.raw_tx,
             checked_at=NOW()
           RETURNING *""",
        (str(_uuid.uuid4()), payout_id, tx_hash, network, wallet_id,
         expected_cents, result.actual_cents, result.confirmations,
         result.status,
         json.dumps(result.discrepancy) if result.discrepancy else None,
         json.dumps(result.raw_tx)      if result.raw_tx      else None),
        fetch="one",
    )
    return dict(row) if row else {}
