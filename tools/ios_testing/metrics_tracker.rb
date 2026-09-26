#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'fileutils'

module IOSTesting
  # Tracks metrics and observability signals for iOS testing
  class MetricsTracker
    def initialize(state_dir:)
      @metrics_file = File.join(state_dir, 'metrics.jsonl')
      ensure_metrics_file
    end

    def ensure_metrics_file
      FileUtils.touch(@metrics_file) unless File.exist?(@metrics_file)
    end

    def log_event(event, **metadata)
      entry = {
        timestamp: Time.now.utc.iso8601,
        event: event
      }.merge(metadata)

      File.open(@metrics_file, 'a') do |f|
        f.puts(JSON.generate(entry))
      end
    end

    def session_start(project:, scheme:, simulator:)
      log_event('session_start',
                project: project,
                scheme: scheme,
                simulator: simulator)
    end

    def session_complete(iterations:, success:, duration_ms:)
      log_event('session_complete',
                iterations: iterations,
                success: success,
                duration_ms: duration_ms)
    end

    def iteration_start(iteration:)
      log_event('iteration_start', iteration: iteration)
    end

    def iteration_complete(iteration:, success:, duration_ms:)
      log_event('iteration_complete',
                iteration: iteration,
                success: success,
                duration_ms: duration_ms)
    end

    def build_start
      log_event('build_start')
    end

    def build_success(duration_ms:)
      log_event('build_success', duration_ms: duration_ms)
    end

    def build_failed(error:, duration_ms:)
      log_event('build_failed',
                error: error,
                duration_ms: duration_ms)
    end

    def issue_detected(type:, severity:, message:)
      log_event('issue_detected',
                type: type,
                severity: severity,
                message: message)
    end

    def fix_applied(approach:, files_count:)
      log_event('fix_applied',
                approach: approach,
                files_count: files_count)
    end

    def fix_failed(reason:)
      log_event('fix_failed', reason: reason)
    end

    def circuit_breaker_triggered(error:, count:)
      log_event('circuit_breaker_triggered',
                error: error,
                count: count)
    end

    def test_start(test_count:)
      log_event('test_start', test_count: test_count)
    end

    def test_complete(passed:, failed:, duration_ms:)
      log_event('test_complete',
                passed: passed,
                failed: failed,
                duration_ms: duration_ms)
    end

    # Read and parse metrics for analysis
    def get_metrics(since: nil)
      return [] unless File.exist?(@metrics_file)

      metrics = []
      File.readlines(@metrics_file).each do |line|
        entry = JSON.parse(line, symbolize_names: true)
        if since.nil? || Time.parse(entry[:timestamp]) >= since
          metrics << entry
        end
      end
      metrics
    rescue JSON::ParserError => e
      warn "Failed to parse metrics: #{e.message}"
      []
    end

    # Generate summary report
    def summary_report
      metrics = get_metrics

      {
        total_sessions: metrics.count { |m| m[:event] == 'session_start' },
        successful_sessions: metrics.count { |m| m[:event] == 'session_complete' && m[:success] },
        failed_sessions: metrics.count { |m| m[:event] == 'session_complete' && !m[:success] },
        total_iterations: metrics.count { |m| m[:event] == 'iteration_start' },
        total_builds: metrics.count { |m| m[:event] == 'build_start' },
        successful_builds: metrics.count { |m| m[:event] == 'build_success' },
        failed_builds: metrics.count { |m| m[:event] == 'build_failed' },
        issues_detected: metrics.count { |m| m[:event] == 'issue_detected' },
        fixes_applied: metrics.count { |m| m[:event] == 'fix_applied' },
        circuit_breakers: metrics.count { |m| m[:event] == 'circuit_breaker_triggered' }
      }
    end
  end
end
