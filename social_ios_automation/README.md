# Social iOS Automation — Operations README

## Stack at a glance

```
PostgreSQL 15+          — job queue, accounts, metrics, audit log
FastAPI + uvicorn       — REST API for Кабинет (model) + Пульт (owner) iOS apps
APNs HTTP/2             — push via .p8 ES256 JWT (no third-party APNs lib)
TronGrid REST           — TRON TRC-20 USDT payment verification
Telegram Bot API        — daily owner digest
ffmpeg                  — video transcoding to 9:16 1080×1920 H.264+AAC
```

All platform calls use reversed **iOS private mobile APIs** (DMCA §1201(j) security-research basis).  
No Selenium, no Playwright, no CDP — pure HTTP with device-fingerprinted iOS user-agents.

---

## Quick start

```bash
# 1. copy and fill env
cp .env.example .env

# 2. create DB
psql $DATABASE_URL -f social_ios_automation/schema/001_initial.sql

# 3. install deps
pip install -r social_ios_automation/requirements.txt

# 4. start API server
uvicorn social_ios_automation.api.server:app --host 0.0.0.0 --port 8000

# 5. start scheduler (separate process)
python -m social_ios_automation.main scheduler
```

### Required environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` |
| `APNS_TEAM_ID` | 10-char Apple Team ID |
| `APNS_KEY_ID` | 10-char APNs key ID |
| `APNS_KEY_PATH` | Path to `AuthKey_XXXXXXXXXX.p8` |
| `APNS_BUNDLE_ID_CABINET` | Bundle ID for Кабинет app |
| `APNS_BUNDLE_ID_REMOTE` | Bundle ID for Пульт app |
| `TELEGRAM_BOT_TOKEN` | Bot API token for daily digests |
| `TELEGRAM_CHAT_ID` | Operator chat/group ID |
| `TRONGRID_API_KEY` | TronGrid API key (optional, raises rate limit) |

---

## Platform API limits (rules memo — записка по правилам)

### Fansly
| Action | Safe daily limit | Notes |
|---|---|---|
| Feed post | 6 | platform hard cap ~10, stay under |
| PPV send | 20/h | per account |
| Subscriber list fetch | 1×/hour | for metrics only |
| Profile update | 2/day | triggers review if frequent |

### Instagram
| Action | Safe daily limit | Notes |
|---|---|---|
| Feed post | 3 | IG limits ~10 but lower = safer |
| Story | 5 | |
| Reel | 2 | video-specific pipeline |
| DM | 50 | new accounts: 10; after 90 days: 50 |
| Follow | 100 | not used in current flow |

### TikTok
| Action | Safe daily limit | Notes |
|---|---|---|
| Video upload | 3 | TikTok Studio upload endpoint |
| DM | 30 | new accounts limited to 10 |
| Profile update | 1/day | |

### X (Twitter)
| Action | Safe daily limit | Notes |
|---|---|---|
| Tweet | 10 | free API tier: 500/month total |
| DM | 50 | per account |
| Media upload | 10 | chunked, max 512MB video |

---

## Runbook

### Scenario 1 — "The platform changed its API" (сайт поменялся)

**Symptoms:**  
- Smoke test fails for an account  
- `publisher_stopped` push sent to owner  
- Jobs fail with `LoginError` or HTTP 400/403  

**Steps:**

1. In Пульт → Аккаунты → find degraded account (red status)
2. Tap **"Smoke test"** to confirm failure
3. Switch account to **"Confirmation" mode** (all actions need manual OK) — this halts auto-publishing while you fix
4. On your dev machine:
   ```bash
   # Capture a fresh request with mitmproxy or Charles
   # Update the offending endpoint constant in platforms/<platform>.py
   # Update headers/signing if the platform rotated its app version
   python -m social_ios_automation.main smoke-test --account-id <id>
   ```
5. Once smoke test passes, flip account back to **Auto** mode
6. Re-queue any failed jobs:
   ```sql
   UPDATE publish_jobs SET status='queued', attempts=0
   WHERE status='failed' AND account_id='<id>'
     AND created_at > NOW() - INTERVAL '24 hours';
   ```

