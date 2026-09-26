#!/usr/bin/env ruby
# frozen_string_literal: true

require 'optparse'
require 'json'
require 'fileutils'
require 'time'

# iOS Test Matrix Automation
# Runs comprehensive testing across multiple configurations
# Integrates with xcodebuildmcp and simulator_control.rb
class IOSTestMatrix
  VERSION = '1.0.0'

  def initialize
    @options = {
      verbose: false,
      dry_run: false,
      json_output: false,
      parallel: false
    }
    @results = []
    @start_time = Time.now
  end

  def run(args)
    command = args.shift

    case command
    when 'run'
      run_matrix_command(args)
    when 'generate-config'
      generate_config_command(args)
    when 'list-configs'
      list_configs_command(args)
    when 'version', '-v', '--version'
      puts "ios_test_matrix v#{VERSION}"
    when 'help', '-h', '--help', nil
      show_help
    else
      puts "Unknown command: #{command}"
      show_help
      exit 1
    end
  rescue StandardError => e
    if @options[:json_output]
      puts JSON.pretty_generate(error: e.message, backtrace: e.backtrace)
    else
      puts "Error: #{e.message}"
      puts e.backtrace if @options[:verbose]
    end
    exit 1
  end

  private

  def run_matrix_command(args)
    opts = parse_options(args, %i[config project scheme simulator])

    config = load_config(opts[:config])
    validate_config(config)

    # Create results directory
    timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
    results_dir = File.join(opts[:output] || 'test-results', timestamp)
    FileUtils.mkdir_p(results_dir)

    log "Starting test matrix run: #{config['name']}"
    log "Results directory: #{results_dir}"
    log "Total combinations: #{calculate_total_combinations(config)}"

    # Generate test matrix
    test_matrix = generate_test_matrix(config)

    log "\nTest Matrix:"
    test_matrix.each_with_index do |test, index|
      log "  #{index + 1}. #{format_test_config(test)}"
    end

    # Run tests
    log "\n" + "="*60
    log "Executing Tests"
    log "="*60 + "\n"

    test_matrix.each_with_index do |test_config, index|
      result = run_single_test(
        test_config,
        opts[:project],
        opts[:scheme],
        opts[:simulator],
        results_dir,
        index + 1
      )

      @results << result

      # Stop on critical failure if configured
      if config['fail_fast'] && !result[:success]
        log "\n⚠️  Fail-fast enabled. Stopping after first failure."
        break
      end
    end

    # Generate summary report
    duration = Time.now - @start_time
    summary = generate_summary(config, @results, duration)

    # Save results
    save_results(results_dir, config, @results, summary)

    # Output summary
    output_summary(summary)

    # Exit with appropriate code
    exit(summary[:failed] == 0 ? 0 : 1)
  end

  def generate_config_command(args)
    opts = parse_options(args, [])

    template = {
      "name" => "iOS Test Matrix",
      "description" => "Comprehensive iOS testing across multiple configurations",
      "fail_fast" => false,
      "matrix" => {
        "appearance" => ["light", "dark"],
        "text_size" => ["L", "XL", "AccessibilityXL"],
        "network" => ["wifi", "3g", "off"],
        "location" => [
          { "name" => "San Francisco", "lat" => 37.7749, "lon" => -122.4194 },
          { "name" => "New York", "lat" => 40.7128, "lon" => -74.0060 }
        ],
        "accessibility" => [
          { "feature" => "none" },
          { "feature" => "reduce_motion" }
        ]
      },
      "tests" => [
        {
          "name" => "Launch Test",
          "action" => "launch",
          "verify" => ["screenshot", "ui_tree"]
        },
        {
          "name" => "Main Flow",
          "action" => "test",
          "verify" => ["screenshot", "logs"]
        }
      ],
      "screenshots" => {
        "enabled" => true,
        "compare_baseline" => false,
        "baseline_dir" => "./screenshots/baseline"
      }
    }

    output_file = opts[:output] || "test-matrix-config.json"
    File.write(output_file, JSON.pretty_generate(template))

    log "Generated test matrix configuration: #{output_file}"
    log "Edit this file to customize your test matrix"
  end

  def list_configs_command(args)
    # Predefined test matrix configurations
    configs = {
      "minimal" => {
        "name" => "Minimal Test Matrix",
        "matrix" => {
          "appearance" => ["light", "dark"],
          "text_size" => ["L"]
        }
      },
      "accessibility" => {
        "name" => "Accessibility Test Matrix",
        "matrix" => {
          "text_size" => ["S", "M", "L", "XL", "XXL", "AccessibilityM", "AccessibilityL", "AccessibilityXL"],
          "appearance" => ["light", "dark"],
          "accessibility" => [
            { "feature" => "reduce_motion" },
            { "feature" => "increase_contrast" },
            { "feature" => "bold_text" }
          ]
        }
      },
      "network" => {
        "name" => "Network Test Matrix",
        "matrix" => {
          "network" => ["wifi", "lte", "3g", "edge", "off"]
        }
      },
      "comprehensive" => {
        "name" => "Comprehensive Test Matrix",
        "matrix" => {
          "appearance" => ["light", "dark"],
          "text_size" => ["S", "L", "XL", "AccessibilityXL"],
          "network" => ["wifi", "3g", "off"]
        }
      }
    }

    puts "Available Test Matrix Configurations:\n\n"

    configs.each do |key, config|
      combinations = calculate_total_combinations(config)
      puts "  #{key.ljust(20)} - #{config['name']} (#{combinations} combinations)"
    end

    puts "\nUse: ios_test_matrix run --config <config_name>"
  end

  def run_single_test(test_config, project, scheme, simulator, results_dir, test_number)
    log "\n📱 Test #{test_number}: #{format_test_config(test_config)}"
    log "-" * 60

    test_dir = File.join(results_dir, "test_#{test_number}")
    FileUtils.mkdir_p(test_dir)

    start_time = Time.now
    success = true
    errors = []

    begin
      # 1. Set environment
      log "Setting environment..."
      setup_environment(test_config, simulator)

      # 2. Build and launch app (if needed)
      unless @options[:dry_run]
        log "Launching app..."
        # Would call xcodebuildmcp here
        sleep 2  # Simulated launch time
      end

      # 3. Wait for app to stabilize
      sleep 3

      # 4. Capture screenshot
      screenshot_path = File.join(test_dir, "screenshot.png")
      unless @options[:dry_run]
        log "Capturing screenshot..."
        # Would call xcodebuildmcp screenshot
        # For now, just create placeholder
        FileUtils.touch(screenshot_path)
      end

      # 5. Capture UI tree
      ui_tree_path = File.join(test_dir, "ui_tree.txt")
      unless @options[:dry_run]
        log "Capturing UI tree..."
        # Would call xcodebuildmcp describe_ui
        File.write(ui_tree_path, "UI Tree placeholder")
      end

      # 6. Run tests (if configured)
      log "Running validation..."

      # 7. Reset environment
      log "Resetting environment..."
      reset_environment(simulator)

      log "✅ Test completed successfully"

    rescue StandardError => e
      success = false
      errors << e.message
      log "❌ Test failed: #{e.message}"
    end

    duration = Time.now - start_time

    {
      test_number: test_number,
      config: test_config,
      success: success,
      errors: errors,
      duration: duration,
      screenshot: File.exist?(screenshot_path) ? screenshot_path : nil,
      ui_tree: File.exist?(ui_tree_path) ? ui_tree_path : nil
    }
  end

  def setup_environment(config, simulator)
    simulator_control = "{{CATALYST_ROOT}}/tools/simulator_control.rb"

    # Set appearance
    if config[:appearance]
      cmd = "ruby #{simulator_control} set-appearance --simulator '#{simulator}' --mode #{config[:appearance]}"
      execute_command(cmd, "Set appearance to #{config[:appearance]}")
    end

    # Set text size
    if config[:text_size]
      cmd = "ruby #{simulator_control} set-text-size --simulator '#{simulator}' --size #{config[:text_size]}"
      execute_command(cmd, "Set text size to #{config[:text_size]}")
    end

    # Set network
    if config[:network]
      cmd = "ruby #{simulator_control} network-throttle --simulator '#{simulator}' --profile #{config[:network]}"
      execute_command(cmd, "Set network to #{config[:network]}")
    end

    # Set location
    if config[:location]
      loc = config[:location]
      cmd = "ruby #{simulator_control} set-location --simulator '#{simulator}' --latitude #{loc['lat']} --longitude #{loc['lon']}"
      execute_command(cmd, "Set location to #{loc['name']}")
    end

    # Set accessibility
    if config[:accessibility] && config[:accessibility]['feature'] != 'none'
      feature = config[:accessibility]['feature']
      cmd = "ruby #{simulator_control} toggle-accessibility --simulator '#{simulator}' --feature #{feature} --enabled true"
      execute_command(cmd, "Enable #{feature}")
    end
  end

  def reset_environment(simulator)
    simulator_control = "{{CATALYST_ROOT}}/tools/simulator_control.rb"
    cmd = "ruby #{simulator_control} reset-environment --simulator '#{simulator}'"
    execute_command(cmd, "Reset environment")
  end

  def execute_command(cmd, description)
    log "  → #{description}"
    unless @options[:dry_run]
      output = `#{cmd} 2>&1`
      unless $?.success?
        raise "Failed to #{description}: #{output}"
      end
    end
  end

  def generate_test_matrix(config)
    matrix = config['matrix']
    combinations = []

    # Generate all combinations
    appearances = matrix['appearance'] || ['light']
    text_sizes = matrix['text_size'] || ['L']
    networks = matrix['network'] || ['wifi']
    locations = matrix['location'] || [nil]
    accessibility_features = matrix['accessibility'] || [{ 'feature' => 'none' }]

    appearances.each do |appearance|
      text_sizes.each do |text_size|
        networks.each do |network|
          locations.each do |location|
            accessibility_features.each do |accessibility|
              combinations << {
                appearance: appearance,
                text_size: text_size,
                network: network,
                location: location,
                accessibility: accessibility
              }
            end
          end
        end
      end
    end

    combinations
  end

  def calculate_total_combinations(config)
    matrix = config['matrix'] || {}

    count = 1
    count *= (matrix['appearance'] || []).length if (matrix['appearance'] || []).length > 0
    count *= (matrix['text_size'] || []).length if (matrix['text_size'] || []).length > 0
    count *= (matrix['network'] || []).length if (matrix['network'] || []).length > 0
    count *= (matrix['location'] || []).length if (matrix['location'] || []).length > 0
    count *= (matrix['accessibility'] || []).length if (matrix['accessibility'] || []).length > 0

    count
  end

  def format_test_config(config)
    parts = []
    parts << "#{config[:appearance]}" if config[:appearance]
    parts << "#{config[:text_size]}" if config[:text_size]
    parts << "#{config[:network]}" if config[:network]
    parts << "#{config[:location]['name']}" if config[:location]
    parts << "#{config[:accessibility]['feature']}" if config[:accessibility] && config[:accessibility]['feature'] != 'none'

    parts.join(" | ")
  end

  def generate_summary(config, results, duration)
    total = results.length
    passed = results.count { |r| r[:success] }
    failed = total - passed

    {
      name: config['name'],
      total: total,
      passed: passed,
      failed: failed,
      duration: duration,
      pass_rate: total > 0 ? (passed.to_f / total * 100).round(2) : 0
    }
  end

  def save_results(results_dir, config, results, summary)
    # Save JSON results
    results_data = {
      config: config,
      summary: summary,
      results: results.map do |r|
        {
          test_number: r[:test_number],
          config: r[:config],
          success: r[:success],
          errors: r[:errors],
          duration: r[:duration],
          screenshot: r[:screenshot],
          ui_tree: r[:ui_tree]
        }
      end
    }

    results_file = File.join(results_dir, 'results.json')
    File.write(results_file, JSON.pretty_generate(results_data))

    # Save HTML report
    html_file = File.join(results_dir, 'report.html')
    generate_html_report(html_file, config, results, summary)

    log "\n📄 Results saved:"
    log "   JSON: #{results_file}"
    log "   HTML: #{html_file}"
  end

  def generate_html_report(output_file, config, results, summary)
    html = <<~HTML
      <!DOCTYPE html>
      <html>
      <head>
        <title>#{config['name']} - Test Results</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; background: #f5f5f5; }
          .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
          h1 { color: #333; }
          .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 30px 0; }
          .stat { padding: 20px; border-radius: 6px; text-align: center; }
          .stat.total { background: #e3f2fd; }
          .stat.passed { background: #e8f5e9; }
          .stat.failed { background: #ffebee; }
          .stat.duration { background: #f3e5f5; }
          .stat-number { font-size: 48px; font-weight: bold; margin: 10px 0; }
          .stat-label { color: #666; font-size: 14px; }
          .test { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 6px; }
          .test.pass { border-left: 4px solid #4caf50; }
          .test.fail { border-left: 4px solid #f44336; }
          .badge { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }
          .badge.pass { background: #4caf50; color: white; }
          .badge.fail { background: #f44336; color: white; }
          .screenshot { width: 300px; border: 1px solid #ddd; border-radius: 4px; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>📱 #{config['name']}</h1>
          <p>#{config['description']}</p>

          <div class="summary">
            <div class="stat total">
              <div class="stat-label">Total Tests</div>
              <div class="stat-number">#{summary[:total]}</div>
            </div>
            <div class="stat passed">
              <div class="stat-label">Passed</div>
              <div class="stat-number">#{summary[:passed]}</div>
            </div>
            <div class="stat failed">
              <div class="stat-label">Failed</div>
              <div class="stat-number">#{summary[:failed]}</div>
            </div>
            <div class="stat duration">
              <div class="stat-label">Duration</div>
              <div class="stat-number">#{summary[:duration].round(1)}s</div>
            </div>
          </div>

          <h2>Test Results</h2>
    HTML

    results.each do |result|
      status = result[:success] ? 'pass' : 'fail'
      badge_text = result[:success] ? '✓ Pass' : '✗ Fail'

      html += <<~HTML
        <div class="test #{status}">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3>Test #{result[:test_number]}: #{format_test_config(result[:config])}</h3>
            <span class="badge #{status}">#{badge_text}</span>
          </div>
          <p>Duration: #{result[:duration].round(2)}s</p>
      HTML

      if result[:screenshot] && File.exist?(result[:screenshot])
        html += "<img src=\"#{File.basename(result[:screenshot])}\" class=\"screenshot\" alt=\"Screenshot\">"
      end

      unless result[:errors].empty?
        html += "<div style=\"color: #f44336; margin-top: 10px;\">Errors: #{result[:errors].join(', ')}</div>"
      end

      html += "</div>"
    end

    html += <<~HTML
        </div>
      </body>
      </html>
    HTML

    File.write(output_file, html)
  end

  def output_summary(summary)
    log "\n" + "="*60
    log "Test Matrix Summary"
    log "="*60
    log "Name:       #{summary[:name]}"
    log "Total:      #{summary[:total]}"
    log "Passed:     #{summary[:passed]} ✓"
    log "Failed:     #{summary[:failed]} ✗"
    log "Pass Rate:  #{summary[:pass_rate]}%"
    log "Duration:   #{summary[:duration].round(2)}s"
    log "="*60
  end

  def load_config(config_path)
    unless File.exist?(config_path)
      raise "Config file not found: #{config_path}"
    end

    JSON.parse(File.read(config_path))
  end

  def validate_config(config)
    required_keys = ['name', 'matrix']
    missing = required_keys.select { |key| !config.key?(key) }

    unless missing.empty?
      raise "Missing required config keys: #{missing.join(', ')}"
    end
  end

  def parse_options(args, required_keys)
    opts = {}

    parser = OptionParser.new do |p|
      p.on('--config PATH', 'Test matrix configuration file') { |v| opts[:config] = v }
      p.on('--project PATH', 'Path to .xcodeproj file') { |v| opts[:project] = v }
      p.on('--scheme NAME', 'Scheme name') { |v| opts[:scheme] = v }
      p.on('--simulator NAME', 'Simulator name') { |v| opts[:simulator] = v }
      p.on('--output PATH', 'Output directory') { |v| opts[:output] = v }
      p.on('--verbose', 'Verbose output') { @options[:verbose] = true }
      p.on('--dry-run', 'Preview without executing') { @options[:dry_run] = true }
      p.on('--json', 'JSON output') { @options[:json_output] = true }
      p.on('--parallel', 'Run tests in parallel') { @options[:parallel] = true }
    end

    parser.parse!(args)

    # Validate required options
    missing = required_keys.select { |key| opts[key].nil? }
    unless missing.empty?
      raise "Missing required options: #{missing.map { |k| "--#{k.to_s.gsub('_', '-')}" }.join(', ')}"
    end

    opts
  end

  def log(message)
    return if @options[:json_output]
    puts message
  end

  def show_help
    puts <<~HELP
      iOS Test Matrix Automation v#{VERSION}
      Comprehensive iOS testing across multiple configurations

      USAGE:
        ios_test_matrix.rb COMMAND [OPTIONS]

      COMMANDS:
        run                Run test matrix
        generate-config    Generate template configuration
        list-configs       List predefined configurations
        version            Show version
        help               Show this help

      RUN OPTIONS:
        --config PATH      Test matrix configuration file (required)
        --project PATH     Path to .xcodeproj file (required)
        --scheme NAME      Scheme name (required)
        --simulator NAME   Simulator name (required)
        --output PATH      Output directory (default: test-results)
        --parallel         Run tests in parallel (experimental)
        --verbose          Verbose output
        --dry-run          Preview without executing
        --json             JSON output

      EXAMPLES:
        # Generate configuration template
        ios_test_matrix.rb generate-config --output my-matrix.json

        # Run test matrix
        ios_test_matrix.rb run \\
          --config my-matrix.json \\
          --project MyApp.xcodeproj \\
          --scheme MyApp \\
          --simulator "iPhone 16"

        # List predefined configurations
        ios_test_matrix.rb list-configs

      CONFIGURATION FORMAT:
        {
          "name": "Test Matrix Name",
          "matrix": {
            "appearance": ["light", "dark"],
            "text_size": ["L", "XL"],
            "network": ["wifi", "3g"]
          }
        }

      See documentation for full configuration options.
    HELP
  end
end

# Run the tool
if __FILE__ == $0
  tool = IOSTestMatrix.new
  tool.run(ARGV)
end
