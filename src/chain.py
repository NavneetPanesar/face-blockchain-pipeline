import hashlib
import json
import time
from datetime import datetime, timezone

from web3 import Web3

# Must match the deployed SocialVerifier.sol exactly
ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "dataHash",  "type": "bytes32"},
            {"internalType": "string",  "name": "postUrl",   "type": "string"},
            {"internalType": "uint16",  "name": "similarity","type": "uint16"},
        ],
        "name": "store",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "dataHash", "type": "bytes32"},
        ],
        "name": "verify",
        "outputs": [
            {"internalType": "bool",    "name": "exists",    "type": "bool"},
            {"internalType": "string",  "name": "postUrl",   "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "address", "name": "submitter", "type": "address"},
            {"internalType": "uint16",  "name": "similarity","type": "uint16"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

EXPLORERS = {
    11155111: "https://sepolia.etherscan.io/tx/",
    80002:    "https://amoy.polygonscan.com/tx/",
}


class BlockchainVerifier:
    def __init__(self, rpc_url: str, private_key: str, contract_address: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot reach Ethereum node: {rpc_url}")

        self.account  = self.w3.eth.account.from_key(private_key)
        self.addr     = Web3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(address=self.addr, abi=ABI)
        self.chain_id = self.w3.eth.chain_id

    def info(self) -> dict:
        bal = self.w3.eth.get_balance(self.account.address)
        return {
            "chain_id": self.chain_id,
            "address":  self.account.address,
            "balance":  float(self.w3.from_wei(bal, "ether")),
        }

    @staticmethod
    def compute_hash(candidate: dict, embedding: list) -> bytes:
        """
        SHA-256 of a canonical JSON that binds:
        - the discovered post URL
        - a fingerprint of the original face embedding
        - the result title and source
        - the current unix timestamp

        This means the on-chain record proves WHICH FACE was matched
        to WHICH POST, at WHAT TIME — tamper-evident end to end.
        """
        face_fingerprint = hashlib.sha256(
            json.dumps(
                [round(v, 6) for v in embedding[:32]], sort_keys=True
            ).encode()
        ).hexdigest()

        canonical = json.dumps(
            {
                "url":              candidate.get("url", ""),
                "title":            candidate.get("title", ""),
                "source":           candidate.get("source", ""),
                "face_fingerprint": face_fingerprint,
                "ts":               int(time.time()),
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).digest()

    def store(
        self,
        data_hash: bytes,
        post_url: str,
        similarity_score: float,
    ) -> dict:
        """
        Write (dataHash, postUrl, similarity) to the contract.
        similarity_score is a float 0.0–1.0; stored as uint16 × 10000.
        Returns tx details dict.
        """
        similarity_int = min(10000, max(0, int(round(similarity_score * 10000))))

        nonce = self.w3.eth.get_transaction_count(self.account.address)
        try:
            gas = self.contract.functions.store(
                data_hash, post_url, similarity_int
            ).estimate_gas({"from": self.account.address})
            gas = int(gas * 1.25)
        except Exception:
            gas = 150_000   # safe fallback

        tx = self.contract.functions.store(
            data_hash, post_url, similarity_int
        ).build_transaction(
            {
                "from":     self.account.address,
                "nonce":    nonce,
                "gas":      gas,
                "gasPrice": self.w3.eth.gas_price,
            }
        )

        signed  = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        base = EXPLORERS.get(self.chain_id, "")
        return {
            "tx_hash":   tx_hash.hex(),
            "block":     receipt.blockNumber,
            "gas_used":  receipt.gasUsed,
            "status":    receipt.status,        # 1 = success, 0 = reverted
            "explorer":  base + tx_hash.hex() if base else "",
            "data_hash": data_hash.hex(),
        }

    def verify(self, data_hash: bytes) -> dict:
        """Read the record back from the contract. Returns verification dict."""
        exists, post_url, ts, submitter, sim_int = (
            self.contract.functions.verify(data_hash).call()
        )
        ts_human = (
            datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            if ts > 0 else "—"
        )
        return {
            "exists":     exists,
            "post_url":   post_url,
            "timestamp":  ts,
            "ts_human":   ts_human,
            "submitter":  submitter,
            "similarity": round(sim_int / 10000, 4),   # back to float
            "data_hash":  data_hash.hex(),
        }
