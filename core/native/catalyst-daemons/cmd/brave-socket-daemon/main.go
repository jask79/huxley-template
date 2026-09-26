// brave-socket-daemon — Socket monitor for Brave profile <-> MCP connection
//
// Watches /tmp/claude-mcp-browser-bridge-{{USER_LOGIN}}/ for socket creation/deletion.
// On each change, updates /tmp/catalyst-chrome-socket-index.json with the
// full socket -> profile -> capsule mapping.
//
// Uses fsnotify for instant notification; falls back to 5s polling on failure.
// Replicates the exact behavior of brave-socket-daemon.py + brave-profile-mapper.py.
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/fsnotify/fsnotify"
	"github.com/catalyst/daemons/internal/config"
	"github.com/catalyst/daemons/internal/logging"
	"gopkg.in/yaml.v3"
)

var profileMapPath = config.CatalystRoot() + "/global/config/brave-profile-map.yaml"

const (
	socketDir            = "/tmp/claude-mcp-browser-bridge-{{USER_LOGIN}}"
	socketIndexFile      = "/tmp/catalyst-chrome-socket-index.json"
	sessionStateDir      = "/tmp/catalyst-chrome-session-bindings"
	staleSessionTTL      = 3600 * time.Second // 1 hour
	cleanupInterval      = 300 * time.Second  // 5 minutes
	periodicScanInterval = 10 * time.Second
	pollFallbackInterval = 5 * time.Second
)

var log = logging.New("brave-socket-daemon")

// ── Profile map types ──────────────────────────────────────────────────────────

type profileInfo struct {
	DisplayName     string   `yaml:"display_name"`
	Capsules        []string `yaml:"capsules"`
	ParentCapsule   string   `yaml:"parent_capsule"`
	SubcapsulePath  string   `yaml:"subcapsule_path"`
}

type profileMap struct {
	Profiles       map[string]profileInfo `yaml:"profiles"`
	DefaultProfile string                 `yaml:"default_profile"`
}

func loadProfileMap() (*profileMap, error) {
	data, err := os.ReadFile(profileMapPath)
	if err != nil {
		return nil, fmt.Errorf("read profile map: %w", err)
	}
	var pm profileMap
	if err := yaml.Unmarshal(data, &pm); err != nil {
		return nil, fmt.Errorf("parse profile map: %w", err)
	}
	if pm.Profiles == nil {
		pm.Profiles = make(map[string]profileInfo)
	}
	return &pm, nil
}

func profileDirToCapsule(profileDir string, pm *profileMap) string {
	info, ok := pm.Profiles[profileDir]
	if !ok || len(info.Capsules) == 0 {
		return ""
	}
	return info.Capsules[0]
}

func profileDirToDisplayName(profileDir string, pm *profileMap) string {
	info, ok := pm.Profiles[profileDir]
	if !ok || info.DisplayName == "" {
		return profileDir
	}
	return info.DisplayName
}

// ── Process introspection ──────────────────────────────────────────────────────

func extractProfileDir(cmd string) string {
	const prefix = "--profile-directory="
	idx := strings.Index(cmd, prefix)
	if idx < 0 {
		return ""
	}
	rest := cmd[idx+len(prefix):]
	// Find the next flag (starts with " --") or end of string
	endIdx := strings.Index(rest, " --")
	if endIdx < 0 {
		return strings.TrimSpace(rest)
	}
	return strings.TrimSpace(rest[:endIdx])
}

func getPPID(pid int) (int, error) {
	out, err := exec.Command("ps", "-p", strconv.Itoa(pid), "-o", "ppid=").Output()
	if err != nil {
		return 0, err
	}
	ppidStr := strings.TrimSpace(string(out))
	ppid, err := strconv.Atoi(ppidStr)
	if err != nil {
		return 0, fmt.Errorf("invalid ppid %q", ppidStr)
	}
	return ppid, nil
}

