use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Deserialize)]
pub struct HookRequest {
    pub hook: String,
    pub tool_name: String,
    pub tool_input: Option<HashMap<String, serde_json::Value>>,
    pub cwd: Option<String>,
}

impl HookRequest {
    pub fn command(&self) -> &str {
        self.tool_input
            .as_ref()
            .and_then(|m| m.get("command"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Action {
    Allow,
    Block,
    Advisory,
}

#[derive(Debug, Serialize)]
pub struct HookResponse {
    pub action: Action,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
    pub exit_code: i32,
}

impl HookResponse {
    pub fn allow() -> Self {
        HookResponse {
            action: Action::Allow,
            message: None,
            exit_code: 0,
        }
    }

    pub fn block(message: impl Into<String>) -> Self {
        HookResponse {
            action: Action::Block,
            message: Some(message.into()),
            exit_code: 2,
        }
    }

    pub fn advisory(message: impl Into<String>) -> Self {
        HookResponse {
            action: Action::Advisory,
            message: Some(message.into()),
            exit_code: 0,
        }
    }
}