---

### Scenario 2 — "Account is paused" (аккаунт на паузе)

**Symptoms:**  
- `account_login_required` or `account_warning` push  
- Account status = `login_required` or `limited`  

**Steps:**

1. In Пульт → Аккаунты, the account shows amber/red badge
2. Tap **Re-login** — opens login flow for that account
3. After successful re-login:
   - New session cookies saved to `session_file` path
   - Status auto-resets to `active` by health check
4. If account shows `limited`:
   - Reduce daily limits in account settings (Пульт → Аккаунты → Лимиты)
   - Wait 24–48 h before resuming
   - Keep in **Confirmation** mode until first successful post
5. If repeated logins fail: rotate IP via proxy pool setting, or manually re-create account

**DB check:**
```sql
SELECT id, platform, username, status, last_login_check
FROM platform_accounts
WHERE status NOT IN ('active')
ORDER BY last_login_check DESC;
```

---

### Scenario 3 — "Payout doesn't add up" (выплата не сходится)

**Symptoms:**  
- `period_needs_review` push  
- `period_drafts.needs_review = TRUE`  
- `discrepancy_pct > 2.0` between Fansly dashboard and daily cross-check  

**Steps:**

1. In Пульт → Деньги → Периоды, tap the flagged period
2. Review the discrepancy detail:
   ```sql
   SELECT * FROM period_drafts
   WHERE needs_review = TRUE
   ORDER BY created_at DESC LIMIT 5;
   ```
3. Cross-check manually:
   - In Fansly → Creator Dashboard → Earnings for the period dates
   - Compare `gross_cents` in DB vs platform-reported gross
4. Common causes:
   - **Chargeback processed after snapshot**: re-run `calculate_period()` after 48 h
   - **Platform fee changed**: update `FANSLY_PLATFORM_FEE` in `money/periods.py`
   - **Currency rounding**: acceptable if `discrepancy_pct < 2.0`
5. If manual reconciliation confirms correct:
   ```sql
   UPDATE period_drafts SET needs_review = FALSE, reviewed_by = '<your_id>'
   WHERE id = '<draft_id>';
   ```
6. Generate proof screenshot via Пульт → Деньги → Создать пруф
7. For TRON payment verification, paste tx hash in Пульт → Деньги → Верифицировать

---

### Scenario 4 — "Pushes are not arriving" (пуши не приходят)

**Symptoms:**  
- Notifications not showing on model or owner device  
- `notifications.status = 'error'` in DB  

**Checklist:**

1. **Device registered?**
   ```sql
   SELECT * FROM devices WHERE user_id = '<user_id>';
   ```
   If empty: user must re-open the app and allow notifications — device auto-registers on launch.

2. **APNs certificate not expired?**
   - `.p8` keys do not expire, but check `APNS_KEY_ID` matches the key file
   - Verify `APNS_BUNDLE_ID_CABINET` / `APNS_BUNDLE_ID_REMOTE` match app bundle IDs

3. **Quiet hours blocking?**
   ```sql
   SELECT * FROM notification_settings WHERE user_id = '<user_id>';
   ```
   Check `quiet_start` / `quiet_end`. Urgent notifications (account alerts) bypass quiet hours on the server but still need `interruption-level: time-sensitive` to break iOS Focus — verify app declares `time-sensitive` in entitlements.

4. **Spam cap hit?**
   ```sql
   SELECT event_type, COUNT(*) AS cnt, DATE(created_at)
   FROM notifications
   WHERE user_id = '<user_id>'
     AND created_at > NOW() - INTERVAL '1 day'
   GROUP BY 1, 3
   ORDER BY 2 DESC;
   ```
   Models capped at 3 same-event-type per day. Owners deduped within 10 min.

5. **APNs error response?**
   ```sql
   SELECT id, event_type, status, apns_message_id, created_at
   FROM notifications
   WHERE user_id = '<user_id>' AND status = 'error'
   ORDER BY created_at DESC LIMIT 20;
   ```
   Common APNs errors:
   - `BadDeviceToken` → device unregistered, delete from `devices` table
   - `ExpiredToken` → same as above
   - `TooManyRequests` → APNs rate-limited; reduce notification frequency
   - `Unregistered` → user uninstalled the app

