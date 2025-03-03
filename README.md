# Atria

Atria is an **open-source decentralized social marketplace** that merges **social networking, federated protocols, AI-powered interactions, and Web3 incentives** into a single ecosystem.

## Features

-   **Decentralized & Federated**: Built on **ActivityPub**, enabling interoperability with platforms like Mastodon and PeerTube.
-   **Web3 & Web2 Integration**: Leverages **Ethereum smart contracts** for governance, content ownership, and token-based rewards, while also supporting traditional payment methods like **PayPal, Stripe, and other Web2 transactions**.
-   **AI-Powered Personalization**: Smart feed recommendations, AI-driven moderation, and enhanced search capabilities.
-   **Social Q&A & Knowledge Economy**: Users can post bounties for answers, monetize expertise, and engage in tokenized knowledge sharing.
-   **User-Owned Digital Identity**: Decentralized identity via **Ethereum Name Service (ENS) and Verifiable Credentials**.
-   **Creator-Centric Monetization**: Subscription-based content, direct tipping, and blockchain-backed transactions without intermediaries.

## Getting Started

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/atria.git
    cd atria
    ```
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
