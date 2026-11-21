"""CLI helper: cetak machine_id mesin saat ini.

Jalankan dengan:

    python -m corebot.machine_id

Output dipakai admin saat menerbitkan lisensi yang machine-bound.
"""

from __future__ import annotations

from .license.check import get_machine_id


def main() -> int:
    print(get_machine_id())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
