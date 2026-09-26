#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'fileutils'
require 'securerandom'

module IOSTesting
  # Manages persistent state for iOS testing sessions
  class StateManager
    attr_reader :session, :state_dir

    def initialize(project_path:, scheme:, simulator:, max_iterations: 10)
      @state_dir = File.join(Dir.pwd, '.ios-testing-state')
      FileUtils.mkdir_p(@state_dir)
      FileUtils.mkdir_p(diagnostics_dir)

      @session_file = File.join(@state_dir, 'current_session.json')
      @history_file = File.join(@state_dir, 'iteration_history.json')
      @known_issues_file = File.join(@state_dir, 'known_issues.json')

      @session = load_or_create_session(project_path, scheme, simulator, max_iterations)
    end

    def load_or_create_session(project_path, scheme, simulator, max_iterations)
      if File.exist?(@session_file)
        load_session
      else
        create_session(project_path, scheme, simulator, max_iterations)
      end
    end

    def create_session(project_path, scheme, simulator, max_iterations)
      {
        session_id: SecureRandom.uuid,
        project_path: project_path,
        scheme: scheme,
        simulator: simulator,
        start_time: Time.now.utc.iso8601,
        current_iteration: 1,
        max_iterations: max_iterations,
        status: 'in_progress',
        iterations: []
      }
    end

    def load_session
      JSON.parse(File.read(@session_file), symbolize_names: true)
    rescue JSON::ParserError => e
      warn "Failed to parse session file: #{e.message}"
      nil
    end

    def save_session
      File.write(@session_file, JSON.pretty_generate(@session))
    end

    def add_iteration(iteration_data)
      @session[:iterations] << iteration_data
      save_session

      # Also append to history file
      history = load_history
      history << iteration_data
      File.write(@history_file, JSON.pretty_generate(history))
    end

    def load_history
      return [] unless File.exist?(@history_file)
      JSON.parse(File.read(@history_file), symbolize_names: true)
    rescue JSON::ParserError
      []
    end

    def complete_session(success:, total_duration_ms:, issues_fixed:)
      @session[:status] = success ? 'completed' : 'failed'
      @session[:final_outcome] = {
        success: success,
        total_iterations: @session[:current_iteration] - 1,
        total_duration_ms: total_duration_ms,
        issues_fixed: issues_fixed
      }
      @session[:end_time] = Time.now.utc.iso8601
      save_session
    end

    def increment_iteration
      @session[:current_iteration] += 1
      save_session
    end

    def diagnostics_dir
      File.join(@state_dir, 'diagnostics')
    end

    def create_diagnostic_bundle(issue)
      timestamp = Time.now.strftime('%Y-%m-%d_%H-%M-%S')
      issue_type = issue[:type]
      bundle_id = "#{timestamp}_#{issue_type}_#{SecureRandom.hex(3)}"
      bundle_dir = File.join(diagnostics_dir, bundle_id)

      FileUtils.mkdir_p(bundle_dir)

      # Write issue details
      File.write(File.join(bundle_dir, 'issue.json'), JSON.pretty_generate(issue))

      bundle_dir
    end

    def known_issues
      return [] unless File.exist?(@known_issues_file)
      JSON.parse(File.read(@known_issues_file), symbolize_names: true)
    rescue JSON::ParserError
      []
    end

    def add_known_issue(pattern:, fix_strategy:, success_rate:)
      issues = known_issues
      issues << {
        pattern: pattern,
        fix_strategy: fix_strategy,
        success_rate: success_rate,
        added_at: Time.now.utc.iso8601
      }
      File.write(@known_issues_file, JSON.pretty_generate(issues))
    end

    def add_validation(validation_results)
      @session[:validations] ||= []
      @session[:validations] << validation_results
      save_session
    end

    def clear_session
      File.delete(@session_file) if File.exist?(@session_file)
    end
  end
end
