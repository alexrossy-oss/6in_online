from __future__ import annotations

import json
import random
import secrets
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Serve the webpage
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


# ----------------------------
# In-memory room + game state
# ----------------------------
@dataclass
class Room:
    code: str
    players: Set[str] = field(default_factory=set)
    sockets: Set[WebSocket] = field(default_factory=set)


@dataclass
class GameState:
    started: bool = False
    turn_order: List[str] = field(default_factory=list)
    current_turn_index: int = 0

    # dice state
    dice: List[int] = field(default_factory=list)        # current dice values
    rolled_this_turn: bool = False                       # prevents re-rolling


rooms: Dict[str, Room] = {}
games: Dict[str, GameState] = {}


def get_or_create_room(code: str) -> Room:
    code = code.strip().upper()
    if not code:
        code = secrets.token_hex(2).upper()
    if code not in rooms:
        rooms[code] = Room(code=code)
    return rooms[code]


def get_game(room_code: str) -> GameState:
    if room_code not in games:
        games[room_code] = GameState()
    return games[room_code]


def current_turn_name(game: GameState) -> Optional[str]:
    if game.started and game.turn_order:
        return game.turn_order[game.current_turn_index]
    return None


async def broadcast_room(room: Room):
    payload = {
        "type": "room_state",
        "room": room.code,
        "players": sorted(room.players),
        "count": len(room.players),
    }
    msg = json.dumps(payload)
    dead: Set[WebSocket] = set()
    for ws in room.sockets:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    room.sockets -= dead


async def broadcast_game(room: Room, game: GameState):
    payload = {
        "type": "game_state",
        "started": game.started,
        "turn_order": game.turn_order,
        "current_turn": current_turn_name(game),
        "dice": game.dice,
        "rolled_this_turn": game.rolled_this_turn,
    }
    msg = json.dumps(payload)
    dead: Set[WebSocket] = set()
    for ws in room.sockets:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    room.sockets -= dead


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    room: Optional[Room] = None
    player_name: Optional[str] = None

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "join":
                code = (msg.get("room") or "").strip().upper()
                player_name = (msg.get("name") or "").strip()

                if not player_name:
                    await ws.send_text(json.dumps({"type": "error", "message": "Name is required."}))
                    continue

                room = get_or_create_room(code)
                room.sockets.add(ws)
                room.players.add(player_name)

                await broadcast_room(room)
                await broadcast_game(room, get_game(room.code))

            elif msg_type == "start_game":
                if not room:
                    continue

                game = get_game(room.code)
                if not game.started:
                    game.started = True
                    game.turn_order = sorted(room.players)
                    secrets.SystemRandom().shuffle(game.turn_order)
                    game.current_turn_index = 0

                    # reset dice for new game
                    game.dice = []
                    game.rolled_this_turn = False

                await broadcast_game(room, game)

            elif msg_type == "roll":
                if not room or not player_name:
                    continue

                game = get_game(room.code)
                if not game.started:
                    continue

                # only current player can roll
                if player_name != current_turn_name(game):
                    continue

                # only once per turn
                if game.rolled_this_turn:
                    continue

                # Default dice: 4 (we'll add extra-die rules later)
                game.dice = [random.randint(1, 6) for _ in range(4)]
                game.rolled_this_turn = True
                await broadcast_game(room, game)

            elif msg_type == "end_turn":
                if not room or not player_name:
                    continue

                game = get_game(room.code)
                if game.started and player_name == current_turn_name(game):
                    game.current_turn_index = (game.current_turn_index + 1) % len(game.turn_order)

                    # reset dice state for next player
                    game.dice = []
                    game.rolled_this_turn = False

                    await broadcast_game(room, game)

            elif msg_type == "leave":
                if room and player_name:
                    room.players.discard(player_name)
                    room.sockets.discard(ws)
                    await broadcast_room(room)

            else:
                await ws.send_text(json.dumps({"type": "error", "message": f"Unknown message type: {msg_type}"}))

    except WebSocketDisconnect:
        pass
    finally:
        if room and player_name:
            room.players.discard(player_name)
            room.sockets.discard(ws)
            await broadcast_room(room)
