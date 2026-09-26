// service-health-push — Catalyst Service Health Monitor
//
// Reads port-registry.yaml, checks each port via TCP connect,
// pushes catalyst_service_up{service, port, type, category} to Pushgateway.
//
// Invoked every 30s by LaunchAgent (StartInterval). Runs once, then exits.
// Replicates exact behavior of push-service-status.py.
package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/catalyst/daemons/internal/config"
	"github.com/catalyst/daemons/internal/health"
	"github.com/catalyst/daemons/internal/logging"
	"gopkg.in/yaml.v3"
)

var portRegistry = config.CatalystRoot() + "/global/config/port-registry.yaml"

const (
	pushgatewayURL = "http://localhost:9092"
	jobName        = "catalyst_service_health"
	tcpTimeout     = 3 * time.Second // 3s per port check (matches task requirements)
	httpTimeout    = 5 * time.Second
)

var log = logging.New("service-health-push")

// ── Service registry ───────────────────────────────────────────────────────────

type service struct {
	name        string
	port        int
	category    string
	description string
	svcType     string // "container" or "native"
}

// loadServices walks every YAML category -> service entry, returns flat list.
// Skips entries without a numeric port and the "oauth" category (ephemeral).
func loadServices(registryPath string) ([]service, error) {
	data, err := os.ReadFile(registryPath)
	if err != nil {
		return nil, fmt.Errorf("read port registry: %w", err)
	}

	// Parse as map[category -> map[name -> attrs]]
	var raw map[string]any
	if err := yaml.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parse port registry: %w", err)
	}

	// Keep category order deterministic
	categories := make([]string, 0, len(raw))
	for k := range raw {
		categories = append(categories, k)
	}
	sort.Strings(categories)

	var services []service
	for _, category := range categories {
		if category == "oauth" {
			continue
		}
		entries, ok := raw[category].(map[string]any)
		if !ok {
			continue
		}

		// Sort service names within category
		svcNames := make([]string, 0, len(entries))
		for k := range entries {
			svcNames = append(svcNames, k)
		}
		sort.Strings(svcNames)

		for _, svcName := range svcNames {
			svcData, ok := entries[svcName].(map[string]any)
			if !ok {
				continue
			}
			portRaw := svcData["port"]
			if portRaw == nil {
				continue
			}
			// YAML integers decode as int
			port, ok := portRaw.(int)
			if !ok {
				continue
			}
			if port == 0 {
				continue
			}

			desc, _ := svcData["description"].(string)
			svcType := "native"
			if category == "docker" {
				svcType = "container"
			}

			services = append(services, service{
				name:        svcName,
				port:        port,
				category:    category,
				description: desc,
				svcType:     svcType,
			})
		}
	}
	return services, nil
}

// ── Prometheus text format push ────────────────────────────────────────────────

type metric struct {
	labels map[string]string
	value  int
}

func sanitize(s string) string {
	s = strings.ReplaceAll(s, `"`, "")
	s = strings.ReplaceAll(s, "\n", "")
	return s
}

func sanitizeDesc(s string) string {
	if len(s) > 60 {
		s = s[:60]
	}
	s = strings.ReplaceAll(s, `"`, "'")
	s = strings.ReplaceAll(s, "\n", " ")
	return s
}

func buildPayload(metrics []metric) string {
	var b strings.Builder
	b.WriteString("# HELP catalyst_service_up 1 if service port is accepting TCP connections, 0 otherwise\n")
	b.WriteString("# TYPE catalyst_service_up gauge\n")
	for _, m := range metrics {
		// Sort label keys for deterministic output
		keys := make([]string, 0, len(m.labels))
		for k := range m.labels {
			keys = append(keys, k)
		}
		sort.Strings(keys)

		var parts []string
		for _, k := range keys {
			parts = append(parts, fmt.Sprintf(`%s="%s"`, k, m.labels[k]))
		}
		b.WriteString(fmt.Sprintf("catalyst_service_up{%s} %d\n", strings.Join(parts, ","), m.value))
	}
	return b.String()
}

func pushMetrics(metrics []metric) bool {
	payload := buildPayload(metrics)
	url := fmt.Sprintf("%s/metrics/job/%s", pushgatewayURL, jobName)

	req, err := http.NewRequest(http.MethodPut, url, bytes.NewBufferString(payload))
	if err != nil {
		log.Errorf("Pushgateway request build error: %v", err)
		return false
	}
	req.Header.Set("Content-Type", "text/plain")

	client := &http.Client{Timeout: httpTimeout}
	resp, err := client.Do(req)
	if err != nil {
		log.Errorf("Pushgateway unreachable: %v", err)
		return false
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)

	if resp.StatusCode == 200 || resp.StatusCode == 202 {
		return true
	}
	log.Warnf("Pushgateway returned HTTP %d", resp.StatusCode)
	return false
}

// ── Main ───────────────────────────────────────────────────────────────────────

func main() {
	log.Infof("=== Catalyst service health check — %s ===", time.Now().Format(time.RFC3339))

	services, err := loadServices(portRegistry)
	if err != nil {
		log.Errorf("Failed to load services: %v", err)
		os.Exit(1)
	}
	log.Infof("Loaded %d services from registry", len(services))

	var metrics []metric
	upCount, downCount := 0, 0

	for _, svc := range services {
		isUp := health.TCPProbe("localhost", svc.port, tcpTimeout)
		status := 0
		if isUp {
			status = 1
			upCount++
		} else {
			downCount++
		}

		symbol := "DOWN"
		if isUp {
			symbol = "UP  "
		}
		log.Infof("  [%s] %s (port %d, %s)", symbol, svc.name, svc.port, svc.category)

		metrics = append(metrics, metric{
			labels: map[string]string{
				"service":     sanitize(svc.name),
				"port":        fmt.Sprintf("%d", svc.port),
				"type":        svc.svcType,
				"category":    sanitize(svc.category),
				"description": sanitizeDesc(svc.description),
			},
			value: status,
		})
	}

	log.Infof("Summary: %d UP / %d DOWN / %d total", upCount, downCount, len(services))

	if pushMetrics(metrics) {
		log.Infof("Metrics pushed to Pushgateway successfully")
	} else {
		log.Warnf("Failed to push metrics — Pushgateway may be down (non-fatal)")
		// Exit 0 to prevent launchd restart thrashing when Pushgateway is down
	}
}
