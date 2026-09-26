use std::os::unix::fs::PermissionsExt;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::UnixListener;
use tokio::signal::unix::{signal, SignalKind};
use tokio::task::JoinSet;

const MAX_REQUEST_BYTES: u64 = 1_048_576; // 1MB

mod hooks;
mod protocol;

use protocol::{HookRequest, HookResponse};

const SOCKET_PATH: &str = "/tmp/catalyst-guard.sock";

fn log(msg: &str) {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    eprintln!("[catalyst-guard {ts}] {msg}");
}

async fn dispatch(req: &HookRequest) -> HookResponse {
    match req.hook.as_str() {
        "keychain-redirect" => hooks::keychain_redirect::run(req),
        "push-commit-guard" => hooks::push_commit_guard::run(req).await,
        unknown => {
            log(&format!("unknown hook: {unknown}"));
            HookResponse::allow()
        }
    }
}

async fn handle_connection(stream: tokio::net::UnixStream) {
    let (reader, mut writer) = tokio::io::split(stream);

    // Read entire request (until EOF), capped at MAX_REQUEST_BYTES
    let mut buf = Vec::new();
    if let Err(e) = reader.take(MAX_REQUEST_BYTES).read_to_end(&mut buf).await {
        log(&format!("read error: {e}"));
        return;
    }

    let response = match serde_json::from_slice::<HookRequest>(&buf) {
        Ok(req) => {
            log(&format!(
                "hook={} tool={} cmd={}",
                req.hook,
                req.tool_name,
                &req.command().chars().take(80).collect::<String>()
            ));
            dispatch(&req).await
        }
        Err(e) => {
            log(&format!("parse error: {e}"));
            HookResponse::allow()
        }
    };

    let json = match serde_json::to_vec(&response) {
        Ok(j) => j,
        Err(e) => {
            log(&format!("serialize error: {e}"));
            return;
        }
    };

    if let Err(e) = writer.write_all(&json).await {
        log(&format!("write error: {e}"));
    }
}

#[tokio::main]
async fn main() {
    log("starting");

    // Clean up stale socket
    let _ = std::fs::remove_file(SOCKET_PATH);

    let listener = match UnixListener::bind(SOCKET_PATH) {
        Ok(l) => l,
        Err(e) => {
            log(&format!("failed to bind {SOCKET_PATH}: {e}"));
            std::process::exit(1);
        }
    };

    // Restrict socket to owner-only access (rw-------)
    std::fs::set_permissions(SOCKET_PATH, std::fs::Permissions::from_mode(0o600))
        .unwrap_or_else(|e| log(&format!("failed to set socket permissions: {e}")));

    log(&format!("listening on {SOCKET_PATH}"));

    // Set up SIGTERM handler for graceful shutdown
    let mut sigterm = match signal(SignalKind::terminate()) {
        Ok(s) => s,
        Err(e) => {
            log(&format!("failed to install SIGTERM handler: {e}"));
            std::process::exit(1);
        }
    };

    let mut tasks: JoinSet<()> = JoinSet::new();

    loop {
        tokio::select! {
            result = listener.accept() => {
                match result {
                    Ok((stream, _addr)) => {
                        tasks.spawn(handle_connection(stream));
                    }
                    Err(e) => {
                        log(&format!("accept error: {e}"));
                    }
                }
            }
            _ = sigterm.recv() => {
                log("received SIGTERM, draining connections");
                break;
            }
        }
    }

    // Drain in-flight connections with a 10s deadline
    let drain = tokio::time::timeout(
        std::time::Duration::from_secs(10),
        async { while tasks.join_next().await.is_some() {} },
    );
    let _ = drain.await;

    let _ = std::fs::remove_file(SOCKET_PATH);
    log("shutdown complete");
}
