#!/usr/bin/env python3
"""Purge all LiveKit rooms, agent dispatches, and active participant sessions.

This script loads environment variables from a ``.env`` file, then:
1) lists every LiveKit room,
2) deletes all agent dispatches in each room,
3) removes all participants from each room,
4) deletes the room.

Expected env vars (from .env or shell):
- LIVEKIT_API_URL (preferred) or LIVEKIT_URL
- LIVEKIT_API_KEY
- LIVEKIT_API_SECRET
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path


def _load_env_file(env_file: Path) -> None:
    """Load KEY=VALUE lines into os.environ.

    Behavior:
    - Existing shell env vars are preserved (highest precedence).
    - Within the file, later duplicate keys override earlier ones.
    """
    if not env_file.exists():
        return

    parsed: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        parsed[key] = value

    for key, value in parsed.items():
        os.environ.setdefault(key, value)


def _resolve_livekit_http_url() -> str:
    """Resolve HTTP(S) LiveKit URL from LIVEKIT_API_URL or LIVEKIT_URL."""
    url = os.environ.get("LIVEKIT_API_URL") or os.environ.get("LIVEKIT_URL")
    if not url:
        raise RuntimeError("Missing LIVEKIT_API_URL (or LIVEKIT_URL) in environment/.env")

    if url.startswith("ws://"):
        return "http://" + url.removeprefix("ws://")
    if url.startswith("wss://"):
        return "https://" + url.removeprefix("wss://")
    return url


async def _purge(*, dry_run: bool, yes: bool) -> int:
    from livekit import api as lkapi

    api_url = _resolve_livekit_http_url()
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")

    if not api_key or not api_secret:
        raise RuntimeError("Missing LIVEKIT_API_KEY or LIVEKIT_API_SECRET in environment/.env")

    lk = lkapi.LiveKitAPI(url=api_url, api_key=api_key, api_secret=api_secret)
    try:
        rooms_resp = await lk.room.list_rooms(lkapi.ListRoomsRequest())
        rooms = list(rooms_resp.rooms)

        if not rooms:
            print("No LiveKit rooms found.")
            return 0

        print(f"Found {len(rooms)} room(s):")
        for room in rooms:
            print(f"- {room.name}")

        if dry_run:
            print("Dry-run mode: nothing was deleted.")
            return 0

        if not yes:
            answer = (
                input("Delete ALL listed rooms and participant sessions? [y/N]: ").strip().lower()
            )
            if answer not in {"y", "yes"}:
                print("Aborted.")
                return 0

        deleted_dispatches = 0
        removed_participants = 0
        deleted_rooms = 0

        for room in rooms:
            dispatches = await lk.agent_dispatch.list_dispatch(room.name)
            for dispatch in dispatches:
                await lk.agent_dispatch.delete_dispatch(dispatch.id, room.name)
                deleted_dispatches += 1
                print(
                    f"Deleted agent dispatch '{dispatch.id}' (agent: '{dispatch.agent_name}')"
                    f" from room '{room.name}'"
                )

            participants_resp = await lk.room.list_participants(
                lkapi.ListParticipantsRequest(room=room.name)
            )
            participants = list(participants_resp.participants)

            for participant in participants:
                await lk.room.remove_participant(
                    lkapi.RoomParticipantIdentity(room=room.name, identity=participant.identity)
                )
                removed_participants += 1
                print(f"Removed participant '{participant.identity}' from room '{room.name}'")

            await lk.room.delete_room(lkapi.DeleteRoomRequest(room=room.name))
            deleted_rooms += 1
            print(f"Deleted room '{room.name}'")

        print(
            "Done. "
            f"Deleted {deleted_dispatches} agent dispatch(es), "
            f"removed {removed_participants} participant session(s), "
            f"deleted {deleted_rooms} room(s)."
        )
        return 0
    finally:
        await lk.aclose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete all LiveKit rooms, agent dispatches, and active participant sessions."
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List rooms but do not delete anything.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _load_env_file(Path(args.env_file))

    try:
        return asyncio.run(_purge(dry_run=args.dry_run, yes=args.yes))
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
