// chrome-mcp-watchdog — Chrome MCP bridge connectivity watchdog
//
// Invoked every 60s by LaunchAgent (StartInterval). Single check-and-maybe-recover
// cycle, then exits. Defensive: all panics caught, never crashes, always exits 0.
//
// Replicates exact behavior of chrome-mcp-watchdog.py.
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/catalyst/daemons/internal/config"
)

var (
	connectCapsule    = config.CatalystRoot() + "/scripts/connect-capsule.sh"
	secretProviderPy  = config.CatalystRoot() + "/global/lib/secret_provider.py"
)

const (
	activeProfileFile = "/tmp/catalyst-chrome-active-profile.json"
	socketIndexFile   = "/tmp/catalyst-chrome-socket-index.json"
	watchdogStateFile = "/tmp/chrome-mcp-watchdog-state.json"
	alertCooldown     = 600 * time.Second
	recoveryTimeout   = 120 * time.Second
)

// ── State ──────────────────────────────────────────────────────────────────────

type watchdogState struct {
	LastCheck         *float64 `json:"last_check"`
	RecoveryAttempts  int      `json:"recovery_attempts"`
	LastRecovery      *float64 `json:"last_recovery"`
	Alerted           bool     `json:"alerted"`
	LastAlertAttempt  *float64 `json:"last_alert_attempt"`
}

func loadState() watchdogState {
	data, err := os.ReadFile(watchdogStateFile)
	if err != nil {
		return watchdogState{}
	}
	var s watchdogState
	if err := json.Unmarshal(data, &s); err != nil {
		return watchdogState{}
	}
	return s
}

func saveState(s watchdogState) {
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		fmt.Printf("[watchdog] WARNING: could not marshal state: %v\n", err)
		return
	}
	// Atomic write
	tmp, err := os.CreateTemp("/tmp", "watchdog-state-*.json.tmp")
	if err != nil {
		fmt.Printf("[watchdog] WARNING: could not create tmp state file: %v\n", err)
		return
	}
	tmpName := tmp.Name()
	_, werr := tmp.Write(data)
	cerr := tmp.Close()
	if werr != nil || cerr != nil {
		os.Remove(tmpName)
		fmt.Printf("[watchdog] WARNING: could not write state: %v %v\n", werr, cerr)
		return
	}
	if err := os.Rename(tmpName, watchdogStateFile); err != nil {
		os.Remove(tmpName)
		fmt.Printf("[watchdog] WARNING: could not replace state file: %v\n", err)
	}
}

func resetState() {
	now := float64(time.Now().UnixMilli()) / 1000.0
	saveState(watchdogState{
		LastCheck:        &now,
		RecoveryAttempts: 0,
	})
	fmt.Println("[watchdog] state reset — system recovered")
}

// ── Connectivity check ──────────────────────────────────────────────────────────

type checkResult struct {
	healthy     bool
	reason      string
	lastCapsule string // empty string if none
}

