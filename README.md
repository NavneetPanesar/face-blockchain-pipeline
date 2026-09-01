# face-blockchain-pipeline
# Face ID + Blockchain Verification Pipeline

A pipeline that detects a face from a photo, finds real matching social
media posts via Google Lens reverse-image search, then writes a
tamper-evident SHA256 record to the Ethereum Sepolia testnet.

## Pipeline
Photo → deepface (128-dim embedding) → imgbb upload → SerpAPI Google Lens
→ best social media match → SHA256 hash → Ethereum Sepolia (store)
→ on-chain verify → results.json


## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your API keys
python pipeline.py your_photo.jpg
```

## Environment variables

| Variable | Source |
|---|---|
| SERPAPI_KEY | serpapi.com free plan |
| IMGBB_KEY | api.imgbb.com |
| RPC_URL | Infura Sepolia endpoint |
| PRIVATE_KEY | MetaMask account private key |
| CONTRACT_ADDRESS | Deployed SocialVerifier.sol (Sepolia) |

## Blockchain used

**Ethereum Sepolia testnet** — Chain ID 11155111
Contract: `SocialVerifier.sol` stores a `bytes32` SHA256 hash + post URL.
Verify with: `python pipeline.py photo.jpg` (re-reads chain at the end)
Or inspect directly on [Sepolia Etherscan](https://sepolia.etherscan.io)

## Known limitations

- SerpAPI free plan = 100 searches/month
- Google Lens finds matches only when the face has web presence
- imgbb hosted URL expires after 10 min (hash is permanent on-chain)
- Sepolia is a testnet; no real ETH used




