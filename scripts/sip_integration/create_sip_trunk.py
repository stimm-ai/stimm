#!/usr/bin/env python3
"""
Create SIP trunk configuration for LiveKit SIP server.

This script creates a SIP trunk entry in Redis that the LiveKit SIP server
uses to route incoming calls. The trunk is configured with a single phone number
(+1234567) and allows connections from any IP (for testing).

Usage:
    python create_sip_trunk.py
"""

import json
import sys
import uuid

import redis


def main():
    # Connect to Redis
    try:
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        print("Make sure Redis is running (docker compose up -d redis)")
        sys.exit(1)

    # Define Trunk Configuration
    trunk_id = "ST_" + str(uuid.uuid4())[:12]
    trunk_config = {
        "sip_trunk_id": trunk_id,
        "name": "Local Trunk",
        "numbers": ["+1234567"],  # The number that SIP clients dial
        "allowed_addresses": ["0.0.0.0/0"],  # Allow from anywhere for testing
        "metadata": {},
    }

    # Key for Inbound Trunks (based on maintenance.sh)
    TRUNK_KEY = "sip_inbound_trunk"

    # Store in Redis
    # Redis HSET: Key, Field (TrunkID), Value (JSON Config)
    r.hset(TRUNK_KEY, trunk_id, json.dumps(trunk_config))

    print(f"Created SIP Trunk with ID: {trunk_id}")
    print(f"Configuration: {json.dumps(trunk_config, indent=2)}")

    # Verify
    print("\nCurrent Trunks in Redis:")
    trunks = r.hgetall(TRUNK_KEY)
    for tid, cfg in trunks.items():
        print(f"- {tid}: {cfg}")


if __name__ == "__main__":
    main()