func checkConnectivity() checkResult {
	// Step 1: Is there an active session at all?
	if _, err := os.Stat(activeProfileFile); os.IsNotExist(err) {
		return checkResult{healthy: true, reason: "no active session (no state file)"}
	}

	profileData, err := os.ReadFile(activeProfileFile)
	if err != nil {
		return checkResult{healthy: true, reason: fmt.Sprintf("could not read active profile file: %v", err)}
	}

	var profile map[string]any
	if err := json.Unmarshal(profileData, &profile); err != nil {
		return checkResult{healthy: true, reason: fmt.Sprintf("could not parse active profile file: %v", err)}
	}

	lastCapsule, _ := profile["capsule"].(string)
	lastProfileDir, _ := profile["profile_dir"].(string)

	// Step 2: Load socket index
	if _, err := os.Stat(socketIndexFile); os.IsNotExist(err) {
		fmt.Println("[watchdog] socket index missing — daemon may be restarting, skipping recovery")
		return checkResult{healthy: true, reason: "socket index missing (advisory)", lastCapsule: lastCapsule}
	}

	indexData, err := os.ReadFile(socketIndexFile)
	if err != nil {
		fmt.Printf("[watchdog] WARNING: could not read socket index: %v\n", err)
		return checkResult{healthy: true, reason: fmt.Sprintf("socket index unreadable: %v", err), lastCapsule: lastCapsule}
	}

	var socketIndex map[string]any
	if err := json.Unmarshal(indexData, &socketIndex); err != nil {
		fmt.Printf("[watchdog] WARNING: could not parse socket index: %v\n", err)
		return checkResult{healthy: true, reason: fmt.Sprintf("socket index parse error: %v", err), lastCapsule: lastCapsule}
	}

	// Step 3: Find sockets matching active capsule
	byCapsule, _ := socketIndex["by_capsule"].(map[string]any)
	byProfile, _ := socketIndex["by_profile"].(map[string]any)
	allSocketsRaw, _ := socketIndex["sockets"].([]any)

	// Build matching entries: capsule first, then profile, then all
	var matchingEntries []map[string]any

	if lastCapsule != "" {
		if entry, ok := byCapsule[lastCapsule]; ok {
			if m, ok := entry.(map[string]any); ok {
				matchingEntries = []map[string]any{m}
			}
		}
	}

	if len(matchingEntries) == 0 && lastProfileDir != "" {
		if entry, ok := byProfile[lastProfileDir]; ok {
			if m, ok := entry.(map[string]any); ok {
				matchingEntries = []map[string]any{m}
			}
		}
	}

	if len(matchingEntries) == 0 {
		for _, raw := range allSocketsRaw {
			if m, ok := raw.(map[string]any); ok {
				matchingEntries = append(matchingEntries, m)
			}
		}
	}

	if len(matchingEntries) == 0 {
		return checkResult{
			healthy:     false,
			reason:      fmt.Sprintf("no socket for capsule '%s'", lastCapsule),
			lastCapsule: lastCapsule,
		}
	}

	// Step 4: Verify at least one socket has a live PID
	for _, entry := range matchingEntries {
		pidRaw := entry["pid"]
		if pidRaw == nil {
			// No PID info — assume alive (conservative)
			return checkResult{
				healthy:     true,
				reason:      fmt.Sprintf("socket present, no PID to check (capsule: %s)", lastCapsule),
				lastCapsule: lastCapsule,
			}
		}

		var pid int
		switch v := pidRaw.(type) {
		case float64:
			pid = int(v)
		case int:
			pid = v
		case string:
			var parseErr error
			pid, parseErr = strconv.Atoi(v)
			if parseErr != nil {
				fmt.Printf("[watchdog] WARNING: invalid PID value '%v'\n", pidRaw)
				continue
			}
		default:
			fmt.Printf("[watchdog] WARNING: unexpected PID type %T\n", pidRaw)
			continue
		}

		err := syscall.Kill(pid, 0)
		if err == nil {
			return checkResult{
				healthy:     true,
				reason:      fmt.Sprintf("socket healthy, PID %d alive (capsule: %s)", pid, lastCapsule),
				lastCapsule: lastCapsule,
			}
		}
		if errors.Is(err, syscall.EPERM) {
			// EPERM — process exists, we just don't own it
			return checkResult{
				healthy:     true,
				reason:      fmt.Sprintf("socket healthy, PID %d alive (capsule: %s)", pid, lastCapsule),
				lastCapsule: lastCapsule,
			}
		}
		// ESRCH: process not found — continue to next entry
	}

	return checkResult{
		healthy:     false,
		reason:      fmt.Sprintf("all native host PIDs dead (capsule: %s)", lastCapsule),
		lastCapsule: lastCapsule,
	}
}

// ── Telegram alert ─────────────────────────────────────────────────────────────

func getKeychain(service string) (string, error) {
	out, err := exec.Command("python3", secretProviderPy, "get", service).Output()
	if err != nil {
		return "", fmt.Errorf("secret_provider get %s: %w", service, err)
	}
	return strings.TrimSpace(string(out)), nil
}

func sendTelegramAlert(message string) bool {
	// Telegram alerting is not bundled in the template (v0.1): the alert
	// is logged to stdout only. Wire your own notifier here if you want
	// push notifications.
	fmt.Printf("[watchdog] ALERT: %s\n", message)
	return false
}

// ── Recovery ───────────────────────────────────────────────────────────────────

