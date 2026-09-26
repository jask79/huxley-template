use crate::protocol::{HookRequest, HookResponse};
use regex::Regex;
use std::sync::OnceLock;

static FIND_GENERIC_RE: OnceLock<Regex> = OnceLock::new();
static DUMP_KEYCHAIN_RE: OnceLock<Regex> = OnceLock::new();

fn find_generic_re() -> &'static Regex {
    FIND_GENERIC_RE
        .get_or_init(|| Regex::new(r"\bsecurity\s+find-generic-password\b").unwrap())
}

fn dump_keychain_re() -> &'static Regex {
    DUMP_KEYCHAIN_RE
        .get_or_init(|| Regex::new(r"\bsecurity\s+(dump-keychain|list-keychains)\b").unwrap())
}

pub fn run(req: &HookRequest) -> HookResponse {
    // Advisory-only hook: Bash tool only
    if req.tool_name != "Bash" {
        return HookResponse::allow();
    }

    let command = req.command();
    let mut messages: Vec<&str> = Vec::new();

    // Detect raw security find-generic-password usage
    if find_generic_re().is_match(command) {
        messages.push(
            "REMINDER: You're using raw `security find-generic-password`. \
            If this returns empty or fails, do NOT conclude the credential \
            doesn't exist. Instead run:\n\
            \x20 python3 global/lib/secret_provider.py list\n\
            This lists every stored Keychain service so you can find the right name.",
        );
    }

    // Detect dump-keychain or list-keychains
    if dump_keychain_re().is_match(command) {
        messages.push(
            "REMINDER: Use `python3 global/lib/secret_provider.py list` \
            instead of raw keychain dumps.",
        );
    }

    if messages.is_empty() {
        HookResponse::allow()
    } else {
        HookResponse::advisory(messages.join("\n\n"))
    }
}
