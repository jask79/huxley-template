#!/usr/bin/env ruby
# frozen_string_literal: true

module IOSTesting
  # Circuit breaker to prevent infinite loops on repeated errors
  class CircuitBreaker
    class CircuitBreakerError < StandardError; end

    def initialize(max_same_errors: 3, metrics_tracker: nil)
      @max_same_errors = max_same_errors
      @error_history = []
      @metrics_tracker = metrics_tracker
    end

    def check(error_message)
      normalized_error = normalize_error(error_message)
      @error_history << normalized_error

      # Check for same error repeating
      recent_errors = @error_history.last(@max_same_errors)

      if recent_errors.length == @max_same_errors && recent_errors.uniq.length == 1
        @metrics_tracker&.circuit_breaker_triggered(
          error: normalized_error,
          count: @max_same_errors
        )

        raise CircuitBreakerError,
              "Circuit breaker triggered: Same error occurred #{@max_same_errors} times: #{normalized_error}"
      end
    end

    def reset
      @error_history.clear
    end

    def error_count
      @error_history.length
    end

    def recent_errors(count = 5)
      @error_history.last(count)
    end

    private

    def normalize_error(error)
      # Normalize error messages by removing file paths, line numbers, etc.
      # to detect truly recurring issues
      error.to_s
        .gsub(%r{/[^ ]+/}, '[PATH]/')  # Replace paths
        .gsub(/:\d+:/, ':[LINE]:')     # Replace line numbers
        .gsub(/\b0x[0-9a-f]+\b/i, '0x[HEX]') # Replace hex addresses
        .strip
    end
  end
end
