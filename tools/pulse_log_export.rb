#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'csv'
require 'time'
require 'fileutils'
require 'optparse'

# Pulse Network Log Export Tool
# Extracts and analyzes network logs from Pulse LoggerStore for debugging and analysis
#
# Features:
# - Export logs in multiple formats (JSON, CSV, text, HTML)
# - Filter by request type, status code, time range, URL pattern
# - Generate analysis reports (request counts, error rates, performance)
# - Identify slow requests and failures
# - Export request/response bodies and headers
#
# Usage:
#   ruby pulse_log_export.rb export --app-id com.example.app --format json
#   ruby pulse_log_export.rb analyze --app-id com.example.app --output report.html
#   ruby pulse_log_export.rb filter --app-id com.example.app --status 400-599 --output errors.json

class PulseLogExporter
  attr_reader :app_id, :simulator

  def initialize(app_id:, simulator: nil)
    @app_id = app_id
    @simulator = simulator
  end

  # Find Pulse database location
  def find_pulse_database
    # Pulse stores logs in App's Application Support directory
    # ~/Library/Developer/CoreSimulator/Devices/[UDID]/data/Containers/Data/Application/[APP-UUID]/Library/Application Support/com.github.kean.logger/logs.sqlite

    unless simulator
      # Get booted simulator
      output = `xcrun simctl list devices booted -j`
      devices = JSON.parse(output)
      booted = devices['devices'].values.flatten.select { |d| d['state'] == 'Booted' }

      if booted.empty?
        puts "❌ No booted simulators found. Boot a simulator first."
        exit 1
      end

      @simulator = booted.first['udid']
    end

    # Find app container
    app_container = `xcrun simctl get_app_container #{simulator} #{app_id}`.strip

    if app_container.empty? || !File.exist?(app_container)
      puts "❌ Could not find app container for #{app_id}"
      puts "   Make sure the app is installed on simulator #{simulator}"
      exit 1
    end

    # Pulse database location
    pulse_dir = File.join(app_container, 'Library', 'Application Support', 'com.github.kean.logger')
    db_path = File.join(pulse_dir, 'logs.sqlite')

    unless File.exist?(db_path)
      puts "❌ Pulse database not found at #{db_path}"
      puts "   Make sure Pulse is integrated and app has made network requests"
      exit 1
    end

    db_path
  end

  # Extract logs from Pulse database using sqlite3
  def extract_logs(filters: {})
    db_path = find_pulse_database

    puts "📊 Extracting logs from Pulse database..."
    puts "   Database: #{db_path}"

    # Query Pulse database
    # Pulse stores network requests in LoggerMessageEntity table
    query = build_query(filters)

    output = `sqlite3 -json "#{db_path}" "#{query}"`

    if output.empty?
      puts "⚠️  No logs found matching filters"
      return []
    end

    logs = JSON.parse(output)
    puts "✅ Extracted #{logs.size} network requests"

    logs
  rescue JSON::ParserError => e
    puts "❌ Failed to parse database output: #{e.message}"
    []
  end

  # Build SQLite query with filters
  def build_query(filters)
    # Pulse database schema (simplified):
    # - LoggerMessageEntity: Main log entries
    # - LoggerNetworkRequestEntity: Network request details
    # - LoggerBlobEntity: Request/response bodies

    conditions = []

    # Status code filter
    if filters[:status_min] && filters[:status_max]
      conditions << "statusCode >= #{filters[:status_min]} AND statusCode <= #{filters[:status_max]}"
    elsif filters[:status_code]
      conditions << "statusCode = #{filters[:status_code]}"
    end

    # URL pattern filter
    if filters[:url_pattern]
      conditions << "url LIKE '%#{filters[:url_pattern]}%'"
    end

    # Time range filter
    if filters[:start_time]
      conditions << "createdAt >= '#{filters[:start_time].iso8601}'"
    end
    if filters[:end_time]
      conditions << "createdAt <= '#{filters[:end_time].iso8601}'"
    end

    # HTTP method filter
    if filters[:method]
      conditions << "httpMethod = '#{filters[:method]}'"
    end

    where_clause = conditions.empty? ? "" : "WHERE #{conditions.join(' AND ')}"

    # Query to extract network requests
    <<~SQL
      SELECT
        createdAt as timestamp,
        url,
        httpMethod as method,
        statusCode as status,
        requestDuration as duration,
        requestBodySize as request_size,
        responseBodySize as response_size,
        errorCode as error,
        host,
        path
      FROM LoggerNetworkRequestEntity
      #{where_clause}
      ORDER BY createdAt DESC;
    SQL
  end

  # Export logs to specified format
  def export(format:, output:, filters: {})
    logs = extract_logs(filters: filters)
    return if logs.empty?

    case format
    when 'json'
      export_json(logs, output)
    when 'csv'
      export_csv(logs, output)
    when 'text'
      export_text(logs, output)
    when 'html'
      export_html(logs, output)
    else
      puts "❌ Unknown format: #{format}"
      exit 1
    end
  end

  # Export as JSON
  def export_json(logs, output)
    File.write(output, JSON.pretty_generate(logs))
    puts "✅ Exported #{logs.size} requests to #{output}"
  end

  # Export as CSV
  def export_csv(logs, output)
    CSV.open(output, 'w') do |csv|
      # Header
      csv << ['Timestamp', 'Method', 'URL', 'Status', 'Duration (ms)', 'Request Size', 'Response Size', 'Error']

      # Rows
      logs.each do |log|
        csv << [
          log['timestamp'],
          log['method'],
          log['url'],
          log['status'],
          (log['duration'].to_f * 1000).round(2),
          log['request_size'],
          log['response_size'],
          log['error']
        ]
      end
    end

    puts "✅ Exported #{logs.size} requests to #{output}"
  end

  # Export as plain text
  def export_text(logs, output)
    File.open(output, 'w') do |f|
      f.puts "Pulse Network Logs Export"
      f.puts "=" * 80
      f.puts "Total Requests: #{logs.size}"
      f.puts "Exported: #{Time.now}"
      f.puts "=" * 80
      f.puts

      logs.each_with_index do |log, i|
        f.puts "Request ##{i + 1}"
        f.puts "-" * 80
        f.puts "Timestamp: #{log['timestamp']}"
        f.puts "Method:    #{log['method']}"
        f.puts "URL:       #{log['url']}"
        f.puts "Status:    #{log['status']}"
        f.puts "Duration:  #{(log['duration'].to_f * 1000).round(2)}ms"
        f.puts "Request:   #{log['request_size']} bytes"
        f.puts "Response:  #{log['response_size']} bytes"
        f.puts "Error:     #{log['error']}" if log['error']
        f.puts
      end
    end

    puts "✅ Exported #{logs.size} requests to #{output}"
  end

  # Export as HTML report
  def export_html(logs, output)
    html = generate_html_report(logs)
    File.write(output, html)
    puts "✅ Generated HTML report: #{output}"
  end

  # Generate analysis report
  def analyze(output:, filters: {})
    logs = extract_logs(filters: filters)
    return if logs.empty?

    analysis = {
      total_requests: logs.size,
      success_count: logs.count { |l| l['status'].to_i >= 200 && l['status'].to_i < 300 },
      error_count: logs.count { |l| l['status'].to_i >= 400 },
      avg_duration: (logs.map { |l| l['duration'].to_f }.sum / logs.size * 1000).round(2),
      total_data_sent: logs.map { |l| l['request_size'].to_i }.sum,
      total_data_received: logs.map { |l| l['response_size'].to_i }.sum,
      methods: logs.group_by { |l| l['method'] }.transform_values(&:size),
      status_codes: logs.group_by { |l| l['status'] }.transform_values(&:size),
      hosts: logs.group_by { |l| l['host'] }.transform_values(&:size),
      slow_requests: logs.select { |l| l['duration'].to_f > 1.0 }.sort_by { |l| -l['duration'].to_f }.first(10),
      errors: logs.select { |l| l['status'].to_i >= 400 }
    }

    if output.end_with?('.json')
      File.write(output, JSON.pretty_generate(analysis))
      puts "✅ Analysis saved to #{output}"
    elsif output.end_with?('.html')
      html = generate_analysis_html(analysis, logs)
      File.write(output, html)
      puts "✅ Analysis report saved to #{output}"
    else
      print_analysis(analysis)
    end
  end

  # Print analysis to console
  def print_analysis(analysis)
    puts
    puts "📊 Network Log Analysis"
    puts "=" * 80
    puts
    puts "Summary:"
    puts "  Total Requests:     #{analysis[:total_requests]}"
    puts "  Successful (2xx):   #{analysis[:success_count]} (#{(analysis[:success_count].to_f / analysis[:total_requests] * 100).round(1)}%)"
    puts "  Errors (4xx/5xx):   #{analysis[:error_count]} (#{(analysis[:error_count].to_f / analysis[:total_requests] * 100).round(1)}%)"
    puts "  Avg Duration:       #{analysis[:avg_duration]}ms"
    puts "  Data Sent:          #{format_bytes(analysis[:total_data_sent])}"
    puts "  Data Received:      #{format_bytes(analysis[:total_data_received])}"
    puts

    puts "HTTP Methods:"
    analysis[:methods].sort_by { |_, count| -count }.each do |method, count|
      puts "  #{method.ljust(10)} #{count} requests"
    end
    puts

    puts "Status Codes:"
    analysis[:status_codes].sort_by { |code, _| code.to_i }.each do |code, count|
      puts "  #{code}:  #{count} requests"
    end
    puts

    puts "Top Hosts:"
    analysis[:hosts].sort_by { |_, count| -count }.first(5).each do |host, count|
      puts "  #{host}: #{count} requests"
    end
    puts

    if analysis[:slow_requests].any?
      puts "Slow Requests (>1s):"
      analysis[:slow_requests].first(5).each do |req|
        puts "  #{(req['duration'].to_f * 1000).round(0)}ms - #{req['method']} #{req['url']}"
      end
      puts
    end

    if analysis[:errors].any?
      puts "Errors:"
      analysis[:errors].first(5).each do |req|
        puts "  #{req['status']} - #{req['method']} #{req['url']}"
      end
      puts
    end
  end

  # Generate HTML report with charts
  def generate_html_report(logs)
    <<~HTML
      <!DOCTYPE html>
      <html>
      <head>
        <title>Pulse Network Logs Report</title>
        <style>
          body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 40px;
            background: #f5f5f5;
          }
          .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
          }
          h1 { color: #333; }
          h2 { color: #666; margin-top: 30px; }
          .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 30px 0;
          }
          .stat {
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            text-align: center;
          }
          .stat-number {
            font-size: 32px;
            font-weight: bold;
            color: #007AFF;
          }
          .stat-label {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
          }
          table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
          }
          th {
            background: #007AFF;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
          }
          td {
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
          }
          tr:hover {
            background: #f8f9fa;
          }
          .method {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            font-family: monospace;
          }
          .method.GET { background: #E3F2FD; color: #1976D2; }
          .method.POST { background: #E8F5E9; color: #388E3C; }
          .method.PUT { background: #FFF3E0; color: #F57C00; }
          .method.DELETE { background: #FFEBEE; color: #D32F2F; }
          .status {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            font-family: monospace;
            font-size: 12px;
          }
          .status.success { background: #E8F5E9; color: #388E3C; }
          .status.error { background: #FFEBEE; color: #D32F2F; }
          .status.other { background: #F5F5F5; color: #666; }
          .duration {
            font-family: monospace;
            color: #666;
          }
          .url {
            font-family: monospace;
            font-size: 12px;
            color: #333;
            max-width: 500px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>📊 Pulse Network Logs Report</h1>
          <p>Generated: #{Time.now.strftime('%Y-%m-%d %H:%M:%S')}</p>

          <div class="stats">
            <div class="stat">
              <div class="stat-number">#{logs.size}</div>
              <div class="stat-label">Total Requests</div>
            </div>
            <div class="stat">
              <div class="stat-number">#{logs.count { |l| l['status'].to_i >= 200 && l['status'].to_i < 300 }}</div>
              <div class="stat-label">Successful</div>
            </div>
            <div class="stat">
              <div class="stat-number">#{logs.count { |l| l['status'].to_i >= 400 }}</div>
              <div class="stat-label">Errors</div>
            </div>
            <div class="stat">
              <div class="stat-number">#{(logs.map { |l| l['duration'].to_f }.sum / logs.size * 1000).round(0)}ms</div>
              <div class="stat-label">Avg Duration</div>
            </div>
          </div>

          <h2>Network Requests</h2>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Method</th>
                <th>URL</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Size</th>
              </tr>
            </thead>
            <tbody>
              #{logs.map { |log| generate_log_row(log) }.join("\n")}
            </tbody>
          </table>
        </div>
      </body>
      </html>
    HTML
  end

  # Generate HTML table row for a log entry
  def generate_log_row(log)
    status_class = if log['status'].to_i >= 200 && log['status'].to_i < 300
                     'success'
                   elsif log['status'].to_i >= 400
                     'error'
                   else
                     'other'
                   end

    timestamp = Time.parse(log['timestamp']).strftime('%H:%M:%S')
    duration = (log['duration'].to_f * 1000).round(0)
    total_size = log['request_size'].to_i + log['response_size'].to_i

    <<~HTML
      <tr>
        <td>#{timestamp}</td>
        <td><span class="method #{log['method']}">#{log['method']}</span></td>
        <td><div class="url" title="#{log['url']}">#{log['url']}</div></td>
        <td><span class="status #{status_class}">#{log['status']}</span></td>
        <td><span class="duration">#{duration}ms</span></td>
        <td>#{format_bytes(total_size)}</td>
      </tr>
    HTML
  end

  # Generate analysis HTML report
  def generate_analysis_html(analysis, logs)
    <<~HTML
      <!DOCTYPE html>
      <html>
      <head>
        <title>Pulse Network Analysis Report</title>
        <style>
          body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 40px;
            background: #f5f5f5;
          }
          .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2 10px rgba(0,0,0,0.1);
          }
          h1 { color: #333; }
          h2 { color: #666; margin-top: 40px; }
          .summary {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin: 30px 0;
          }
          .metric {
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
          }
          .metric-value {
            font-size: 36px;
            font-weight: bold;
            color: #007AFF;
          }
          .metric-label {
            color: #666;
            font-size: 14px;
            margin-top: 8px;
          }
          .chart {
            margin: 30px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
          }
          .bar {
            display: flex;
            align-items: center;
            margin: 10px 0;
          }
          .bar-label {
            width: 100px;
            font-weight: 600;
          }
          .bar-fill {
            height: 30px;
            background: #007AFF;
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-size: 12px;
            font-weight: bold;
          }
          .list {
            list-style: none;
            padding: 0;
          }
          .list li {
            padding: 12px;
            border-bottom: 1px solid #eee;
            font-family: monospace;
            font-size: 14px;
          }
          .success { color: #388E3C; }
          .error { color: #D32F2F; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>📊 Pulse Network Analysis</h1>
          <p>Generated: #{Time.now.strftime('%Y-%m-%d %H:%M:%S')}</p>

          <div class="summary">
            <div class="metric">
              <div class="metric-value">#{analysis[:total_requests]}</div>
              <div class="metric-label">Total Requests</div>
            </div>
            <div class="metric">
              <div class="metric-value" class="success">#{analysis[:success_count]}</div>
              <div class="metric-label">Successful (#{(analysis[:success_count].to_f / analysis[:total_requests] * 100).round(1)}%)</div>
            </div>
            <div class="metric">
              <div class="metric-value" class="error">#{analysis[:error_count]}</div>
              <div class="metric-label">Errors (#{(analysis[:error_count].to_f / analysis[:total_requests] * 100).round(1)}%)</div>
            </div>
          </div>

          <div class="summary">
            <div class="metric">
              <div class="metric-value">#{analysis[:avg_duration]}ms</div>
              <div class="metric-label">Avg Duration</div>
            </div>
            <div class="metric">
              <div class="metric-value">#{format_bytes(analysis[:total_data_sent])}</div>
              <div class="metric-label">Data Sent</div>
            </div>
            <div class="metric">
              <div class="metric-value">#{format_bytes(analysis[:total_data_received])}</div>
              <div class="metric-label">Data Received</div>
            </div>
          </div>

          <h2>HTTP Methods Distribution</h2>
          <div class="chart">
            #{generate_bar_chart(analysis[:methods])}
          </div>

          <h2>Status Codes</h2>
          <div class="chart">
            #{generate_bar_chart(analysis[:status_codes])}
          </div>

          #{if analysis[:slow_requests].any?
            "<h2>Slow Requests (&gt;1s)</h2>
            <ul class=\"list\">
              #{analysis[:slow_requests].first(10).map { |req|
                "<li>#{(req['duration'].to_f * 1000).round(0)}ms - #{req['method']} #{req['url']}</li>"
              }.join("\n")}
            </ul>"
          end}

          #{if analysis[:errors].any?
            "<h2>Errors</h2>
            <ul class=\"list\">
              #{analysis[:errors].first(10).map { |req|
                "<li class=\"error\">#{req['status']} - #{req['method']} #{req['url']}</li>"
              }.join("\n")}
            </ul>"
          end}
        </div>
      </body>
      </html>
    HTML
  end

  # Generate HTML bar chart
  def generate_bar_chart(data)
    max_value = data.values.max
    data.sort_by { |_, count| -count }.map do |label, count|
      width_percent = (count.to_f / max_value * 100).round(0)
      <<~HTML
        <div class="bar">
          <div class="bar-label">#{label}</div>
          <div class="bar-fill" style="width: #{width_percent}%;">#{count}</div>
        </div>
      HTML
    end.join("\n")
  end

  # Format bytes to human-readable format
  def format_bytes(bytes)
    return '0 B' if bytes.zero?

    units = ['B', 'KB', 'MB', 'GB']
    exp = (Math.log(bytes) / Math.log(1024)).floor
    exp = [exp, units.size - 1].min

    size = (bytes / (1024.0 ** exp)).round(2)
    "#{size} #{units[exp]}"
  end
end

# CLI Command Handler
class CLI
  def self.run(args)
    options = parse_options(args)

    case options[:command]
    when 'export'
      export_command(options)
    when 'analyze'
      analyze_command(options)
    when 'filter'
      filter_command(options)
    when 'list-apps'
      list_apps_command
    else
      print_help
      exit 1
    end
  end

  def self.parse_options(args)
    options = {
      command: args[0],
      format: 'json',
      output: nil,
      filters: {}
    }

    OptionParser.new do |opts|
      opts.banner = "Usage: pulse_log_export.rb <command> [options]"

      opts.on('--app-id APP_ID', 'App bundle identifier (required)') do |v|
        options[:app_id] = v
      end

      opts.on('--simulator UDID', 'Simulator UDID (auto-detect if not specified)') do |v|
        options[:simulator] = v
      end

      opts.on('--format FORMAT', 'Export format: json, csv, text, html (default: json)') do |v|
        options[:format] = v
      end

      opts.on('--output FILE', 'Output file path') do |v|
        options[:output] = v
      end

      opts.on('--status STATUS', 'Filter by status code or range (e.g., 200, 400-599)') do |v|
        if v.include?('-')
          min, max = v.split('-').map(&:to_i)
          options[:filters][:status_min] = min
          options[:filters][:status_max] = max
        else
          options[:filters][:status_code] = v.to_i
        end
      end

      opts.on('--url-pattern PATTERN', 'Filter by URL pattern') do |v|
        options[:filters][:url_pattern] = v
      end

      opts.on('--method METHOD', 'Filter by HTTP method (GET, POST, etc.)') do |v|
        options[:filters][:method] = v.upcase
      end

      opts.on('--since TIME', 'Filter requests since time (ISO8601)') do |v|
        options[:filters][:start_time] = Time.parse(v)
      end

      opts.on('--until TIME', 'Filter requests until time (ISO8601)') do |v|
        options[:filters][:end_time] = Time.parse(v)
      end

      opts.on('-h', '--help', 'Show this help') do
        puts opts
        exit
      end
    end.parse!(args[1..])

    options
  end

  def self.export_command(options)
    unless options[:app_id]
      puts "❌ --app-id is required"
      exit 1
    end

    output = options[:output] || "pulse-logs-#{Time.now.strftime('%Y%m%d-%H%M%S')}.#{options[:format]}"

    exporter = PulseLogExporter.new(
      app_id: options[:app_id],
      simulator: options[:simulator]
    )

    exporter.export(
      format: options[:format],
      output: output,
      filters: options[:filters]
    )
  end

  def self.analyze_command(options)
    unless options[:app_id]
      puts "❌ --app-id is required"
      exit 1
    end

    output = options[:output] || 'console'

    exporter = PulseLogExporter.new(
      app_id: options[:app_id],
      simulator: options[:simulator]
    )

    exporter.analyze(
      output: output,
      filters: options[:filters]
    )
  end

  def self.filter_command(options)
    unless options[:app_id]
      puts "❌ --app-id is required"
      exit 1
    end

    unless options[:filters].any?
      puts "❌ At least one filter is required (--status, --url-pattern, --method, etc.)"
      exit 1
    end

    output = options[:output] || "filtered-logs-#{Time.now.strftime('%Y%m%d-%H%M%S')}.json"

    exporter = PulseLogExporter.new(
      app_id: options[:app_id],
      simulator: options[:simulator]
    )

    exporter.export(
      format: options[:format],
      output: output,
      filters: options[:filters]
    )
  end

  def self.list_apps_command
    puts "📱 Installed Apps on Booted Simulator:"
    puts

    # Get booted simulator
    output = `xcrun simctl list devices booted -j`
    devices = JSON.parse(output)
    booted = devices['devices'].values.flatten.select { |d| d['state'] == 'Booted' }

    if booted.empty?
      puts "❌ No booted simulators found"
      exit 1
    end

    simulator = booted.first['udid']

    # List installed apps
    apps_output = `xcrun simctl listapps #{simulator}`

    # Parse app bundle IDs
    bundle_ids = apps_output.scan(/CFBundleIdentifier = "([^"]+)"/).flatten

    bundle_ids.each do |bundle_id|
      next if bundle_id.start_with?('com.apple.')
      puts "  #{bundle_id}"
    end
  end

  def self.print_help
    puts <<~HELP
      Pulse Network Log Export Tool
      ==============================

      Export and analyze network logs from Pulse LoggerStore

      Commands:
        export        Export logs to file
        analyze       Generate analysis report
        filter        Filter logs by criteria
        list-apps     List installed apps on simulator

      Examples:
        # Export all logs
        ruby pulse_log_export.rb export --app-id com.example.app --format json

        # Generate analysis report
        ruby pulse_log_export.rb analyze --app-id com.example.app --output report.html

        # Filter errors only
        ruby pulse_log_export.rb filter --app-id com.example.app --status 400-599 --output errors.json

        # Filter by URL pattern
        ruby pulse_log_export.rb filter --app-id com.example.app --url-pattern "api.example.com" --format csv

        # Filter by method and time
        ruby pulse_log_export.rb filter --app-id com.example.app --method POST --since "2024-01-01T00:00:00Z"

        # List installed apps
        ruby pulse_log_export.rb list-apps

      Options:
        --app-id          App bundle identifier (required)
        --simulator       Simulator UDID (auto-detect if not specified)
        --format          Export format: json, csv, text, html (default: json)
        --output          Output file path
        --status          Filter by status code or range (e.g., 200, 400-599)
        --url-pattern     Filter by URL pattern
        --method          Filter by HTTP method (GET, POST, etc.)
        --since           Filter requests since time (ISO8601)
        --until           Filter requests until time (ISO8601)
        -h, --help        Show this help
    HELP
  end
end

# Run CLI
CLI.run(ARGV) if __FILE__ == $PROGRAM_NAME
