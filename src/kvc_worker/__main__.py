"""No-op background worker entrypoint for the bootstrap stage."""


def main() -> int:
    """Start the worker shell.

    Polling, scheduling, and external API calls are intentionally outside the
    bootstrap stage.
    """

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
