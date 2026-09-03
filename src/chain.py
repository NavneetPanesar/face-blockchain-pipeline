import hashlib
import json
from datetime import datetime, timezone

from web3 import Web3
from dotenv import load_dotenv
import os


load_dotenv()


class BlockchainVerifier:
    ABI = [
        {
            "inputs": [
                {"internalType": "bytes32", "name": "dataHash", "type": "bytes32"},
                {"internalType": "string", "name": "postUrl", "type": "string"},
                {"internalType": "uint16", "name": "similarity", "type": "uint16"},
            ],
            "name": "store",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "bytes32", "name": "dataHash", "type": "bytes32"}
            ],
            "name": "verify",
            "outputs": [
                {"internalType": "bool", "name": "exists", "type": "bool"},
                {"internalType": "string", "name": "postUrl", "type": "string"},
                {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                {"internalType": "address", "name": "submitter", "type": "address"},
                {"internalType": "uint16", "name": "similarity", "type": "uint16"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    def __init__(self):
        rpc_url = os.getenv("RPC_URL")
        private_key = os.getenv("PRIVATE_KEY")
        contract_address = os.getenv("CONTRACT_ADDRESS")

        if not rpc_url:
            raise RuntimeError("RPC_URL is missing from .env")

        if not private_key:
            raise RuntimeError("PRIVATE_KEY is missing from .env")

        if not contract_address:
            raise RuntimeError("CONTRACT_ADDRESS is missing from .env")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not self.w3.is_connected():
            raise RuntimeError("Could not connect to the Ethereum RPC")

        self.account = self.w3.eth.account.from_key(private_key)
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=self.ABI,
        )

    @staticmethod
    def compute_hash(candidate: dict, embedding: list) -> bytes:
        """
        Create a deterministic SHA-256 evidence fingerprint.

        The hash binds:
        - the discovered post URL
        - the result title
        - the result source
        - a fingerprint of the face embedding

        The blockchain transaction/block timestamp provides the
        authoritative time at which the evidence was recorded.
        """

        face_fingerprint = hashlib.sha256(
            json.dumps(
                [round(v, 6) for v in embedding[:32]],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        canonical = {
            "url": candidate.get("url", ""),
            "title": candidate.get("title", ""),
            "source": candidate.get("source", ""),
            "face_fingerprint": face_fingerprint,
        }

        canonical_json = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

        return hashlib.sha256(
            canonical_json.encode("utf-8")
        ).digest()

    def store(self, data_hash: bytes, post_url: str, similarity: float) -> dict:
        similarity_uint16 = int(round(similarity * 10000))

        if similarity_uint16 < 0:
            similarity_uint16 = 0

        if similarity_uint16 > 10000:
            similarity_uint16 = 10000

        nonce = self.w3.eth.get_transaction_count(self.account.address)

        tx = self.contract.functions.store(
            data_hash,
            post_url,
            similarity_uint16,
        ).build_transaction(
            {
                "from": self.account.address,
                "nonce": nonce,
                "chainId": self.w3.eth.chain_id,
            }
        )

        try:
            tx["gas"] = self.w3.eth.estimate_gas(tx)
        except Exception:
            tx["gas"] = 150000

        latest_block = self.w3.eth.get_block("latest")

        base_fee = latest_block.get("baseFeePerGas")

        if base_fee is not None:
            tx["maxPriorityFeePerGas"] = self.w3.to_wei(1, "gwei")
            tx["maxFeePerGas"] = base_fee * 2 + self.w3.to_wei(
                1, "gwei"
            )
        else:
            tx["gasPrice"] = self.w3.eth.gas_price

        signed = self.account.sign_transaction(tx)

        tx_hash = self.w3.eth.send_raw_transaction(
            signed.raw_transaction
        )

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "tx_hash": tx_hash.hex(),
            "block": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "status": receipt.status,
            "explorer": (
                f"https://sepolia.etherscan.io/tx/{tx_hash.hex()}"
            ),
            "data_hash": data_hash.hex(),
        }

    def verify(self, data_hash: bytes) -> dict:
        result = self.contract.functions.verify(
            data_hash
        ).call()

        exists, post_url, timestamp, submitter, similarity = result

        readable_time = None

        if timestamp:
            readable_time = datetime.fromtimestamp(
                timestamp,
                timezone.utc,
            ).isoformat()

        return {
            "exists": exists,
            "post_url": post_url,
            "timestamp": timestamp,
            "timestamp_utc": readable_time,
            "submitter": submitter,
            "similarity": similarity / 10000,
        }