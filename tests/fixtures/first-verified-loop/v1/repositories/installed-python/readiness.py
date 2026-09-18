def ready(checks: dict[str, bool]) -> bool:
    return all(checks.values())
