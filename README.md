# 🔐 Face ID + Blockchain Verification

### Face Scan → Web/Social Discovery → Face Matching → SHA-256 → Ethereum → Verification

An end-to-end computer-vision and blockchain pipeline that discovers relevant web/social content from a face image, validates candidate images using FaceNet similarity, creates a tamper-evident evidence fingerprint, and verifies that fingerprint on the Ethereum Sepolia blockchain.

---

## 🏆 Working Proof

The complete pipeline has been successfully executed end-to-end:

| Metric | Result |
|---|---:|
| Face detected | ✅ 1 |
| Face embedding | **128 dimensions** |
| Reverse-image candidates | **59** |
| Social candidates | **29** |
| Best face similarity | **98.96%** |
| Evidence fingerprint | **SHA-256** |
| Blockchain | **Ethereum Sepolia** |
| Block | **11627478** |
| On-chain verification | **PASSED** |
| Final status | 🟢 **SUCCESS** |

**Verified transaction:**

`d93937fd0775b4468361b2dd3a94ebb9f97bc400a3977932dd677aca40616084`

👉 [View transaction on Sepolia Etherscan](https://sepolia.etherscan.io/tx/d93937fd0775b4468361b2dd3a94ebb9f97bc400a3977932dd677aca40616084)

---

## 🎯 What This Project Demonstrates

This project combines four different technologies into one verifiable workflow:

- **Computer Vision** to generate a facial embedding
- **Reverse Image Search** to discover relevant web/social candidates
- **Cryptographic Hashing** to create a deterministic evidence fingerprint
- **Blockchain** to record and verify that evidence

The key idea is to move from **discovery → visual comparison → evidence fingerprinting → immutable record → verification**.

---

## 🚀 Pipeline

```text
                         INPUT IMAGE
                              │
                              ▼
                 ┌────────────────────────┐
                 │ Face Detection +        │
                 │ FaceNet Embedding       │
                 └────────────┬───────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │ Google Lens             │
                 │ Reverse Image Search    │
                 └────────────┬───────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │ Web / Social Candidates │
                 └────────────┬───────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │ Face Similarity         │
                 │ Matching                │
                 └────────────┬───────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │ SHA-256 Evidence        │
                 │ Fingerprint             │
                 └────────────┬───────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │ Ethereum Sepolia        │
                 │ Blockchain              │
                 └────────────┬───────────┘
                              │
                              ▼
                    ✓ EVIDENCE VERIFIED ON-CHAIN
```

---

## 🔬 How It Works

### 1. Face Detection & Encoding

DeepFace with FaceNet detects the face, aligns it and generates a **128-dimensional facial embedding**.

### 2. Reverse-Image Search

The face crop is temporarily hosted and submitted to **Google Lens through SerpAPI**.

The search dynamically returns web and social-media candidates rather than relying on a hardcoded URL.

### 3. Face Similarity Matching

Candidate images are downloaded and processed using the same FaceNet model.

Cosine similarity is calculated between the input embedding and candidate embeddings.

Example successful run:

```text
Candidate 5  → 94.94%
Candidate 6  → 98.96%  ← best
Candidate 9  → 93.02%
Candidate 11 → 65.87%
```

The highest qualifying candidate is selected.

### 4. Evidence Fingerprinting

The selected evidence is represented deterministically using:

```text
URL
Title
Source
Face fingerprint
```

The canonical representation is hashed using **SHA-256**.

Example:

```text
a9c980164839b43ae66f50da42ddd704f18b1f33c7ee5819ad95a833ab7b9398
```

The timestamp is intentionally excluded from the evidence hash, allowing identical evidence to produce the same fingerprint.

### 5. Blockchain Storage

The evidence fingerprint, associated post URL and similarity information are recorded on **Ethereum Sepolia**.

### 6. On-Chain Verification

The blockchain record is read back and checked against the selected evidence.

The successful run confirmed:

```text
✓ Record exists
✓ URL matches
✓ On-chain similarity recorded: 98.96%
✓ Current matching similarity: 98.96%
✓ Evidence fingerprint verified
```

---

## 🔗 Blockchain

**Network:** Ethereum Sepolia

**Smart Contract:**

`0xD5d7203342B52CBF15E5B0404c15184A2a0eA120`

The complete image is **not stored on-chain**.

Instead, the system stores a compact cryptographic fingerprint:

```text
Candidate Evidence
       ↓
Canonical Representation
       ↓
SHA-256 Fingerprint
       ↓
Ethereum Sepolia
       ↓
Read Back
       ↓
Compare
       ↓
Verified ✓
```

This provides a tamper-evident record that can be independently inspected on the blockchain.

---

## 🧠 Technology Stack

| Technology | Role |
|---|---|
| Python 3.11 | Core pipeline |
| DeepFace | Face processing |
| FaceNet | Face embeddings |
| OpenCV | Image processing |
| Google Lens | Reverse-image search |
| SerpAPI | Search API |
| ImgBB | Temporary image hosting |
| NumPy | Numerical computation |
| Web3.py | Ethereum interaction |
| Ethereum Sepolia | Blockchain |
| SHA-256 | Evidence fingerprint |
| Rich | CLI interface |

---

## 📁 Project Structure

```text
face-blockchain-pipeline/
│
├── contracts/
│   └── FaceVerification.sol
│
├── src/
│   ├── face.py
│   ├── search.py
│   ├── match.py
│   └── chain.py
│
├── pipeline.py
├── requirements
├── .env.example
├── .gitignore
└── README.md
```

### Module Responsibilities

| File | Responsibility |
|---|---|
| `pipeline.py` | Orchestrates the complete six-stage workflow |
| `src/face.py` | Face detection, alignment and FaceNet embedding |
| `src/search.py` | Reverse-image search and candidate extraction |
| `src/match.py` | Candidate face detection and similarity matching |
| `src/chain.py` | SHA-256 fingerprinting and Ethereum interaction |
| `contracts/` | Smart-contract source |

---

## ⚙️ Setup

### Requirements

- Python 3.11
- SerpAPI API key
- ImgBB API key
- Ethereum Sepolia RPC endpoint
- Sepolia test ETH

### Install

```powershell
git clone https://github.com/NavneetPanesar/face-blockchain-pipeline.git
cd face-blockchain-pipeline
py -3.11 -m pip install -r requirements
```

Create a local `.env` file using `.env.example`:

```env
SERPAPI_KEY=your_serpapi_key
IMGBB_KEY=your_imgbb_key
RPC_URL=your_sepolia_rpc_url
PRIVATE_KEY=your_wallet_private_key
CONTRACT_ADDRESS=0xD5d7203342B52CBF15E5B0404c15184A2a0eA120
```

⚠️ **Never commit `.env` or expose private keys/API credentials.**

---

## ▶️ Run

Place an input image in the project directory and run:

```powershell
py -3.11 pipeline.py test.jpeg
```

Optional similarity threshold:

```powershell
py -3.11 pipeline.py test.jpeg --threshold 0.60
```

The CLI displays all six stages and saves execution results locally as `results_*.json`.

---

## 🔐 Important Design Note

The system separates **search discovery, visual similarity and blockchain evidence verification**.

A Google Lens related result is displayed as **provider-supplied metadata**. The pipeline does not independently infer a person's identity from a username, URL, page title or similarity score.

Likewise, the blockchain proves that the selected evidence fingerprint was recorded and can be verified later. It does **not independently establish real-world identity**.

This distinction is important when interpreting the output.

---

## ⚠️ Limitations

- Reverse-image-search results depend on external search-provider coverage and ranking.
- Face similarity can be affected by pose, lighting, image quality, occlusion and other factors.
- External APIs may impose rate limits or change their responses.
- The blockchain stores evidence fingerprints rather than the original image.
- The demonstration uses the Ethereum Sepolia test network.

---

## 🎯 Key Engineering Features

- Dynamic web/social discovery instead of a hardcoded post
- 128-dimensional FaceNet embeddings
- Cosine-similarity candidate verification
- Deterministic SHA-256 evidence fingerprinting
- Real Ethereum Sepolia transaction
- On-chain read-back verification
- Credential protection through `.gitignore`
- Complete six-stage CLI pipeline

### Verification Model

```text
DISCOVER
   ↓
COMPARE
   ↓
FINGERPRINT
   ↓
STORE
   ↓
READ
   ↓
VERIFY ✓
```

---

## 👨‍💻 Project

**Face ID + Blockchain Verification**

Built as a technical demonstration combining:

**Computer Vision · Reverse Image Search · Cryptography · Blockchain**

[GitHub Repository](https://github.com/NavneetPanesar/face-blockchain-pipeline)