func attemptRecovery(capsule string, attemptNumber int) bool {
	if attemptNumber == 2 {
		fmt.Printf("[watchdog] recovery attempt %d: sleeping 10s before surgical reconnect\n", attemptNumber)
		time.Sleep(10 * time.Second)
	}

	var args []string
	var label string
	if attemptNumber == 1 || attemptNumber == 2 {
		args = []string{connectCapsule, capsule}
		label = "surgical"
	} else {
		args = []string{connectCapsule, "--nuclear", capsule}
		label = "nuclear"
	}

	fmt.Printf("[watchdog] recovery attempt %d (%s): bash %s\n", attemptNumber, label, strings.Join(args, " "))

	cmd := exec.Command("bash", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	done := make(chan error, 1)
	if err := cmd.Start(); err != nil {
		fmt.Printf("[watchdog] recovery attempt %d error starting: %v\n", attemptNumber, err)
		return false
	}
	go func() { done <- cmd.Wait() }()

	select {
	case err := <-done:
		if err != nil {
			fmt.Printf("[watchdog] recovery attempt %d exited with error: %v\n", attemptNumber, err)
			return false
		}
		fmt.Printf("[watchdog] recovery attempt %d succeeded\n", attemptNumber)
		return true
	case <-time.After(recoveryTimeout):
		cmd.Process.Kill()
		fmt.Printf("[watchdog] recovery attempt %d timed out after 120s\n", attemptNumber)
		return false
	}
}

// ── Main ───────────────────────────────────────────────────────────────────────

func main() {
	// Absolute last-resort panic recovery (same as the Python try/except around main)
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("[watchdog] FATAL (uncaught): %v\n", r)
			os.Exit(0)
		}
	}()

	fmt.Printf("[watchdog] check started at %s\n", time.Now().Format("2006-01-02 15:04:05"))

	state := loadState()
	now := float64(time.Now().UnixMilli()) / 1000.0
	state.LastCheck = &now

	result := checkConnectivity()
	healthStr := "healthy"
	if !result.healthy {
		healthStr = "UNHEALTHY"
	}
	fmt.Printf("[watchdog] status: %s — %s\n", healthStr, result.reason)

	if result.healthy {
		if state.RecoveryAttempts > 0 {
			fmt.Printf("[watchdog] system recovered after %d attempt(s)\n", state.RecoveryAttempts)
			resetState()
		} else {
			saveState(state)
		}
		os.Exit(0)
	}

	// Unhealthy path
	if result.lastCapsule == "" {
		fmt.Println("[watchdog] no capsule context for recovery — saving state and exiting")
		saveState(state)
		os.Exit(0)
	}

	currentAttempts := state.RecoveryAttempts

	if currentAttempts >= 3 && !state.Alerted {
		// Cooldown check
		if state.LastAlertAttempt != nil {
			elapsed := time.Duration((float64(time.Now().UnixMilli())/1000.0-*state.LastAlertAttempt)*float64(time.Second))
			if elapsed < alertCooldown {
				fmt.Printf("[watchdog] alert cooldown active — last attempt %ds ago, skipping\n", int(elapsed.Seconds()))
				saveState(state)
				os.Exit(0)
			}
		}

		fmt.Println("[watchdog] 3+ attempts failed — sending Telegram alert")
		alertMsg := fmt.Sprintf(
			"Chrome MCP: extension disconnected from bridge.\n"+
				"3 auto-recovery attempts failed (surgical x2, nuclear x1).\n"+
				"Manual fix: connect-capsule %s",
			result.lastCapsule,
		)
		alertNow := float64(time.Now().UnixMilli()) / 1000.0
		state.LastAlertAttempt = &alertNow
		sent := sendTelegramAlert(alertMsg)
		state.Alerted = sent
		saveState(state)
		fmt.Println("[watchdog] alert sent — no further recovery attempts until state is reset")
		os.Exit(0)
	}

	if currentAttempts >= 3 && state.Alerted {
		fmt.Println("[watchdog] already alerted — waiting for manual intervention or state reset")
		saveState(state)
		os.Exit(0)
	}

	// Attempt recovery (1-indexed)
	nextAttempt := currentAttempts + 1
	fmt.Printf("[watchdog] starting recovery attempt %d/3 for capsule '%s'\n", nextAttempt, result.lastCapsule)

	recovered := attemptRecovery(result.lastCapsule, nextAttempt)

	state.RecoveryAttempts = nextAttempt
	recoveryNow := float64(time.Now().UnixMilli()) / 1000.0
	state.LastRecovery = &recoveryNow

	if recovered {
		fmt.Printf("[watchdog] recovery attempt %d succeeded — resetting state\n", nextAttempt)
		resetState()
	} else {
		fmt.Printf("[watchdog] recovery attempt %d failed — state saved\n", nextAttempt)
		saveState(state)
	}

	os.Exit(0)
}
