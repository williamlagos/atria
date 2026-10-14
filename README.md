# Atria

[![CI](https://github.com/williamlagos/atria/actions/workflows/ci.yml/badge.svg)](https://github.com/williamlagos/atria/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.x](https://img.shields.io/badge/django-5.x-green.svg)](https://www.djangoproject.com/)
[![Django Ninja](https://img.shields.io/badge/api-django--ninja-purple.svg)](https://django-ninja.rest-framework.com/)

**Atria** is an open-source decentralized social marketplace, knowledge economy, and federated publishing network. It orchestrates federated ActivityPub interactions, multi-rail commerce (Stripe, PayPal v2, Web3 EVM), AI-driven content discovery via Google Gemini, and tokenized social Q&A bounties into a cohesive platform.

---

## Architecture Overview

Atria is architected as an orchestrator application powered by three autonomous, standalone companion packages published independently to PyPI:

```
                          ┌─────────────────────────────────────────┐
                          │               ATRIA CORE                │
                          │  • Knowledge Economy & Social Q&A       │
                          │  • Dual-Rail Bounty Escrow (Fiat/ETH)   │
                          │  • Unified Django Ninja OpenAPI v1      │
                          │  • Reputation & Identity Mapping        │
                          └────┬─────────────────┬────────────────┬─┘
                               │                 │                │
            ┌──────────────────┘                 │                └──────────────────┐
            ▼                                    ▼                                   ▼
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│     django-socialize    │      │       django-ship       │      │      django-feedly      │
│  • ActivityPub Node     │      │  • Web2 Payments        │      │  • Google Gemini SDK    │
│  • Cavage HTTP Sigs     │      │    - Stripe Checkout    │      │  • Vector Embeddings    │
│  • WebFinger & NodeInfo │      │    - PayPal v2 REST     │      │  • Semantic Search      │
│  • Inboxes & Outboxes   │      │  • Web3 & Crypto        │      │  • Safety Moderation    │
│  • Mastodon / PeerTube  │      │    - SIWE (EIP-4361)    │      │  • Multi-Strategy Feeds │
│    Interoperability     │      │    - EVM On-Chain Tx    │      │    - Chronological      │
│                         │      │    - ENS Resolution     │      │    - Trending Gravity   │
│                         │      │  • Creator Tiers & Tips │      │    - Affinity Scoring   │
└─────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
```

---

## Features

### 1. Federated Social Network (`django-socialize`)
- **ActivityPub 2.0 Engine**: Bidirectional federation with Mastodon, Pixelfed, and PeerTube.
- **Cryptographic Security**: `draft-cavage-http-signatures` RSA-SHA256 request signing and verification with clock-skew detection.
- **Discovery**: Full `/.well-known/webfinger` and `/.well-known/nodeinfo` 2.0 protocol endpoints.
- **Collections & Actors**: Paginated outboxes, follower/following graphs, and background delivery via Celery.

### 2. Multi-Rail Commerce & Web3 (`django-ship`)
- **Web2 Gateways**: Stripe Checkout sessions, PaymentIntents, and PayPal v2 REST Orders (`create_order`, `capture_order`).
- **Sign-In with Ethereum (SIWE)**: EIP-4361 wallet authentication with cryptographic nonces and address recovery.
- **On-Chain Verification**: EVM transaction confirmation on Ethereum, Polygon, and Arbitrum.
- **ENS Integration**: Forward (`vitalik.eth` -> `0x...`) and reverse name resolution.
- **Creator Monetization**: Tiered memberships, recurring subscriptions, and direct tips across fiat and crypto.

### 3. AI Discovery & Safety Moderation (`django-feedly`)
- **Vector Embeddings**: 768-dimensional text embeddings powered by Google Gemini (`google-genai` SDK) with deterministic fallback for offline/test environments.
- **Automated Moderation**: Content safety evaluation across 5 categories (toxicity, harassment, hate speech, danger, spam) with quarantine audit logging.
- **Multi-Strategy Feeds**:
  - *Chronological*: Strict temporal order with automated safety quarantining.
  - *Trending*: Hacker News gravity engagement decay ($\frac{E+1}{(t+2)^{1.5}}$).
  - *Personalized*: Composite ranking blending social follow graph, semantic topic cosine similarity, and recency half-life.
- **Semantic Vector Search**: High-performance cosine similarity matching across any embedded model.

### 4. Knowledge Economy & Social Q&A (`atria.qa`)
- **Dual-Rail Bounty Escrow**: Post questions with bounties in USD (Stripe card hold) or ETH (EVM wallet hold).
- **Atomic Escrow Release**: Selecting an accepted answer automatically disburses funds to the author.
- **Topic Reputation**: Dynamic reputation scoring (+15 accepted answer, +10 upvote, -2 downvote) with badge tiers (*Novice*, *Contributor*, *Expert*, *Master*).
- **Federated Q&A**: Native ActivityPub `Question` and `Note` objects with JSON-LD content negotiation.

---

## Unified REST API (Django Ninja)

Interactive OpenAPI documentation is available at `/api/v1/docs`.

| Prefix | Description | Key Endpoints |
|---|---|---|
| `/api/v1/auth/` | Identity & Auth | `POST /register`, `POST /login`, `POST /logout`, `GET /me`, `GET /siwe/nonce`, `POST /siwe/verify` |
| `/api/v1/social/` | Federated Network | `GET /actors`, `GET /actors/{user}`, `POST /follow`, `POST /unfollow`, `GET /actors/{user}/outbox`, `POST /activities` |
| `/api/v1/shop/` | Marketplace | `GET /products`, `POST /products`, `GET /cart`, `POST /cart/items`, `GET /orders`, `POST /orders`, `GET /creators/{id}/tiers` |
| `/api/v1/payments/` | Payment Rails | `POST /stripe/checkout`, `POST /paypal/create-order`, `POST /paypal/capture-order`, `POST /web3/verify`, `GET /web3/ens/resolve`, `POST /tip` |
| `/api/v1/feeds/` | AI Discovery | `GET /chronological`, `GET /trending`, `GET /personalized`, `POST /search`, `GET /interests`, `POST /interests`, `POST /moderate` |
| `/api/v1/qa/` | Knowledge Economy | `GET /questions`, `POST /questions`, `GET /questions/{id}`, `POST /questions/{id}/answers`, `POST /questions/{id}/accept/{answer_id}`, `POST /answers/{id}/vote`, `GET /questions/{id}/related`, `GET /reputation/{user}` |

---

## Development Setup

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker & Docker Compose (for PostgreSQL and Redis)

### Quick Start

1. Clone Atria and its companion satellite repositories:
   ```bash
   mkdir -p ~/Developer && cd ~/Developer
   git clone https://github.com/williamlagos/atria.git
   git clone https://github.com/williamlagos/django-socialize.git socialize
   git clone https://github.com/williamlagos/django-ship.git shipping
   git clone https://github.com/williamlagos/django-feedly.git feedly
   cd atria
   ```

2. Run the automated development setup:
   ```bash
   python scripts/setup_dev.py
   ```
   *This script installs dependencies via `uv`, links the local companion libraries in editable mode, starts PostgreSQL & Redis containers, runs migrations, and configures pre-commit hooks.*

3. Start background worker and web server:
   ```bash
   # Terminal 1: Celery Worker
   .venv/bin/celery -A atria worker -l info

   # Terminal 2: Web Server
   .venv/bin/python manage.py runserver 0.0.0.0:8000
   ```

4. Open `atria.code-workspace` in VS Code to edit Atria and all 3 companion packages concurrently.

---

## Production Deployment

### Docker Compose Production Stack

Atria includes a production Docker setup (`docker-compose.prod.yml`) featuring Gunicorn, Celery, PostgreSQL 16, and Redis 7:

```bash
# Build production image
docker build -t atria:prod .

# Launch production stack
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Variables

| Variable | Description | Default / Example |
|---|---|---|
| `SECRET_KEY` | Django cryptographic secret | Secure 50-char string |
| `DEBUG` | Django debug flag | `0` in production |
| `ALLOWED_HOSTS` | Allowed HTTP Host headers | `atria.example.com` |
| `SITE_DOMAIN` | Domain for ActivityPub Actor IDs & WebFinger | `atria.example.com` |
| `DATABASE_URL` | PostgreSQL connection string | `postgres://atria:pass@db:5432/atria` |
| `CELERY_BROKER_URL` | Redis broker URL | `redis://redis:6379/0` |
| `STRIPE_SECRET_KEY` | Stripe API Secret Key | `sk_live_...` |
| `PAYPAL_CLIENT_ID` | PayPal REST App Client ID | `client_...` |
| `PAYPAL_CLIENT_SECRET` | PayPal REST App Secret | `secret_...` |
| `WEB3_PROVIDER_URL` | EVM JSON-RPC provider | `https://eth.llamarpc.com` |
| `GEMINI_API_KEY` | Google Gemini API Key | `AIza...` |

---

## Testing & Quality Assurance

Run the test suite across all packages:

```bash
# Atria Core & Unified Routers (53 tests)
.venv/bin/python manage.py test

# django-socialize (29 tests)
.venv/bin/pytest ../socialize/src/socialize/tests

# django-ship (38 tests)
.venv/bin/pytest ../shipping/shipping/tests.py

# django-feedly (31 tests)
.venv/bin/pytest ../feedly/feedly/tests.py

# Format and Lint
pre-commit run --all-files
```

---

## License

Atria is released under the **MIT License**.
Individual satellite libraries (`django-socialize`, `django-ship`, `django-feedly`) are distributed under the **LGPL-3.0 License**.
