            elif msg_type == "cover":
                if not room or not player_name:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Not in a room."
                    }))
                    continue

                game = get_game(room.code)
                if not game.started:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Game not started."
                    }))
                    continue

                # must be your turn
                if player_name != current_turn_name(game):
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Not your turn."
                    }))
                    continue

                # must have rolled this turn
                if not game.rolled_this_turn:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "You must roll before covering."
                    }))
                    continue

                # parse the number to cover
                try:
                    n = int(msg.get("n"))
                except Exception:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid tile number."
                    }))
                    continue

                if n < 1 or n > 6:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Tile must be between 1 and 6."
                    }))
                    continue

                # must have a board
                if player_name not in game.boards:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "Board not initialized."
                    }))
                    continue

                # can't cover twice
                if game.boards[player_name].get(n, False):
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": "That tile is already covered."
                    }))
                    continue

                # must have matching die available
                if n not in game.dice:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": f"You do not have a {n} die."
                    }))
                    continue

                # consume ONE die and cover the tile
                game.dice.remove(n)
                game.boards[player_name][n] = True

                await broadcast_game(room, game)
