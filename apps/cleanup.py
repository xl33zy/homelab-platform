import os
import sys

import psycopg


def main() -> int:
    days = int(os.environ.get("NOTES_RETENTION_DAYS", "30"))
    if days < 1:
        print("NOTES_RETENTION_DAYS должно быть не меньше 1", file=sys.stderr)
        return 2
    with psycopg.connect(connect_timeout=10) as conn:
        cur = conn.execute(
            "DELETE FROM notes WHERE created_at < now() - make_interval(days => %s)",
            (days,),
        )
        deleted = cur.rowcount
    print(f"deleted={deleted} retention_days={days}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
