#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'fileutils'
require 'shellwords'
require_relative 'ios_testing/state_manager'
require_relative 'ios_testing/metrics_tracker'
require_relative 'ios_testing/circuit_breaker'
require_relative 'ios_testing/issue_detector'
require_relative 'ios_testing/mobile_dev_delegator'
require_relative 'ios_testing/design_validator'

# Production-grade iOS testing agentic loop
# Coordinates with xcodebuildmcp MCP tools and Mobile Dev agent
class IOSTestingLoop
  VERSION = '1.0.0'

  def initialize(project_path:, scheme:, simulator: 'iPhone 16', max_iterations: 10, mode: 'debug')
    @project_path = File.expand_path(project_path)
    @scheme = scheme
    @simulator = simulator
    @max_iterations = max_iterations
    @mode = mode

    validate_project!

    # Initialize core components
    @state = IOSTesting::StateManager.new(
      project_path: @project_path,
      scheme: @scheme,
      simulator: @simulator,
      max_iterations: @max_iterations
    )

    @metrics = IOSTesting::MetricsTracker.new(state_dir: @state.state_dir)
    @circuit_breaker = IOSTesting::CircuitBreaker.new(
      max_same_errors: 3,
      metrics_tracker: @metrics
    )
    @issue_detector = IOSTesting::IssueDetector.new(metrics_tracker: @metrics)
    @delegator = IOSTesting::MobileDevDelegator.new(
      project_path: @project_path,
      scheme: @scheme
    )
    @design_validator = IOSTesting::DesignValidator.new(
      state_dir: @state.state_dir,
      project_path: @project_path
    )

    @start_time = Time.now
  end

  def run
    log_banner
    @metrics.session_start(
      project: File.basename(@project_path),
      scheme: @scheme,
      simulator: @simulator
    )

    case @mode
    when 'quick'
      run_quick_verification
    when 'debug'
      run_debug_loop
    when 'test'
      run_test_suite
    else
      error_exit("Unknown mode: #{@mode}")
    end

    finalize_session
  rescue IOSTesting::CircuitBreaker::CircuitBreakerError => e
    handle_circuit_breaker(e)
  rescue StandardError => e
    handle_error(e)
  ensure
    cleanup
  end

  private

  def run_quick_verification
    log_info "🔍 Running quick verification..."

    iteration_start = Time.now
    @metrics.iteration_start(iteration: 1)

    # Build and run
    build_result = build_project
    unless build_result[:success]
      log_error "Build failed: #{build_result[:error]}"
      return finish_iteration(1, false, iteration_start)
    end

    # Launch in simulator
    launch_result = launch_in_simulator
    unless launch_result[:success]
      log_error "Launch failed: #{launch_result[:error]}"
      return finish_iteration(1, false, iteration_start)
    end

    # Visual verification
    screenshot_path = capture_screenshot
    ui_tree = capture_ui_tree

    # VALIDATE design (auto-run 5 tools)
    if screenshot_path
      validation_results = @design_validator.validate(screenshot_path, iteration: 1)
      @state.add_validation(validation_results) if validation_results
    end

    # Check for issues
    issues = detect_runtime_issues(build_result[:log], ui_tree)

    if issues.empty?
      log_success "✅ Quick verification passed!"
      finish_iteration(1, true, iteration_start)
      @state.complete_session(
        success: true,
        total_duration_ms: elapsed_ms(@start_time),
        issues_fixed: 0
      )
    else
      log_warning "❌ Issues detected:"
      issues.each { |issue| log_warning "  - #{issue[:message]}" }
      finish_iteration(1, false, iteration_start)
      @state.complete_session(
        success: false,
        total_duration_ms: elapsed_ms(@start_time),
        issues_fixed: 0
      )
    end
  end

  def run_debug_loop
    log_info "🔄 Starting debug loop (max #{@max_iterations} iterations)..."

    iteration = @state.session[:current_iteration]

    while iteration <= @max_iterations
      log_section "Iteration #{iteration}/#{@max_iterations}"
      iteration_start = Time.now
      @metrics.iteration_start(iteration: iteration)

      # BUILD phase
      build_result = build_project
      issues = []

      if build_result[:success]
        # RUN phase
        launch_result = launch_in_simulator
        if launch_result[:success]
          # MONITOR phase
          sleep 2 # Wait for app to stabilize

          screenshot = capture_screenshot
          ui_tree = capture_ui_tree

          # VALIDATE design (auto-run 5 tools)
          if screenshot
            validation_results = @design_validator.validate(screenshot, iteration: iteration)
            @state.add_validation(validation_results) if validation_results
          end

          # DETECT issues
          issues = detect_runtime_issues(build_result[:log], ui_tree)
        else
          # Launch failure is an issue
          issues << {
            type: :crash,
            severity: 'critical',
            message: "App failed to launch: #{launch_result[:error]}",
            timestamp: Time.now.utc.iso8601
          }
        end
      else
        # Build failure is an issue
        issues = @issue_detector.analyze_build_log(build_result[:log])
      end

      # SUCCESS - no issues detected
      if issues.empty?
        log_success "✅ No issues detected! App is working."
        finish_iteration(iteration, true, iteration_start)
        @state.complete_session(
          success: true,
          total_duration_ms: elapsed_ms(@start_time),
          issues_fixed: iteration - 1
        )
        return true
      end

      # CIRCUIT BREAKER check
      begin
        @circuit_breaker.check(issues.first[:message])
      rescue IOSTesting::CircuitBreaker::CircuitBreakerError => e
        raise e # Re-raise to be handled by outer rescue
      end

      # FIX phase - Delegate to Mobile Dev agent
      log_warning "❌ Issues detected (#{issues.length}):"
      issues.each { |issue| log_warning "  - [#{issue[:severity]}] #{issue[:message]}" }

      diagnostic_bundle = create_diagnostic_bundle(issues, build_result[:log], screenshot, ui_tree)

      log_info "🤖 Delegating to Mobile Dev agent for fixes..."
      fix_result = delegate_to_mobile_dev(issues, diagnostic_bundle, iteration)

      if fix_result[:success]
        log_success "✅ Fixes applied by Mobile Dev agent"
        @metrics.fix_applied(
          approach: fix_result[:approach],
          files_count: fix_result[:files_modified].length
        )

        record_iteration(iteration, issues, fix_result, true)
      else
        log_error "❌ Mobile Dev agent failed to fix issues: #{fix_result[:error]}"
        @metrics.fix_failed(reason: fix_result[:error])
        record_iteration(iteration, issues, fix_result, false)
      end

      finish_iteration(iteration, fix_result[:success], iteration_start)

      # Next iteration
      iteration += 1
      @state.increment_iteration
    end

    # Max iterations reached
    log_error "⚠️ Maximum iterations (#{@max_iterations}) reached without resolving all issues"
    @state.complete_session(
      success: false,
      total_duration_ms: elapsed_ms(@start_time),
      issues_fixed: 0
    )

    false
  end

  def run_test_suite
    log_info "🧪 Running test suite..."

    iteration_start = Time.now
    @metrics.iteration_start(iteration: 1)

    # Build for testing
    build_result = build_project
    unless build_result[:success]
      log_error "Build failed: #{build_result[:error]}"
      return finish_iteration(1, false, iteration_start)
    end

    # Run tests via xcodebuildmcp
    test_result = run_tests
    @metrics.test_complete(
      passed: test_result[:passed],
      failed: test_result[:failed],
      duration_ms: test_result[:duration_ms]
    )

    if test_result[:failed] > 0
      log_warning "❌ #{test_result[:failed]} test(s) failed"
      # Switch to debug loop to fix failures
      log_info "Switching to debug loop to fix test failures..."
      run_debug_loop
    else
      log_success "✅ All tests passed! (#{test_result[:passed]} tests)"
      finish_iteration(1, true, iteration_start)
      @state.complete_session(
        success: true,
        total_duration_ms: elapsed_ms(@start_time),
        issues_fixed: 0
      )
    end
  end

  def build_project
    log_info "🔨 Building #{@scheme}..."
    build_start = Time.now
    @metrics.build_start

    # Build for simulator using xcodebuild
    sdk = 'iphonesimulator'
    destination = "platform=iOS Simulator,name=#{@simulator}"

    # Detect workspace vs project
    use_workspace = @project_path.end_with?('.xcworkspace')
    project_flag = use_workspace ? '-workspace' : '-project'

    build_cmd = [
      'xcodebuild',
      project_flag, Shellwords.escape(@project_path),
      '-scheme', Shellwords.escape(@scheme),
      '-sdk', sdk,
      '-destination', Shellwords.escape(destination),
      'clean', 'build',
      '2>&1'
    ].join(' ')

    log_info "Running: #{build_cmd}"
    build_output = `#{build_cmd}`
    build_success = $?.success?

    duration_ms = elapsed_ms(build_start)

    result = {
      success: build_success,
      log: build_output,
      output: build_output
    }

    if build_success
      @metrics.build_success(duration_ms: duration_ms)
      log_success "✅ Build succeeded (#{duration_ms}ms)"
    else
      error_line = build_output.lines.find { |l| l =~ /\*\* BUILD FAILED \*\*/ } || 'Build failed'
      result[:error] = error_line.strip
      @metrics.build_failed(error: result[:error], duration_ms: duration_ms)
      log_error "❌ Build failed (#{duration_ms}ms)"
    end

    result
  end

  def launch_in_simulator
    log_info "🚀 Launching in #{@simulator}..."

    bundle_id = get_bundle_id

    # Boot simulator if needed
    sim_udid = get_simulator_udid(@simulator)
    unless sim_udid
      return { success: false, error: "Simulator '#{@simulator}' not found" }
    end

    # Boot the simulator
    system('xcrun', 'simctl', 'boot', sim_udid, err: '/dev/null')
    sleep 2  # Wait for boot

    # Install the app
    app_path = find_built_app
    unless app_path
      return { success: false, error: "Built app not found in DerivedData" }
    end

    install_output = `xcrun simctl install #{Shellwords.escape(sim_udid)} #{Shellwords.escape(app_path)} 2>&1`
    unless $?.success?
      return { success: false, error: "Failed to install app: #{install_output}" }
    end

    # Launch the app
    launch_output = `xcrun simctl launch #{Shellwords.escape(sim_udid)} #{Shellwords.escape(bundle_id)} 2>&1`
    launch_success = $?.success?

    if launch_success
      log_success "✅ App launched successfully"
      { success: true, output: launch_output }
    else
      log_error "❌ App launch failed: #{launch_output}"
      { success: false, error: launch_output }
    end
  end

  def capture_screenshot
    log_info "📸 Capturing screenshot..."
    sim_udid = get_simulator_udid(@simulator)
    return nil unless sim_udid

    # Create screenshots directory
    screenshots_dir = File.join(@state.state_dir, 'screenshots')
    FileUtils.mkdir_p(screenshots_dir)

    timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
    screenshot_path = File.join(screenshots_dir, "screenshot_#{timestamp}.png")

    # Capture screenshot using simctl
    system('xcrun', 'simctl', 'io', sim_udid, 'screenshot', screenshot_path, out: '/dev/null', err: '/dev/null')

    if $?.success? && File.exist?(screenshot_path)
      log_success "Screenshot saved to #{screenshot_path}"
      screenshot_path
    else
      log_warning "Failed to capture screenshot"
      nil
    end
  end

  def capture_ui_tree
    log_info "🌳 Capturing UI tree..."
    sim_udid = get_simulator_udid(@simulator)
    return nil unless sim_udid

    # Get UI hierarchy using simctl
    ui_output = `xcrun simctl ui #{Shellwords.escape(sim_udid)} dump 2>&1`

    if $?.success?
      ui_output
    else
      log_warning "Failed to capture UI tree"
      nil
    end
  end

  def run_tests
    log_info "🧪 Running tests..."
    test_start = Time.now
    @metrics.test_start(test_count: 0) # Will be updated with actual count

    destination = "platform=iOS Simulator,name=#{@simulator}"

    # Detect workspace vs project
    use_workspace = @project_path.end_with?('.xcworkspace')
    project_flag = use_workspace ? '-workspace' : '-project'

    test_cmd = [
      'xcodebuild',
      'test',
      project_flag, Shellwords.escape(@project_path),
      '-scheme', Shellwords.escape(@scheme),
      '-destination', Shellwords.escape(destination),
      '2>&1'
    ].join(' ')

    log_info "Running: #{test_cmd}"
    test_output = `#{test_cmd}`
    test_success = $?.success?

    # Parse test results
    passed = test_output.scan(/Test Case.*passed/).length
    failed = test_output.scan(/Test Case.*failed/).length
    duration_ms = elapsed_ms(test_start)

    {
      success: test_success,
      passed: passed,
      failed: failed,
      duration_ms: duration_ms,
      output: test_output
    }
  end

  def detect_runtime_issues(build_log, ui_tree)
    issues = []

    # Analyze build log
    issues += @issue_detector.analyze_build_log(build_log) if build_log

    # Analyze UI tree (check for expected elements - project-specific)
    # This would be enhanced based on project requirements

    issues
  end

  def create_diagnostic_bundle(issues, build_log, screenshot, ui_tree)
    bundle_dir = @state.create_diagnostic_bundle(issues.first)

    # Save diagnostic artifacts
    File.write(File.join(bundle_dir, 'build_log.txt'), build_log) if build_log
    File.write(File.join(bundle_dir, 'ui_tree.json'), JSON.pretty_generate(ui_tree)) if ui_tree
    FileUtils.cp(screenshot, File.join(bundle_dir, 'screenshot.png')) if screenshot && File.exist?(screenshot)

    # Save git diff if in git repo
    if system('git rev-parse --git-dir > /dev/null 2>&1')
      git_diff = `git diff`
      File.write(File.join(bundle_dir, 'git_diff.patch'), git_diff) unless git_diff.empty?
    end

    bundle_dir
  end

  def delegate_to_mobile_dev(issues, diagnostic_bundle, iteration)
    # Create delegation context and prompt
    context_file = @delegator.save_delegation_context(issues, diagnostic_bundle, iteration)
    prompt = @delegator.create_delegation_prompt(issues, diagnostic_bundle, iteration)

    log_info "📝 Delegation context saved to: #{context_file}"
    log_info "Diagnostic bundle: #{diagnostic_bundle}"
    log_info ""
    log_info "=" * 80
    log_info "DELEGATION TO MOBILE DEV AGENT"
    log_info "=" * 80
    puts prompt
    log_info "=" * 80
    log_info ""

    # Check if running in automated mode (Claude Code agent session)
    if ENV['CLAUDE_CODE_SESSION'] || ENV['AUTOMATED_MODE']
      # Running in agent session - write delegation signal file
      delegation_signal = File.join(diagnostic_bundle, 'DELEGATION_NEEDED.json')
      File.write(delegation_signal, JSON.pretty_generate({
        context_file: context_file,
        diagnostic_bundle: diagnostic_bundle,
        prompt: prompt,
        timestamp: Time.now.utc.iso8601
      }))

      log_info "🤖 Delegation signal created: #{delegation_signal}"
      log_info "Waiting for Mobile Dev agent to apply fixes..."
      log_info "(Run this script again after fixes are applied to continue testing)"

      # Exit with special code to signal delegation needed
      exit(42) # Special exit code meaning "delegation needed"
    else
      # Running standalone - prompt for manual intervention
      log_warning "⚠️ Running in standalone mode"
      log_info "Please apply fixes manually and re-run this script"
      log_info "Or invoke Mobile Dev agent with the prompt above"

      {
        success: false,
        approach: 'manual_intervention_required',
        files_modified: [],
        error: 'Delegation requires Claude Code agent session'
      }
    end
  end

  def get_bundle_id
    # Extract bundle ID from project using xcodeproj gem
    require 'xcodeproj'

    begin
      project = Xcodeproj::Project.open(@project_path)

      # Find the target that matches our scheme
      target = project.targets.find { |t| t.name == @scheme }
      return "com.example.#{@scheme}" unless target

      # Get bundle identifier from build settings
      build_config = target.build_configurations.first
      bundle_id = build_config.build_settings['PRODUCT_BUNDLE_IDENTIFIER']

      bundle_id || "com.example.#{@scheme}"
    rescue => e
      log_warning "Failed to extract bundle ID: #{e.message}"
      "com.example.#{@scheme}"
    end
  end

  def get_simulator_udid(simulator_name)
    # Get simulator UDID by name
    sims_output = `xcrun simctl list devices available`

    # Parse output to find matching simulator
    sims_output.each_line do |line|
      if line.include?(simulator_name) && line =~ /\(([A-F0-9-]+)\)/
        return $1
      end
    end

    nil
  end

  def find_built_app
    # Find the built .app in DerivedData
    # Look for the app that matches the scheme name
    derived_data = File.expand_path('~/Library/Developer/Xcode/DerivedData')

    # Find the most recent .app bundle for this project
    app_pattern = "#{derived_data}/**/Build/Products/Debug-iphonesimulator/#{@scheme}.app"

    apps = Dir.glob(app_pattern).sort_by { |f| File.mtime(f) }
    apps.last  # Return most recently modified
  end

  def record_iteration(iteration, issues, fix_result, success)
    iteration_data = {
      iteration: iteration,
      timestamp: Time.now.utc.iso8601,
      issues_detected: issues,
      fix_applied: fix_result,
      outcome: success ? 'success' : 'failure'
    }

    @state.add_iteration(iteration_data)
  end

  def finish_iteration(iteration, success, start_time)
    duration_ms = elapsed_ms(start_time)
    @metrics.iteration_complete(
      iteration: iteration,
      success: success,
      duration_ms: duration_ms
    )
  end

  def finalize_session
    duration_ms = elapsed_ms(@start_time)
    @metrics.session_complete(
      iterations: @state.session[:current_iteration] - 1,
      success: @state.session[:status] == 'completed',
      duration_ms: duration_ms
    )

    generate_final_report
  end

  def generate_final_report
    log_section "Final Report"
    puts
    puts "Session ID: #{@state.session[:session_id]}"
    puts "Project: #{File.basename(@project_path)}"
    puts "Scheme: #{@scheme}"
    puts "Simulator: #{@simulator}"
    puts "Status: #{@state.session[:status]}"
    puts "Iterations: #{@state.session[:current_iteration] - 1}/#{@max_iterations}"
    puts "Duration: #{(elapsed_ms(@start_time) / 1000.0).round(2)}s"
    puts
    puts "State saved to: #{@state.state_dir}"
    puts "Metrics saved to: #{File.join(@state.state_dir, 'metrics.jsonl')}"
    puts

    summary = @metrics.summary_report
    puts "Metrics Summary:"
    summary.each { |k, v| puts "  #{k}: #{v}" }
  end

  def handle_circuit_breaker(error)
    log_error "🔴 #{error.message}"
    log_error "Circuit breaker triggered - same error repeated 3 times"
    log_info "Manual intervention required. See diagnostic bundles in #{@state.diagnostics_dir}"

    @state.complete_session(
      success: false,
      total_duration_ms: elapsed_ms(@start_time),
      issues_fixed: 0
    )

    finalize_session
    exit 1
  end

  def handle_error(error)
    log_error "💥 Fatal error: #{error.message}"
    error.backtrace.first(5).each { |line| log_error "  #{line}" }

    @state.complete_session(
      success: false,
      total_duration_ms: elapsed_ms(@start_time),
      issues_fixed: 0
    )

    finalize_session
    exit 1
  end

  def cleanup
    # Cleanup resources
    log_info "Cleaning up..."
  end

  def validate_project!
    unless File.exist?(@project_path)
      error_exit("Project not found: #{@project_path}")
    end

    unless @project_path.end_with?('.xcodeproj') || @project_path.end_with?('.xcworkspace')
      error_exit("Invalid project: must be .xcodeproj or .xcworkspace")
    end
  end

  def elapsed_ms(start_time)
    ((Time.now - start_time) * 1000).to_i
  end

  # Logging helpers
  def log_banner
    puts "\n" + "=" * 80
    puts "  iOS Testing Agentic Loop v#{VERSION}"
    puts "=" * 80
    puts
  end

  def log_section(title)
    puts "\n" + "-" * 80
    puts "  #{title}"
    puts "-" * 80
  end

  def log_info(message)
    puts "[INFO] #{message}"
  end

  def log_success(message)
    puts "\e[32m[SUCCESS]\e[0m #{message}"
  end

  def log_warning(message)
    puts "\e[33m[WARN]\e[0m #{message}"
  end

  def log_error(message)
    puts "\e[31m[ERROR]\e[0m #{message}"
  end

  def error_exit(message)
    log_error(message)
    exit 1
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  options = {
    simulator: 'iPhone 16',
    max_iterations: 10,
    mode: 'debug'
  }

  OptionParser.new do |opts|
    opts.banner = "Usage: ios_testing_loop.rb [options] PROJECT_PATH SCHEME"

    opts.on('--simulator NAME', 'Simulator name (default: iPhone 16)') do |v|
      options[:simulator] = v
    end

    opts.on('--max-iterations N', Integer, 'Maximum iterations (default: 10)') do |v|
      options[:max_iterations] = v
    end

    opts.on('--mode MODE', %w[quick debug test], 'Mode: quick, debug, or test (default: debug)') do |v|
      options[:mode] = v
    end

    opts.on('-h', '--help', 'Show this help') do
      puts opts
      exit
    end
  end.parse!

  if ARGV.length < 2
    puts "Error: PROJECT_PATH and SCHEME required"
    puts "Usage: ios_testing_loop.rb [options] PROJECT_PATH SCHEME"
    exit 1
  end

  project_path = ARGV[0]
  scheme = ARGV[1]

  loop = IOSTestingLoop.new(
    project_path: project_path,
    scheme: scheme,
    simulator: options[:simulator],
    max_iterations: options[:max_iterations],
    mode: options[:mode]
  )

  loop.run
end
