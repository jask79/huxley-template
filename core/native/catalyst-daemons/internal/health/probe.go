// Package health provides TCP port probing for service health checks.
package health

import (
	"net"
	"strconv"
	"time"
)

// TCPProbe attempts a TCP connection to host:port within timeout.
// Returns true if the connection succeeds (port is accepting).
func TCPProbe(host string, port int, timeout time.Duration) bool {
	addr := net.JoinHostPort(host, strconv.Itoa(port))
	conn, err := net.DialTimeout("tcp", addr, timeout)
	if err != nil {
		return false
	}
	conn.Close()
	return true
}
