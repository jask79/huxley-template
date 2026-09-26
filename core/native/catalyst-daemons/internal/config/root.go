// Package config provides shared configuration helpers for Catalyst daemons.
package config

import "os"

const defaultRoot = "{{CATALYST_ROOT}}"

// CatalystRoot returns the Catalyst root directory.
// Reads CATALYST_ROOT env var first; falls back to the default hardcoded path.
func CatalystRoot() string {
	if root := os.Getenv("CATALYST_ROOT"); root != "" {
		return root
	}
	return defaultRoot
}
