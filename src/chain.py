import hashlib
import json
import time
from web3 import Web3

# Minimal ABI — only the functions we call
ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "dataHash", "type": "bytes32"},
            {"internalType": "string",  "name": "postUrl",  "type": "string"},
        ],
        "name": "store",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "dataHash", "type": "bytes32"}],
        "name": "verify",
        "outputs": [
            {"internalType": "bool",    "name": "exists",    "type": "bool"},
            {"internalType": "string",  "name": "postUrl",   "type": "string"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
            {"internalType": "address", "name": "submitter", "type": "address"},
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
            raise ConnectionError(f"Cannot reach node: {rpc_url}")
        self.account  = self.w3.eth.account.from_key(private_key)
        self.addr     = Web3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(address=self.addr, abi=ABI)
        self.chain_id = self.w3.eth.chain_id

    # ── Hashing ──────────────────────────────────────────────────────────
    @staticmethod
    def compute_hash(match: dict) -> bytes:
        canonical = json.dumps(
            {
                "url":    match.get("url", ""),
                "title":  match.get("title", ""),
                "source": match.get("source", ""),
                "ts":     int(time.time()),
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).digest()   # 32 bytes

    # ── Write to chain ───────────────────────────────────────────────────
    def store(self, data_hash: bytes, post_url: str) -> dict:
        nonce = self.w3.eth.get_transaction_count(self.account.address)
        try:
            gas = self.contract.functions.store(data_hash, post_url).estimate_gas(
                {"from": self.account.address}
            )
            gas = int(gas * 1.25)
        except Exception:
            gas = 120_000

        tx = self.contract.functions.store(data_hash, post_url).build_transaction(
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
            "tx_hash":     tx_hash.hex(),
            "block":       receipt.blockNumber,
            "gas_used":    receipt.gasUsed,
            "status":      receipt.status,          # 1 = success
            "explorer":    base + tx_hash.hex() if base else "",
            "data_hash":   data_hash.hex(),
        }

    # ── Read from chain ──────────────────────────────────────────────────
    def verify(self, data_hash: bytes) -> dict:
        exists, post_url, ts, submitter = self.contract.functions.verify(
            data_hash
        ).call()
        return {
            "exists":    exists,
            "post_url":  post_url,
            "timestamp": ts,
            "submitter": submitter,
            "data_hash": data_hash.hex(),
        }

    def info(self) -> dict:
        bal = self.w3.eth.get_balance(self.account.address)
        return {
            "chain_id": self.chain_id,
            "address":  self.account.address,
            "balance":  float(self.w3.from_wei(bal, "ether")),
        }