func getProcessCommand(pid int) (string, error) {
	out, err := exec.Command("ps", "-p", strconv.Itoa(pid), "-o", "command=").Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// pidToProfileDir traces: native host PID -> PPID (Brave) -> --profile-directory value
func pidToProfileDir(pid int) string {
	ppid, err := getPPID(pid)
	if err != nil {
		return ""
	}
	cmd, err := getProcessCommand(ppid)
	if err != nil || !strings.Contains(cmd, "Brave Browser") {
		return ""
	}
	return extractProfileDir(cmd)
}

func strPtr(s string) *string { return &s }

// ── PID alive check ────────────────────────────────────────────────────────────

func isPidAlive(pid int) bool {
	err := syscall.Kill(pid, 0)
	if err == nil {
		return true
	}
	if errors.Is(err, syscall.EPERM) {
		return true // exists but we don't own it
	}
	return false
}

// ── Socket struct ──────────────────────────────────────────────────────────────

type socketEntry struct {
	PID         int     `json:"pid"`
	SocketPath  string  `json:"socket_path"`
	ProfileDir  *string `json:"profile_dir"`
	DisplayName *string `json:"display_name"`
	Capsule     *string `json:"capsule"`
	Alive       bool    `json:"alive"`
}

// ── Socket enumeration ─────────────────────────────────────────────────────────

func listActiveSockets() ([]socketEntry, error) {
	entries, err := os.ReadDir(socketDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}

	pm, pmErr := loadProfileMap()
	if pmErr != nil {
		log.Warnf("Could not load profile map: %v", pmErr)
		pm = &profileMap{Profiles: make(map[string]profileInfo)}
	}

	// Sort by name for deterministic output
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].Name() < entries[j].Name()
	})

	var results []socketEntry
	for _, e := range entries {
		name := e.Name()
		if !strings.HasSuffix(name, ".sock") {
			continue
		}
		pidStr := strings.TrimSuffix(name, ".sock")
		pid, err := strconv.Atoi(pidStr)
		if err != nil {
			continue
		}

		alive := isPidAlive(pid)
		var profileDir, displayName, capsule *string

		if alive {
			pd := pidToProfileDir(pid)
			if pd != "" {
				profileDir = strPtr(pd)
				displayName = strPtr(profileDirToDisplayName(pd, pm))
				capsule = strPtr(profileDirToCapsule(pd, pm))
			}
		}

		results = append(results, socketEntry{
			PID:         pid,
			SocketPath:  filepath.Join(socketDir, name),
			ProfileDir:  profileDir,
			DisplayName: displayName,
			Capsule:     capsule,
			Alive:       alive,
		})
	}
	return results, nil
}

// ── Index writer ───────────────────────────────────────────────────────────────

type socketIndex struct {
	UpdatedAt float64                  `json:"updated_at"`
	Sockets   []socketEntry            `json:"sockets"`
	ByProfile map[string]socketEntry   `json:"by_profile"`
	ByCapsule map[string]socketEntry   `json:"by_capsule"`
}

func writeSocketIndex(sockets []socketEntry) error {
	// by_profile: prefer highest PID on duplicate profiles
	byProfile := make(map[string]socketEntry)
	for _, s := range sockets {
		if !s.Alive || s.ProfileDir == nil {
			continue
		}
		existing, ok := byProfile[*s.ProfileDir]
		if !ok || s.PID > existing.PID {
			byProfile[*s.ProfileDir] = s
		}
	}

	// by_capsule: prefer highest PID on duplicate capsules
	byCapsule := make(map[string]socketEntry)
	for _, s := range sockets {
		if !s.Alive || s.Capsule == nil || *s.Capsule == "" {
			continue
		}
		existing, ok := byCapsule[*s.Capsule]
		if !ok || s.PID > existing.PID {
			byCapsule[*s.Capsule] = s
		}
	}

	idx := socketIndex{
		UpdatedAt: float64(time.Now().UnixMilli()) / 1000.0,
		Sockets:   sockets,
		ByProfile: byProfile,
		ByCapsule: byCapsule,
	}

	// Ensure sockets is [] not null in JSON
	if idx.Sockets == nil {
		idx.Sockets = []socketEntry{}
	}

	data, err := json.MarshalIndent(idx, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal index: %w", err)
	}

	// Atomic write: write to .tmp, then rename
	dir := filepath.Dir(socketIndexFile)
	tmp, err := os.CreateTemp(dir, "socket-index-*.tmp")
	if err != nil {
		return fmt.Errorf("create tmp file: %w", err)
	}
	tmpName := tmp.Name()

	_, writeErr := tmp.Write(data)
	closeErr := tmp.Close()
	if writeErr != nil || closeErr != nil {
		os.Remove(tmpName)
		if writeErr != nil {
			return fmt.Errorf("write tmp: %w", writeErr)
		}
		return fmt.Errorf("close tmp: %w", closeErr)
	}

	if err := os.Rename(tmpName, socketIndexFile); err != nil {
		os.Remove(tmpName)
		return fmt.Errorf("rename to index: %w", err)
	}
	return nil
}

// ── Stale session cleanup ──────────────────────────────────────────────────────

func cleanStaleSessionBindings() {
	entries, err := os.ReadDir(sessionStateDir)
	if err != nil {
		return
	}
	now := time.Now()
	for _, e := range entries {
		if !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		if now.Sub(info.ModTime()) > staleSessionTTL {
			path := filepath.Join(sessionStateDir, e.Name())
			if err := os.Remove(path); err == nil {
				log.Infof("Cleaned stale session binding: %s", e.Name())
			}
		}
	}
}

// ── Scan and update ────────────────────────────────────────────────────────────

