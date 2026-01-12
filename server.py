            elif msg_type == "cover":
                if not room or not player_name:
                    continue

                game = get_game(room.code)
                if not game.started:
                    continue

                # must be your turn
                if player_name != current_turn_name(game):
                    continue

                # must have rolled this turn
                if not game.rolled_this_turn:
                    continue

                # parse the number to cover
                try:
                    n = int(msg.get("n"))
                except Exception:
                    continue

                if n < 1 or n > 6:
                    continue

                # must have a board
                if player_name not in game.boards:
                    continue

                # can't cover twice
                if game.boards[player_name].get(n, False):
                    continue

                # must have matching die available
                if n not in game.dice:
                    continue

                # consume ONE die and cover the tile
                game.dice.remove(n)
                game.boards[player_name][n] = True

                await broadcast_game(room, game)
