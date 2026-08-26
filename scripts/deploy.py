#!/usr/bin/env python3
"""Deploy / configure TruthMarket with genlayer-py.

    pip install genlayer-py
    export GENLAYER_PRIVATE_KEY=0x...

    python scripts/deploy.py deploy  --config examples/claims.json
    python scripts/deploy.py submit  --address 0xCONTRACT --claim "..."
    python scripts/deploy.py verify  --address 0xCONTRACT --claim-id 1 \
        --source https://www.who.int/... --source https://apnews.com/... \
        --source https://www.reuters.com/...
    python scripts/deploy.py waive   --address 0xCONTRACT --claim-id 1
    python scripts/deploy.py finalize --address 0xCONTRACT --claim-id 1
    python scripts/deploy.py read    --address 0xCONTRACT --claim-id 1

Note: verify/appeal/waive must be sent by the claim author, the arbiter or the
owner; finalize is open to anyone once the claim's challenge window has closed.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "truth_market.py"


def client(rpc: str):
    try:
        from genlayer_py import create_account, create_client
        from genlayer_py.chains import localnet, studionet, testnet_asimov
    except ImportError:  # pragma: no cover
        sys.exit("genlayer-py is required: pip install genlayer-py")

    chains = {"localnet": localnet, "studionet": studionet, "testnet": testnet_asimov}
    if rpc not in chains:
        sys.exit(f"unknown network {rpc}; choose one of {', '.join(chains)}")

    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    account = create_account(account_private_key=key) if key else create_account()
    return create_client(chain=chains[rpc], account=account), account


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["deploy", "submit", "verify", "appeal", "waive", "finalize", "read", "config"])
    parser.add_argument("--network", default="studionet", help="localnet | studionet | testnet")
    parser.add_argument("--config", default=str(ROOT / "examples" / "claims.json"))
    parser.add_argument("--address")
    parser.add_argument("--claim")
    parser.add_argument("--claim-id", type=int)
    parser.add_argument("--source", action="append", default=[])
    args = parser.parse_args()

    gl_client, account = client(args.network)
    code = CONTRACT.read_text()

    if args.command == "deploy":
        cfg = json.loads(pathlib.Path(args.config).read_text())["deployment"]
        tx_hash = gl_client.deploy_contract(
            code=code,
            args=[
                cfg.get("arbiter", account.address),
                cfg["allowed_domains"],
                cfg["min_sources"],
                cfg["max_rounds"],
            ],
        )
        receipt = gl_client.wait_for_transaction_receipt(transaction_hash=tx_hash)
        print(json.dumps({"tx": str(tx_hash), "receipt": str(receipt)}, indent=2))
        return 0

    if not args.address:
        sys.exit("--address is required for this command")

    if args.command == "config":
        print(gl_client.read_contract(address=args.address, function_name="config", args=[]))
        return 0

    if args.command == "read":
        for method, params in (
            ("get_claim", [args.claim_id]),
            ("get_sources", [args.claim_id]),
            ("get_rulings", [args.claim_id]),
        ):
            print(method, "->", gl_client.read_contract(address=args.address, function_name=method, args=params))
        return 0

    calls = {
        "submit": ("submit_claim", [args.claim]),
        "verify": ("verify", [args.claim_id, args.source]),
        "appeal": ("appeal", [args.claim_id, args.source]),
        "waive": ("waive_challenge", [args.claim_id]),
        "finalize": ("finalize", [args.claim_id]),
    }
    function_name, call_args = calls[args.command]
    tx_hash = gl_client.write_contract(address=args.address, function_name=function_name, args=call_args)
    print(json.dumps({"tx": str(tx_hash)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
