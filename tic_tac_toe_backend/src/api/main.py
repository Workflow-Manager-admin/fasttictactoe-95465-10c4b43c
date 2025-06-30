from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid


# Tic Tac Toe FastAPI Backend
app = FastAPI(
    title="Tic Tac Toe Game API",
    description=(
        "API Backend for Tic Tac Toe Game. Supports starting a new game, "
        "making moves, and checking game status."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Game", "description": "Tic Tac Toe game management operations"}
    ],
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Game Logic & Models ---


class Move(BaseModel):
    """A move request for Tic Tac Toe."""
    row: int = Field(..., description="Row index, 0-based")
    col: int = Field(..., description="Column index, 0-based")
    player: str = Field(
        ..., description='Player making the move: either "X" or "O"'
    )


class GameState(BaseModel):
    """Full game state, as returned by the backend."""
    game_id: str = Field(..., description="Unique ID of the game")
    board: List[List[Optional[str]]] = Field(
        ..., description="3x3 game board as a 2D array"
    )
    current_player: str = Field(
        ..., description='Player whose turn it is: "X" or "O"'
    )
    status: str = Field(
        ..., description='Status: "waiting", "ongoing", "win_X", "win_O", "draw"'
    )
    winner: Optional[str] = Field(
        None, description='Winner: "X", "O", or None if no winner yet'
    )


class NewGameResponse(BaseModel):
    game_id: str
    state: GameState


class StatusResponse(BaseModel):
    game_id: str
    state: GameState


# In-memory store for games: {game_id: game_state_dict}
games: Dict[str, dict] = {}


def initial_board():
    return [
        [None, None, None],
        [None, None, None],
        [None, None, None]
    ]


def check_winner(board):
    # Check rows, columns, diagonals for 3-match
    for i in range(3):
        if (
            board[i][0] is not None
            and all(board[i][j] == board[i][0] for j in range(3))
        ):
            return board[i][0]
        if (
            board[0][i] is not None
            and all(board[j][i] == board[0][i] for j in range(3))
        ):
            return board[0][i]
    # Diagonals
    if (
        board[0][0] is not None
        and all(board[d][d] == board[0][0] for d in range(3))
    ):
        return board[0][0]
    if (
        board[0][2] is not None
        and all(board[d][2 - d] == board[0][2] for d in range(3))
    ):
        return board[0][2]
    return None


def board_full(board):
    return all(cell is not None for row in board for cell in row)


# PUBLIC_INTERFACE
@app.get("/", tags=["Game"])
def health_check():
    """Basic health check endpoint."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.post(
    "/game/new",
    response_model=NewGameResponse,
    tags=["Game"],
    summary="Start a new game",
    description="Creates a new Tic Tac Toe game and returns the initial board and game ID.",
)
def start_new_game():
    """
    Starts a new Tic Tac Toe game.

    Returns:
        game_id: Unique identifier for this game session.
        state: Current game state (empty board, X starts).
    """
    game_id = str(uuid.uuid4())
    state = {
        "game_id": game_id,
        "board": initial_board(),
        "current_player": "X",
        "status": "ongoing",
        "winner": None,
    }
    games[game_id] = state
    return {"game_id": game_id, "state": GameState(**state)}


# PUBLIC_INTERFACE
@app.post(
    "/game/{game_id}/move",
    response_model=GameState,
    tags=["Game"],
    summary="Make a move",
    description=(
        "Make a move on the game board for the given game, returning the new "
        "state. Accepts row, col and player."
    ),
)
def make_move(game_id: str, move: Move = Body(...)):
    """
    Register a player's move for this game.

    Args:
        game_id: ID of the game to play.
        move: Move object specifying row, col, and player ("X"/"O").

    Returns current GameState or error if invalid.
    """
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    state = games[game_id]
    board = state["board"]

    # Validate move
    if state["status"] not in ["ongoing"]:
        raise HTTPException(status_code=400, detail="Game is not ongoing.")
    if move.player != state["current_player"]:
        raise HTTPException(status_code=400, detail="It is not this player's turn.")
    if not (0 <= move.row < 3) or not (0 <= move.col < 3):
        raise HTTPException(status_code=400, detail="Move out of bounds.")
    if board[move.row][move.col] is not None:
        raise HTTPException(status_code=400, detail="Cell is already occupied.")

    # Apply move
    board[move.row][move.col] = move.player

    # Check if there's a winner or draw
    winner = check_winner(board)
    if winner:
        state["status"] = "win_" + winner
        state["winner"] = winner
    elif board_full(board):
        state["status"] = "draw"
        state["winner"] = None
    else:
        state["current_player"] = "O" if move.player == "X" else "X"

    return GameState(**state)


# PUBLIC_INTERFACE
@app.get(
    "/game/{game_id}/status",
    response_model=GameState,
    tags=["Game"],
    summary="Check game status",
    description="Returns the current state of the specified game.",
)
def get_game_status(game_id: str):
    """
    Get the current status of a Tic Tac Toe game.

    Args:
        game_id: ID of the game.

    Returns the current GameState.
    """
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    return GameState(**games[game_id])
