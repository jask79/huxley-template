#!/usr/bin/env ruby
# frozen_string_literal: true

module IOSTesting
  # Detects issues from build logs, runtime behavior, and test results
  class IssueDetector
    ISSUE_PATTERNS = {
      build_error: [
        /error:.*Cannot find.*in scope/i,
        /error:.*Use of unresolved identifier/i,
        /error:.*Expected.*before/i,
        /error:.*Missing.*import/i,
        /\*\* BUILD FAILED \*\*/
      ],
      crash: [
        /Fatal error:/,
        /EXC_BAD_ACCESS/,
        /SIGABRT/,
        /Terminating app due to/
      ],
      ui_error: [
        /UITest.*failed/,
        /Unable to find.*element/,
        /View not found/
      ],
      console_error: [
        /\[error\]/i,
        /Exception:/,
        /Failed to/
      ]
    }.freeze

    def initialize(metrics_tracker: nil)
      @metrics_tracker = metrics_tracker
    end

    def analyze_build_log(log_content)
      issues = []

      ISSUE_PATTERNS.each do |type, patterns|
        patterns.each do |pattern|
          log_content.scan(pattern) do
            match_line = $~.to_s
            issue = extract_issue_details(type, match_line, log_content)
            issues << issue if issue
          end
        end
      end

      issues.uniq { |i| [i[:type], i[:message]] }
    end

    def extract_issue_details(type, match_line, full_log)
      # Extract file, line number, and surrounding context
      file_match = match_line.match(%r{([^/\s]+\.swift):(\d+):})

      issue = {
        type: type,
        severity: determine_severity(type),
        message: sanitize_message(match_line),
        timestamp: Time.now.utc.iso8601
      }

      if file_match
        issue[:file] = file_match[1]
        issue[:line] = file_match[2].to_i
        issue[:context] = extract_context(full_log, file_match[1], file_match[2].to_i)
      end

      @metrics_tracker&.issue_detected(
        type: issue[:type],
        severity: issue[:severity],
        message: issue[:message]
      )

      issue
    end

    def determine_severity(type)
      case type
      when :build_error, :crash
        'critical'
      when :ui_error
        'high'
      when :console_error
        'medium'
      else
        'low'
      end
    end

    def sanitize_message(message)
      # Remove ANSI colors and clean up message
      message.gsub(/\e\[[0-9;]*m/, '').strip
    end

    def extract_context(log, file, line)
      # Extract surrounding lines from build log for context
      lines = log.split("\n")
      file_pattern = /#{Regexp.escape(file)}:#{line}:/

      index = lines.index { |l| l.match?(file_pattern) }
      return nil unless index

      start_idx = [0, index - 2].max
      end_idx = [lines.length - 1, index + 2].min

      lines[start_idx..end_idx].join("\n")
    end

    def analyze_ui_tree(ui_tree, expected_elements)
      missing_elements = expected_elements.reject do |element|
        ui_tree.include?(element)
      end

      missing_elements.map do |element|
        {
          type: :ui_error,
          severity: 'high',
          message: "Missing UI element: #{element}",
          expected: element,
          timestamp: Time.now.utc.iso8601
        }
      end
    end

    def analyze_test_results(test_output)
      issues = []

      # Parse XCTest output
      if test_output.match?(/Test Case.*failed/)
        test_output.scan(/Test Case '(.*)' failed.*/) do |test_name|
          issues << {
            type: :test_failure,
            severity: 'high',
            message: "Test failed: #{test_name.first}",
            test_name: test_name.first,
            timestamp: Time.now.utc.iso8601
          }
        end
      end

      issues
    end

    def categorize_issues(issues)
      {
        critical: issues.select { |i| i[:severity] == 'critical' },
        high: issues.select { |i| i[:severity] == 'high' },
        medium: issues.select { |i| i[:severity] == 'medium' },
        low: issues.select { |i| i[:severity] == 'low' }
      }
    end
  end
end