func scanAndUpdate() (int, []socketEntry) {
	sockets, err := listActiveSockets()
	if err != nil {
		log.Errorf("Failed to list sockets: %v", err)
		return 0, nil
	}
	if sockets == nil {
		sockets = []socketEntry{}
	}
	if err := writeSocketIndex(sockets); err != nil {
		log.Errorf("Failed to write socket index: %v", err)
	}
	alive := 0
	for _, s := range sockets {
		if s.Alive {
			alive++
		}
	}
	return alive, sockets
}

// ── Main ───────────────────────────────────────────────────────────────────────

func main() {
	log.Infof("Starting brave-socket-daemon")
	log.Infof("Watching: %s", socketDir)
	log.Infof("Index: %s", socketIndexFile)

	// Ensure watch dir exists
	if err := os.MkdirAll(socketDir, 0755); err != nil {
		log.Errorf("Cannot create socket dir: %v", err)
		os.Exit(1)
	}

	// Signal handling
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)

	// Try fsnotify first
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		log.Warnf("fsnotify unavailable (%v) — falling back to polling", err)
		runPolling(sigCh)
		return
	}

	if err := watcher.Add(socketDir); err != nil {
		watcher.Close()
		log.Warnf("fsnotify add failed (%v) — falling back to polling", err)
		runPolling(sigCh)
		return
	}

	log.Infof("Using fsnotify for socket monitoring")
	runFsnotify(watcher, sigCh)
}

func runFsnotify(watcher *fsnotify.Watcher, sigCh chan os.Signal) {
	defer watcher.Close()

	// Initial scan
	count, _ := scanAndUpdate()
	log.Infof("Initial scan: %d active socket(s)", count)

	var (
		mu           sync.Mutex
		lastScan     time.Time
		debounce     = 500 * time.Millisecond
		lastCleanup  = time.Now()
		lastPeriodic = time.Now()
	)

	// Debounced trigger channel
	triggerCh := make(chan string, 32)

	// Watcher event goroutine
	go func() {
		for {
			select {
			case event, ok := <-watcher.Events:
				if !ok {
					return
				}
				if strings.HasSuffix(event.Name, ".sock") {
					triggerCh <- event.Name
				}
			case err, ok := <-watcher.Errors:
				if !ok {
					return
				}
				log.Warnf("fsnotify error: %v", err)
			}
		}
	}()

	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-sigCh:
			log.Infof("Signal received — shutting down")
			return

		case path := <-triggerCh:
			mu.Lock()
			now := time.Now()
			if now.Sub(lastScan) >= debounce {
				lastScan = now
				mu.Unlock()
				count, _ := scanAndUpdate()
				log.Infof("Socket change detected (%s) — index updated (%d active socket(s))", path, count)
			} else {
				mu.Unlock()
			}
			// Drain remaining triggers
		drain:
			for {
				select {
				case <-triggerCh:
					continue
				default:
					break drain
				}
			}

		case now := <-ticker.C:
			// Periodic scan every 10s to catch process deaths
			if now.Sub(lastPeriodic) >= periodicScanInterval {
				count, _ := scanAndUpdate()
				log.Debugf("Periodic scan: %d active socket(s)", count)
				lastPeriodic = now
			}
			// Periodic stale session cleanup every 5m
			if now.Sub(lastCleanup) >= cleanupInterval {
				cleanStaleSessionBindings()
				lastCleanup = now
			}
		}
	}
}

func runPolling(sigCh chan os.Signal) {
	log.Infof("Using polling fallback (%v interval)", pollFallbackInterval)

	// Initial scan
	count, sockets := scanAndUpdate()
	log.Infof("Initial scan: %d active socket(s)", count)

	prevPIDs := make(map[int]bool)
	for _, s := range sockets {
		if s.Alive {
			prevPIDs[s.PID] = true
		}
	}

	lastCleanup := time.Now()
	ticker := time.NewTicker(pollFallbackInterval)
	defer ticker.Stop()

	for {
		select {
		case <-sigCh:
			log.Infof("Signal received — shutting down")
			return

		case now := <-ticker.C:
			count, sockets := scanAndUpdate()

			currentPIDs := make(map[int]bool)
			for _, s := range sockets {
				if s.Alive {
					currentPIDs[s.PID] = true
				}
			}

			// Detect adds and removals
			for pid := range currentPIDs {
				if !prevPIDs[pid] {
					for _, s := range sockets {
						if s.PID == pid {
							pd := ""
							if s.ProfileDir != nil {
								pd = *s.ProfileDir
							}
							dn := ""
							if s.DisplayName != nil {
								dn = *s.DisplayName
							}
							log.Infof("Socket added: PID %d -> %s / %s", pid, pd, dn)
						}
					}
				}
			}
			for pid := range prevPIDs {
				if !currentPIDs[pid] {
					log.Infof("Socket removed: PID %d", pid)
				}
			}
			_ = count

			prevPIDs = currentPIDs

			if now.Sub(lastCleanup) >= cleanupInterval {
				cleanStaleSessionBindings()
				lastCleanup = now
			}
		}
	}
}
