#!/usr/bin/env python3
"""CLI utility to register QMA on Arc Testnet ERC-8004 registries and record reputation feedback.

Usage:
  python scripts/register_erc8004_agent.py status
  python scripts/register_erc8004_agent.py register [--uri <metadata_uri>]
  python scripts/register_erc8004_agent.py feedback --score 98 --tag accurate_signal
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

from backend.app.core.config import (
    ARC_CHAIN_ID,
    ARC_EXPLORER,
    ARC_RPC_URL,
    ERC8004_AGENT_ID,
    ERC8004_IDENTITY_REGISTRY,
    ERC8004_REPUTATION_REGISTRY,
    ERC8004_VALIDATION_REGISTRY,
)
from backend.app.services.erc8004_service import (
    IDENTITY_ABI,
    REPUTATION_ABI,
    VALIDATION_ABI,
    get_onchain_identity,
    get_onchain_reputation_summary,
    record_reputation_feedback,
)


def get_web3():
    return Web3(Web3.HTTPProvider(ARC_RPC_URL))


def cmd_status(args):
    w3 = get_web3()
    print("=" * 60)
    print("QMA ERC-8004 ON-CHAIN AGENT STATUS (ARC TESTNET)")
    print("=" * 60)
    print(f"Arc RPC:                 {ARC_RPC_URL}")
    print(f"Chain ID:                {ARC_CHAIN_ID}")
    print(f"Current Block:           {w3.eth.block_number}")
    print(f"Agent ID:                {ERC8004_AGENT_ID}")
    print(f"Identity Registry:       {ERC8004_IDENTITY_REGISTRY}")
    print(f"Reputation Registry:     {ERC8004_REPUTATION_REGISTRY}")
    print(f"Validation Registry:     {ERC8004_VALIDATION_REGISTRY}")
    print("-" * 60)

    ident = get_onchain_identity(ERC8004_AGENT_ID)
    print(f"On-chain Verified:       {ident.get('onchain_verified')}")
    print(f"Owner Address:           {ident.get('owner')}")
    print(f"Token Metadata URI:      {ident.get('token_uri')}")
    print(f"Arc Explorer URL:        {ident.get('explorer_url')}")
    print("-" * 60)

    rep = get_onchain_reputation_summary(ERC8004_AGENT_ID)
    print(f"Average Reputation:      {rep.get('average_score')}/100")
    print(f"Total Feedbacks:         {rep.get('total_feedbacks')}")
    print(f"Verified Tags:           {', '.join(rep.get('verified_tags', []))}")
    val = rep.get("validation_status", {})
    print(f"Validation Status:       {val.get('status')} (Score: {val.get('score')}, Tag: {val.get('tag')})")
    print("=" * 60)


def cmd_register(args):
    w3 = get_web3()
    pk = os.getenv("AGENT_PRIVATE_KEY")
    if not pk:
        print("Error: AGENT_PRIVATE_KEY environment variable is required.")
        sys.exit(1)
    if not pk.startswith("0x"):
        pk = f"0x{pk}"

    account = w3.eth.account.from_key(pk)
    uri = args.uri or "https://genqma.vercel.app/.well-known/agent.json"
    registry_addr = Web3.to_checksum_address(ERC8004_IDENTITY_REGISTRY)
    contract = w3.eth.contract(address=registry_addr, abi=IDENTITY_ABI)

    print(f"Registering Agent identity for {account.address}...")
    print(f"Metadata URI: {uri}")

    nonce = w3.eth.get_transaction_count(account.address)
    tx = contract.functions.register(uri).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 250000,
        "gasPrice": w3.eth.gas_price,
        "chainId": ARC_CHAIN_ID,
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hex = f"0x{tx_hash.hex()}" if not tx_hash.hex().startswith("0x") else tx_hash.hex()
    print(f"Registration Tx Sent: {ARC_EXPLORER.rstrip('/')}/tx/{tx_hex}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    print(f"Mined in block: {receipt.blockNumber}, Status: {receipt.status}")

    events = contract.events.Transfer().process_receipt(receipt)
    if events:
        token_id = events[0]["args"]["tokenId"]
        print(f"SUCCESS! Minted ERC-8004 Agent ID: {token_id}")
        print(f"Explorer URL: {ARC_EXPLORER.rstrip('/')}/token/{ERC8004_IDENTITY_REGISTRY}?a={token_id}")
    else:
        print("Registration completed but Transfer event could not be decoded.")


def cmd_feedback(args):
    print(f"Submitting reputation feedback: Agent ID {args.agent_id or ERC8004_AGENT_ID}, Score: {args.score}, Tag: {args.tag}...")
    res = record_reputation_feedback(
        agent_id=args.agent_id or ERC8004_AGENT_ID,
        score=args.score,
        tag=args.tag,
        comment=args.comment or "CLI Feedback Submission",
    )
    print("Success:", res)


def main():
    parser = argparse.ArgumentParser(description="QMA ERC-8004 Agent Registry CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Check on-chain status of QMA agent")

    reg_p = subparsers.add_parser("register", help="Register a new agent identity on Arc Testnet")
    reg_p.add_argument("--uri", default="https://genqma.vercel.app/.well-known/agent.json", help="Agent Metadata URI")

    fb_p = subparsers.add_parser("feedback", help="Record reputation feedback")
    fb_p.add_argument("--agent-id", type=int, default=None, help="Agent Token ID")
    fb_p.add_argument("--score", type=int, default=95, help="Score 0-100")
    fb_p.add_argument("--tag", default="accurate_signal", help="Feedback Tag")
    fb_p.add_argument("--comment", default="", help="Optional comment")

    args = parser.parse_args()
    if args.command == "register":
        cmd_register(args)
    elif args.command == "feedback":
        cmd_feedback(args)
    else:
        cmd_status(args)


if __name__ == "__main__":
    main()
