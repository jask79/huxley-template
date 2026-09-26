"""Account info and auth status commands."""

from ..cache import FileCache
from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN,
    RESET, YELLOW,
)
from ..formatters import (
    format_table, human_number, json_output, print_error,
    print_footer, print_header,
)
from ..models import CommandResult


def cmd_account(args, client) -> int:
    """Show connected Instagram Business Account info."""
    cache = _get_cache(args)
    filters = {"command": "account"}

    if cache:
        cached = cache.get("account", filters)
        if cached:
            return _output_cached_account(cached, args)

    try:
        info = client.get_account_info()
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    data = info.to_dict()

    if cache:
        cache.set("account", filters, {"data": data})

    if args.json:
        json_output({"success": True, "data": data, "cached": False})
    else:
        print_header("account")
        lines = [
            f"  {BOLD}@{info.username}{RESET}",
            f"  {DIM}{info.name}{RESET}",
        ]
        if info.biography:
            lines.append(f"  {DIM}{info.biography}{RESET}")
        lines.append("")
        lines.append(
            f"  {CYAN}Followers:{RESET} {human_number(info.followers_count)}   "
            f"{CYAN}Following:{RESET} {human_number(info.following_count)}   "
            f"{CYAN}Posts:{RESET} {human_number(info.media_count)}"
        )
        if info.website:
            lines.append(f"  {CYAN}Website:{RESET} {info.website}")
        if info.profile_picture_url:
            lines.append(f"  {CYAN}Avatar:{RESET} {DIM}{info.profile_picture_url}{RESET}")
        print("\n".join(lines))
        print_footer(1)

    return EXIT_SUCCESS


def cmd_auth_status(args, client) -> int:
    """Verify token validity and show scopes."""
    try:
        token = client.debug_token()
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "auth_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    data = token.to_dict()

    if args.json:
        json_output({"success": True, "data": data})
    else:
        print_header("auth-status")
        valid_str = f"{GREEN}Valid{RESET}" if token.is_valid else f"\033[91mInvalid{RESET}"
        expires_str = "Never" if token.expires_at == 0 else str(token.expires_at)

        lines = [
            f"  {CYAN}Valid:{RESET}      {valid_str}",
            f"  {CYAN}Type:{RESET}       {token.type}",
            f"  {CYAN}App ID:{RESET}     {token.app_id}",
            f"  {CYAN}User ID:{RESET}    {token.user_id}",
            f"  {CYAN}Expires:{RESET}    {expires_str}",
        ]

        if token.scopes:
            lines.append(f"\n  {BOLD}Scopes ({len(token.scopes)}):{RESET}")
            for scope in sorted(token.scopes):
                lines.append(f"    {DIM}-{RESET} {scope}")

        print("\n".join(lines))
        print_footer(1)

    return EXIT_SUCCESS


def cmd_mentions(args, client) -> int:
    """Show media where account is @mentioned."""
    limit = getattr(args, "limit", 25)
    cache = _get_cache(args)
    filters = {"command": "mentions", "limit": limit}

    if cache:
        cached = cache.get("mentions", filters)
        if cached:
            return _output_cached_mentions(cached, args)

    try:
        mentions = client.get_mentions(limit=limit)
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    data = [m.to_dict() for m in mentions]

    if cache:
        cache.set("mentions", filters, {"data": data, "count": len(data)})

    if args.json:
        json_output({
            "success": True, "data": data,
            "count": len(data), "cached": False,
        })
    else:
        print_header("mentions")
        if not mentions:
            print("  (no mentions found)")
        else:
            from ..formatters import _truncate, ts_to_str
            headers = ["#", "User", "Type", "Date", "Caption", "Link"]
            rows = []
            for i, m in enumerate(mentions):
                rows.append([
                    str(i + 1),
                    m.username or "unknown",
                    m.media_type,
                    ts_to_str(m.timestamp),
                    _truncate(m.caption, 40),
                    _truncate(m.permalink, 45),
                ])
            print(format_table(headers, rows))
        print_footer(len(mentions))

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_cache(args) -> FileCache | None:
    if getattr(args, "no_cache", False):
        return None
    return FileCache(ttl=args.cache_ttl)


def _output_cached_account(cached: dict, args) -> int:
    data = cached.get("data", {})
    if args.json:
        json_output({"success": True, "data": data, "cached": True})
    else:
        print_header("account")
        username = data.get("username", "")
        name = data.get("name", "")
        bio = data.get("biography", "")
        lines = [f"  {BOLD}@{username}{RESET}", f"  {DIM}{name}{RESET}"]
        if bio:
            lines.append(f"  {DIM}{bio}{RESET}")
        lines.append("")
        lines.append(
            f"  {CYAN}Followers:{RESET} {human_number(data.get('followers_count', 0))}   "
            f"{CYAN}Following:{RESET} {human_number(data.get('following_count', 0))}   "
            f"{CYAN}Posts:{RESET} {human_number(data.get('media_count', 0))}"
        )
        print("\n".join(lines))
        print_footer(1, cached=True)
    return EXIT_SUCCESS


def _output_cached_mentions(cached: dict, args) -> int:
    data = cached.get("data", [])
    count = cached.get("count", len(data))
    if args.json:
        json_output({"success": True, "data": data, "count": count, "cached": True})
    else:
        print_header("mentions")
        if not data:
            print("  (no mentions found)")
        else:
            from ..formatters import _truncate, ts_to_str
            headers = ["#", "User", "Type", "Date", "Caption", "Link"]
            rows = []
            for i, m in enumerate(data):
                rows.append([
                    str(i + 1),
                    m.get("username", "unknown"),
                    m.get("media_type", ""),
                    ts_to_str(m.get("timestamp", "")),
                    _truncate(m.get("caption", ""), 40),
                    _truncate(m.get("permalink", ""), 45),
                ])
            print(format_table(headers, rows))
        print_footer(count, cached=True)
    return EXIT_SUCCESS
