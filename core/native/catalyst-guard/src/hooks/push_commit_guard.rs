use crate::protocol::{HookRequest, HookResponse};
use regex::Regex;
use std::process::Command;
use std::sync::OnceLock;
use std::time::Duration;
use tokio::task;

const BLOCK_MSG: &str =
    "BLOCKED: Working tree has uncommitted changes. \
    Convention in this repo: 'push' means commit + push (edit this guard to change it). \
    Stage and commit first, then push.";

// Non-destructive flags that shouldn't be blocked even with dirty tree
static EXEMPT_FLAGS: OnceLock<Regex> = OnceLock::new();

// Compound commands where a commit precedes the push.
// TOCTOU note: we check dirty state before the compound runs, so
// `git commit && git push` would be blocked even though the commit
// would clean the tree. We accept this trade-off and exempt the pattern.
static COMMIT_THEN_PUSH: OnceLock<Regex> = OnceLock::new();

static GIT_PUSH_RE: OnceLock<Regex> = OnceLock::new();

fn exempt_flags() -> &'static Regex {
    EXEMPT_FLAGS
        .get_or_init(|| Regex::new(r"\bgit\s+push\s+--(?:help|dry-run|list)\b").unwrap())
}

fn commit_then_push() -> &'static Regex {
    COMMIT_THEN_PUSH.get_or_init(|| {
        Regex::new(r"\bgit\s+commit\b.*(?:&&|\|\|).*\bgit\s+push\b").unwrap()
    })
}

fn git_push_re() -> &'static Regex {
    GIT_PUSH_RE.get_or_init(|| Regex::new(r"\bgit\s+push\b").unwrap())
}

/// Returns true if the command is a real git push that should be guarded.
fn is_git_push_command(command: &str) -> bool {
    if !git_push_re().is_match(command) {
        return false;
    }
    if exempt_flags().is_match(command) {
        return false;
    }
    if commit_then_push().is_match(command) {
        return false;
    }
    true
}

/// Returns true if the working tree has uncommitted changes (excluding untracked files).
/// Runs `git status --porcelain` in the provided cwd.
/// If we can't check, we allow the push (don't block on tool errors).
fn has_uncommitted_changes(cwd: Option<&str>) -> bool {
    let mut cmd = Command::new("git");
    cmd.args(["status", "--porcelain"]);
    if let Some(dir) = cwd {
        cmd.current_dir(dir);
    }

    let result = match cmd.output() {
        Ok(o) => o,
        Err(_) => return false,
    };

    let stdout = match std::str::from_utf8(&result.stdout) {
        Ok(s) => s,
        Err(_) => return false,
    };

    // Exclude untracked files (??) since those don't affect push safety
    for line in stdout.lines() {
        if !line.starts_with("?? ") {
            return true;
        }
    }

    false
}

pub async fn run(req: &HookRequest) -> HookResponse {
    if req.tool_name != "Bash" {
        return HookResponse::allow();
    }

    let command = req.command();

    if is_git_push_command(command) {
        let cwd = req.cwd.clone();
        let blocking = task::spawn_blocking(move || has_uncommitted_changes(cwd.as_deref()));
        let has_changes = match tokio::time::timeout(Duration::from_secs(5), blocking).await {
            Ok(Ok(result)) => result,
            Ok(Err(_)) => false, // JoinError — treat as no changes
            Err(_) => false,     // Timed out — don't block on tool errors
        };
        if has_changes {
            return HookResponse::block(BLOCK_MSG);
        }
    }

    HookResponse::allow()
}
