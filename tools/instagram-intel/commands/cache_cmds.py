"""Cache management commands."""

from ..cache import FileCache
from ..config import EXIT_SUCCESS, GREEN, RESET
from ..formatters import format_table, json_output, print_header


def cmd_cache_clear(args) -> int:
    """Clear all cached results."""
    cache = FileCache(ttl=args.cache_ttl)
    count = cache.clear()
    if args.json:
        json_output({"cleared": count})
    else:
        print(f"\n{GREEN}Cleared {count} cache entries.{RESET}\n")
    return EXIT_SUCCESS


def cmd_cache_stats(args) -> int:
    """Show cache statistics."""
    cache = FileCache(ttl=args.cache_ttl)
    stats = cache.stats()
    if args.json:
        json_output(stats)
    else:
        print_header("cache-stats")
        rows = [[k, str(v)] for k, v in stats.items()]
        print(format_table(["Key", "Value"], rows))
        print()
    return EXIT_SUCCESS
