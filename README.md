# Atria

Atria is an **open-source decentralized social marketplace** that merges **social networking, federated protocols, AI-powered interactions, and Web3 incentives** into a single ecosystem.

## Features

-   **Decentralized & Federated**: Built on **ActivityPub**, enabling interoperability with platforms like Mastodon and PeerTube.
-   **Web3 & Web2 Integration**: Leverages **Ethereum smart contracts** for governance, content ownership, and token-based rewards, while also supporting traditional payment methods like **PayPal, Stripe, and other Web2 transactions**.
-   **AI-Powered Personalization**: Smart feed recommendations, AI-driven moderation, and enhanced search capabilities.
-   **Social Q&A & Knowledge Economy**: Users can post bounties for answers, monetize expertise, and engage in tokenized knowledge sharing.
-   **User-Owned Digital Identity**: Decentralized identity via **Ethereum Name Service (ENS) and Verifiable Credentials**.
-   **Creator-Centric Monetization**: Subscription-based content, direct tipping, and blockchain-backed transactions without intermediaries.

## Security Features

-   **Environment-based Configuration**: All sensitive settings managed via environment variables
-   **Secure by Default**: Production-ready security settings enabled out of the box
-   **HTTPS Enforcement**: Automatic HTTPS redirection and HSTS configuration
-   **XSS Protection**: Browser XSS filtering and Content Security Policy
-   **CSRF Protection**: Configurable trusted origins and secure cookie handling
-   **Secret Management**: No hardcoded secrets, all managed via environment variables

## Getting Started

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/atria.git
    cd atria
    ```

2. Set up your environment:

    ```bash
    # Create and activate a virtual environment
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

    # Install development dependencies using uv
    ./scripts/setup_dev.py
    ```

3. Configure your environment:

    ```bash
    # Copy the environment template
    cp .env.example .env

    # Generate a secure secret key
    python -c "import secrets; print(secrets.token_urlsafe(50))"

    # Edit .env with your settings
    nano .env  # or use your preferred editor
    ```

4. Start the development server:
    ```bash
    python manage.py migrate
    python manage.py runserver
    ```

## Environment Configuration

The project uses environment variables for configuration. Key variables include:

### Required Settings

-   `SECRET_KEY`: Django secret key for cryptographic operations
-   `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
-   `DEBUG`: Set to 0 in production, 1 for development
-   `DATABASE_URL`: Database connection string

### Security Settings

-   `CSRF_TRUSTED_ORIGINS`: List of trusted origins for CSRF protection
-   `SECURE_SSL_REDIRECT`: Force HTTPS (recommended in production)
-   `SESSION_COOKIE_SECURE`: Secure session cookies (HTTPS only)
-   `CSRF_COOKIE_SECURE`: Secure CSRF cookies (HTTPS only)

### Optional Features

-   `PAYPAL_CLIENT_ID`: PayPal integration credentials
-   `DROPBOX_OAUTH2_TOKEN`: Dropbox storage integration
-   Additional settings as needed for your deployment

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3. Set up environment variables:
    ```bash
    cp .env.example .env
    ```
4. Run migrations and start the server:
    ```bash
    python manage.py migrate
    python manage.py runserver
    ```

## Roadmap

-   [ ] Implement ActivityPub federation.
-   [ ] AI-powered content discovery and moderation.
-   [ ] Ethereum-based DAO for governance.
-   [ ] Decentralized reputation system.
-   [ ] Expand Web3 integrations (ENS, NFTs for content ownership).
-   [ ] Support Web2 payment providers (PayPal, Stripe, etc.).

## Contributing

We welcome contributions! Please check the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Atria is released under the **MIT License**.
