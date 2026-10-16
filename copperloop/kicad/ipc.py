"""Live session with the open KiCad PCB editor over the IPC API (kipy).

KiCad 10: the PCB editor window must be open with the board loaded. The IPC
API cannot run DRC or plot; use copperloop.kicad.cli for those.
"""
from __future__ import annotations
from dataclasses import dataclass

HELP = ("Could not reach an open board over the KiCad IPC API.\n"
        "  1. KiCad 10 must be running with the IPC API enabled (Preferences > Plugins).\n"
        "  2. The PCB editor window must be open with the board loaded (the project\n"
        "     manager or schematic alone does not answer board requests).\n"
        "  3. No modal dialog may be open in KiCad.")

@dataclass
class Session:
    kicad: object
    board: object

    @property
    def name(self) -> str:
        return self.board.name

def connect() -> Session:
    from kipy import KiCad
    from kipy.errors import ApiError
    try:
        k = KiCad()
        k.ping()
    except Exception as e:  # socket missing, token mismatch, not running
        raise ConnectionError(f"{HELP}\n  underlying: {type(e).__name__}: {e}") from e
    try:
        b = k.get_board()
    except ApiError as e:
        raise ConnectionError(f"{HELP}\n  KiCad {k.get_version()} answered: {e}") from e
    return Session(k, b)

def summary(s: Session) -> dict:
    b = s.board
    return {
        "board": b.name,
        "kicad": str(s.kicad.get_version()),
        "copper_layers": b.get_copper_layer_count(),
        "nets": len(b.get_nets()),
        "footprints": len(b.get_footprints()),
        "tracks": len(b.get_tracks()),
        "vias": len(b.get_vias()),
        "zones": len(b.get_zones()),
    }