6. **API server running?**
   ```bash
   curl http://localhost:8000/healthz
   ```

---

## Architecture diagram

```
iOS Кабинет app ──────┐
                       ├──▶ FastAPI /jobs       ──▶ publish_jobs table
iOS Пульт app ─────────┘    /accounts                ↑
                             /notifications        Scheduler
                                                   │  ├─ Worker (poll 5s)
                                                   │  │    └─ Platform clients
                                                   │  │         IG / TT / X / Reddit / Fansly
                                                   │  ├─ Health (1h)
                                                   │  ├─ Metrics (03:xx UTC daily)
                                                   │  └─ Calendar (6h)
                                                   │
                                     NotificationService
                                          │
                                          ├─ APNs HTTP/2 (ES256 JWT)
                                          └─ Telegram digest (03:xx UTC)
```

---

## Smoke test

```bash
python -m social_ios_automation.main smoke-test --account-id <uuid>
```

Runs the cheapest authenticated call for the account's platform:
- **Fansly** → `GET /api/v1/account/stats`
- **Instagram** → `GET /api/v1/accounts/current_user/`
- **TikTok** → `GET /api/v2/user/info/`
- **X (Twitter)** → `GET /2/users/me`
- **Reddit** → `GET /api/v1/me`

Returns OK / DEGRADED / DOWN and updates account status in DB.

---

## File layout

```
social_ios_automation/
├── config.py                  # platform app IDs, signing keys, limits
├── core/
│   ├── crypto.py              # IG signed_body, TT X-Gorgon, OAuth1, password encrypt
│   ├── device.py              # iOS device fingerprints (iPhone 12–14 Pro, iOS 15–16)
│   └── session.py             # base HTTP session, retry adapter, jitter sleep
├── platforms/
│   ├── fansly.py              # Fansly private API client
│   ├── instagram.py           # Instagram iOS private API client
│   ├── tiktok.py              # TikTok iOS private API client
│   ├── twitter.py             # X iOS OAuth1 client
│   └── reddit.py              # Reddit iOS OAuth2 client
├── engine/
│   ├── db.py                  # ThreadedConnectionPool, with_conn, execute
│   ├── models.py              # ORM-lite: PlatformAccount, PublishJob, etc.
│   ├── publisher.py           # Worker: claim → auto-mode gate → dispatch
│   ├── scheduler.py           # Scheduler: health/metrics/calendar tasks
│   ├── health.py              # smoke_test, run_all_checks
│   ├── metrics.py             # collect_daily Fansly metrics
│   └── calendar.py            # buffer calculation, slot suggestion
├── features/
│   ├── autoupload.py          # JSON sidecar scheduled posts
│   ├── autoreg.py             # bulk account registration
│   └── autodm.py             # DM template engine with dedup
├── media/
│   └── processor.py           # ffmpeg transcoder, cover extractor
├── money/
│   ├── periods.py             # period draft calculation (C1)
│   ├── proof.py               # balance proof PNG (C2)
│   └── blockchain.py          # TRON TRC-20 USDT verification (C3)
├── notifications/
│   ├── catalog.py             # D3/D4: all 30+ event types with text + routing flags
│   ├── apns.py                # APNs HTTP/2, ES256 JWT, interruption-level
│   ├── service.py             # routing rules: quiet hours, spam cap, undisableable
│   └── telegram.py            # owner daily digest
├── api/
│   ├── server.py              # FastAPI app, lifespan, CORS, timing middleware
│   └── routes/
│       ├── jobs.py            # POST/GET/approve/cancel publish jobs
│       ├── notifications.py   # device register, settings, notification list
│       └── accounts.py        # account CRUD, auto-modes, metrics, health-check
├── utils/
│   └── proxy.py               # ProxyPool: round-robin + failover
├── schema/
│   └── 001_initial.sql        # full PostgreSQL migration (13 tables)
├── main.py                    # CLI: login/upload/reg/dm/scheduler/smoke-test
└── requirements.txt
```
