#!/usr/bin/env ruby
# frozen_string_literal: true

require 'optparse'
require 'json'
require 'pathname'

# Huxley Simulator Control Tool
# Comprehensive iOS simulator enhancement capabilities for Mobile Dev agent
# Wraps simctl commands with convenience features
class SimulatorControl
  VERSION = '1.0.0'

  def initialize
    @options = {
      verbose: false,
      dry_run: false,
      json_output: false
    }
  end

  def run(args)
    command = args.shift

    case command
    # Network Commands
    when 'network-throttle'
      network_throttle_command(args)
    when 'network-reset'
      network_reset_command(args)

    # Location Commands
    when 'set-location'
      set_location_command(args)
    when 'simulate-route'
      simulate_route_command(args)
    when 'reset-location'
      reset_location_command(args)

    # Environment Commands
    when 'set-appearance'
      set_appearance_command(args)
    when 'set-text-size'
      set_text_size_command(args)
    when 'toggle-accessibility'
      toggle_accessibility_command(args)
    when 'reset-environment'
      reset_environment_command(args)

    # Quick Actions
    when 'send-push'
      send_push_command(args)
    when 'open-url'
      open_url_command(args)

    # User Defaults
    when 'read-defaults'
      read_defaults_command(args)
    when 'write-defaults'
      write_defaults_command(args)
    when 'delete-defaults'
      delete_defaults_command(args)

    # Simulator Management
    when 'list-simulators'
      list_simulators_command(args)
    when 'boot-simulator'
      boot_simulator_command(args)
    when 'shutdown-simulator'
      shutdown_simulator_command(args)
    when 'erase-simulator'
      erase_simulator_command(args)

    # Camera
    when 'set-camera'
      set_camera_command(args)

    # Status Bar
    when 'override-status-bar'
      override_status_bar_command(args)
    when 'clear-status-bar'
      clear_status_bar_command(args)

    # Utility
    when 'get-udid'
      get_udid_command(args)
    when 'version', '-v', '--version'
      puts "simulator_control v#{VERSION}"
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

  # ==================== Network Commands ====================

  def network_throttle_command(args)
    opts = parse_options(args, %i[simulator profile])

    udid = get_simulator_udid(opts[:simulator])
    profile = opts[:profile] || '3g'

    log "Throttling network to #{profile} profile for simulator #{opts[:simulator]}"

    # Network throttling via status bar override (simulates network indicator)
    case profile.downcase
    when '3g'
      data_network = '3g'
    when 'edge', '2g'
      data_network = 'edge'
    when 'lte', '4g'
      data_network = 'lte'
    when '5g'
      data_network = '5g'
    when 'wifi'
      data_network = 'wifi'
    when 'off', 'airplane'
      data_network = 'notSupported'
    else
      raise "Unknown network profile: #{profile}. Use: 3g, edge, lte, 5g, wifi, off"
    end

    unless @options[:dry_run]
      cmd = "xcrun simctl status_bar '#{udid}' override --dataNetwork #{data_network}"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to set network throttle: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Network throttled to #{profile}",
      simulator: opts[:simulator],
      profile: profile,
      note: "This only changes the status bar indicator. For true network throttling, use Network Link Conditioner (macOS System Preferences)."
    )
  end

  def network_reset_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    log "Resetting network status for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl status_bar '#{udid}' clear"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to reset network: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Network status reset to default",
      simulator: opts[:simulator]
    )
  end

  # ==================== Location Commands ====================

  def set_location_command(args)
    opts = parse_options(args, %i[simulator latitude longitude])

    udid = get_simulator_udid(opts[:simulator])
    lat = opts[:latitude]
    lon = opts[:longitude]

    log "Setting location to #{lat}, #{lon} for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl location '#{udid}' set #{lat} #{lon}"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to set location: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Location set successfully",
      simulator: opts[:simulator],
      latitude: lat,
      longitude: lon,
      location_name: get_location_name(lat, lon)
    )
  end

  def simulate_route_command(args)
    opts = parse_options(args, %i[simulator gpx_file])

    udid = get_simulator_udid(opts[:simulator])
    gpx_file = opts[:gpx_file]

    unless File.exist?(gpx_file)
      raise "GPX file not found: #{gpx_file}"
    end

    log "Simulating route from GPX file: #{gpx_file}"

    unless @options[:dry_run]
      cmd = "xcrun simctl location '#{udid}' load '#{gpx_file}'"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to load GPX route: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Route simulation started",
      simulator: opts[:simulator],
      gpx_file: gpx_file
    )
  end

  def reset_location_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    log "Resetting location for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl location '#{udid}' clear"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to reset location: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Location reset to default",
      simulator: opts[:simulator]
    )
  end

  # ==================== Environment Commands ====================

  def set_appearance_command(args)
    opts = parse_options(args, %i[simulator mode])

    udid = get_simulator_udid(opts[:simulator])
    mode = opts[:mode] || 'dark'

    unless %w[dark light].include?(mode.downcase)
      raise "Invalid appearance mode: #{mode}. Use 'dark' or 'light'"
    end

    log "Setting appearance to #{mode} mode for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl ui '#{udid}' appearance #{mode}"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to set appearance: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Appearance set to #{mode} mode",
      simulator: opts[:simulator],
      mode: mode
    )
  end

  def set_text_size_command(args)
    opts = parse_options(args, %i[simulator size])

    udid = get_simulator_udid(opts[:simulator])
    size = opts[:size] || 'L'

    # Dynamic Type size categories
    size_map = {
      'XS' => 'UICTContentSizeCategoryXS',
      'S' => 'UICTContentSizeCategoryS',
      'M' => 'UICTContentSizeCategoryM',
      'L' => 'UICTContentSizeCategoryL',
      'XL' => 'UICTContentSizeCategoryXL',
      'XXL' => 'UICTContentSizeCategoryXXL',
      'XXXL' => 'UICTContentSizeCategoryXXXL',
      'AccessibilityM' => 'UICTContentSizeCategoryAccessibilityM',
      'AccessibilityL' => 'UICTContentSizeCategoryAccessibilityL',
      'AccessibilityXL' => 'UICTContentSizeCategoryAccessibilityXL',
      'AccessibilityXXL' => 'UICTContentSizeCategoryAccessibilityXXL',
      'AccessibilityXXXL' => 'UICTContentSizeCategoryAccessibilityXXXL'
    }

    size_category = size_map[size]
    unless size_category
      raise "Invalid text size: #{size}. Use: #{size_map.keys.join(', ')}"
    end

    log "Setting text size to #{size} (#{size_category}) for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl spawn '#{udid}' notifyutil -s com.apple.UIContentSizeCategory #{size_category}"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to set text size: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Text size set to #{size}",
      simulator: opts[:simulator],
      size: size,
      category: size_category
    )
  end

  def toggle_accessibility_command(args)
    opts = parse_options(args, %i[simulator feature])

    udid = get_simulator_udid(opts[:simulator])
    feature = opts[:feature]
    enabled = opts[:enabled] == 'true' || opts[:enabled] == '1' || opts[:enabled].nil?

    # Accessibility features
    feature_map = {
      'bold_text' => { key: 'com.apple.accessibility.boldtext', value: enabled },
      'reduce_motion' => { key: 'com.apple.springboard.reduceMotion', value: enabled },
      'reduce_transparency' => { key: 'com.apple.accessibility.reduceTransparency', value: enabled },
      'increase_contrast' => { key: 'UIAccessibilityDarkerSystemColors', value: enabled },
      'button_shapes' => { key: 'com.apple.accessibility.buttonShapes', value: enabled },
      'on_off_labels' => { key: 'com.apple.accessibility.onOffLabels', value: enabled }
    }

    feature_config = feature_map[feature]
    unless feature_config
      raise "Unknown accessibility feature: #{feature}. Use: #{feature_map.keys.join(', ')}"
    end

    log "#{enabled ? 'Enabling' : 'Disabling'} #{feature} for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl spawn '#{udid}' defaults write -g #{feature_config[:key]} -bool #{feature_config[:value]}"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to toggle accessibility feature: #{output}"
      end
    end

    output_result(
      success: true,
      message: "#{enabled ? 'Enabled' : 'Disabled'} #{feature}",
      simulator: opts[:simulator],
      feature: feature,
      enabled: enabled
    )
  end

  def reset_environment_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    log "Resetting environment to defaults for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      # Clear status bar
      `xcrun simctl status_bar '#{udid}' clear 2>&1`

      # Reset appearance to light
      `xcrun simctl ui '#{udid}' appearance light 2>&1`

      # Reset text size to default (L)
      `xcrun simctl spawn '#{udid}' notifyutil -s com.apple.UIContentSizeCategory UICTContentSizeCategoryL 2>&1`
    end

    output_result(
      success: true,
      message: "Environment reset to defaults",
      simulator: opts[:simulator]
    )
  end

  # ==================== Quick Actions ====================

  def send_push_command(args)
    opts = parse_options(args, %i[simulator bundle_id])

    udid = get_simulator_udid(opts[:simulator])
    bundle_id = opts[:bundle_id]
    payload_file = opts[:payload] || create_default_push_payload

    unless File.exist?(payload_file)
      raise "Push notification payload file not found: #{payload_file}"
    end

    log "Sending push notification to #{bundle_id}"

    unless @options[:dry_run]
      cmd = "xcrun simctl push '#{udid}' '#{bundle_id}' '#{payload_file}'"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to send push notification: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Push notification sent",
      simulator: opts[:simulator],
      bundle_id: bundle_id,
      payload: payload_file
    )
  end

  def open_url_command(args)
    opts = parse_options(args, %i[simulator url])

    udid = get_simulator_udid(opts[:simulator])
    url = opts[:url]

    log "Opening URL: #{url}"

    unless @options[:dry_run]
      cmd = "xcrun simctl openurl '#{udid}' '#{url}'"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to open URL: #{output}"
      end
    end

    output_result(
      success: true,
      message: "URL opened in simulator",
      simulator: opts[:simulator],
      url: url
    )
  end

  # ==================== User Defaults Commands ====================

  def read_defaults_command(args)
    opts = parse_options(args, %i[simulator bundle_id])

    udid = get_simulator_udid(opts[:simulator])
    bundle_id = opts[:bundle_id]
    key = opts[:key]

    log "Reading UserDefaults for #{bundle_id}"

    if key
      cmd = "xcrun simctl spawn '#{udid}' defaults read '#{bundle_id}' '#{key}'"
    else
      cmd = "xcrun simctl spawn '#{udid}' defaults read '#{bundle_id}'"
    end

    output = `#{cmd} 2>&1`

    unless $?.success?
      raise "Failed to read UserDefaults: #{output}"
    end

    output_result(
      success: true,
      simulator: opts[:simulator],
      bundle_id: bundle_id,
      key: key,
      value: output.strip
    )
  end

  def write_defaults_command(args)
    opts = parse_options(args, %i[simulator bundle_id key value])

    udid = get_simulator_udid(opts[:simulator])
    bundle_id = opts[:bundle_id]
    key = opts[:key]
    value = opts[:value]
    type = opts[:type] || 'string'

    log "Writing UserDefaults: #{key} = #{value} (#{type})"

    unless @options[:dry_run]
      cmd = "xcrun simctl spawn '#{udid}' defaults write '#{bundle_id}' '#{key}' -#{type} '#{value}'"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to write UserDefaults: #{output}"
      end
    end

    output_result(
      success: true,
      message: "UserDefaults written",
      simulator: opts[:simulator],
      bundle_id: bundle_id,
      key: key,
      value: value,
      type: type
    )
  end

  def delete_defaults_command(args)
    opts = parse_options(args, %i[simulator bundle_id key])

    udid = get_simulator_udid(opts[:simulator])
    bundle_id = opts[:bundle_id]
    key = opts[:key]

    log "Deleting UserDefaults key: #{key}"

    unless @options[:dry_run]
      cmd = "xcrun simctl spawn '#{udid}' defaults delete '#{bundle_id}' '#{key}'"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to delete UserDefaults: #{output}"
      end
    end

    output_result(
      success: true,
      message: "UserDefaults key deleted",
      simulator: opts[:simulator],
      bundle_id: bundle_id,
      key: key
    )
  end

  # ==================== Simulator Management ====================

  def list_simulators_command(args)
    opts = parse_options(args, [])

    cmd = "xcrun simctl list devices available --json"
    output = `#{cmd} 2>&1`

    unless $?.success?
      raise "Failed to list simulators: #{output}"
    end

    data = JSON.parse(output)

    simulators = []
    data['devices'].each do |runtime, devices|
      devices.each do |device|
        simulators << {
          name: device['name'],
          udid: device['udid'],
          state: device['state'],
          runtime: runtime
        }
      end
    end

    output_result(
      total: simulators.count,
      simulators: simulators
    )
  end

  def boot_simulator_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    log "Booting simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl boot '#{udid}'"
      output = `#{cmd} 2>&1`

      # Booting already booted simulator is not an error
      unless $?.success? || output.include?('Unable to boot device in current state: Booted')
        raise "Failed to boot simulator: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Simulator booted",
      simulator: opts[:simulator],
      udid: udid
    )
  end

  def shutdown_simulator_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    log "Shutting down simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl shutdown '#{udid}'"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to shutdown simulator: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Simulator shut down",
      simulator: opts[:simulator]
    )
  end

  def erase_simulator_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    log "Erasing simulator #{opts[:simulator]} (all data will be deleted)"

    unless @options[:dry_run]
      cmd = "xcrun simctl erase '#{udid}'"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to erase simulator: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Simulator erased",
      simulator: opts[:simulator],
      warning: "All app data has been deleted"
    )
  end

  # ==================== Camera Commands ====================

  def set_camera_command(args)
    opts = parse_options(args, %i[simulator])

    # Camera setting is done via Simulator.app menu: I/O → Camera
    # There's no simctl command for this

    output_result(
      success: false,
      message: "Camera setting must be done via Simulator.app GUI",
      instructions: "Open Simulator.app → I/O → Camera → Select Mac webcam",
      simulator: opts[:simulator]
    )
  end

  # ==================== Status Bar Commands ====================

  def override_status_bar_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    # Status bar overrides
    time = opts[:time] || '9:41'
    battery = opts[:battery] || '100'
    wifi = opts[:wifi] || '3'
    cellular = opts[:cellular] || '4'

    log "Overriding status bar for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl status_bar '#{udid}' override " \
            "--time '#{time}' " \
            "--batteryLevel #{battery} " \
            "--wifiBars #{wifi} " \
            "--cellularBars #{cellular}"

      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to override status bar: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Status bar overridden",
      simulator: opts[:simulator],
      time: time,
      battery: battery,
      wifi_bars: wifi,
      cellular_bars: cellular
    )
  end

  def clear_status_bar_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    log "Clearing status bar overrides for simulator #{opts[:simulator]}"

    unless @options[:dry_run]
      cmd = "xcrun simctl status_bar '#{udid}' clear"
      output = `#{cmd} 2>&1`

      unless $?.success?
        raise "Failed to clear status bar: #{output}"
      end
    end

    output_result(
      success: true,
      message: "Status bar cleared",
      simulator: opts[:simulator]
    )
  end

  # ==================== Utility Commands ====================

  def get_udid_command(args)
    opts = parse_options(args, %i[simulator])

    udid = get_simulator_udid(opts[:simulator])

    output_result(
      simulator: opts[:simulator],
      udid: udid
    )
  end

  # ==================== Helper Methods ====================

  def get_simulator_udid(name_or_udid)
    # If already a UDID, return it
    return name_or_udid if name_or_udid =~ /^[A-F0-9-]{36}$/i

    # Otherwise, look up by name
    cmd = "xcrun simctl list devices available --json"
    output = `#{cmd} 2>&1`

    unless $?.success?
      raise "Failed to list simulators: #{output}"
    end

    data = JSON.parse(output)

    # Search for simulator by name
    data['devices'].each do |runtime, devices|
      devices.each do |device|
        return device['udid'] if device['name'] == name_or_udid
      end
    end

    raise "Simulator not found: #{name_or_udid}"
  end

  def get_location_name(lat, lon)
    # Famous locations for reference
    locations = {
      [37.7749, -122.4194] => 'San Francisco, CA',
      [40.7128, -74.0060] => 'New York, NY',
      [51.5074, -0.1278] => 'London, UK',
      [35.6762, 139.6503] => 'Tokyo, Japan',
      [48.8566, 2.3522] => 'Paris, France',
      [37.3861, -122.0839] => 'Apple Park, Cupertino'
    }

    # Find closest match
    closest = locations.keys.min_by do |coords|
      Math.sqrt((coords[0] - lat.to_f)**2 + (coords[1] - lon.to_f)**2)
    end

    distance = Math.sqrt((closest[0] - lat.to_f)**2 + (closest[1] - lon.to_f)**2)

    if distance < 0.1
      locations[closest]
    else
      "Custom location"
    end
  end

  def create_default_push_payload
    payload = {
      "aps" => {
        "alert" => {
          "title" => "Test Notification",
          "body" => "This is a test push notification from Huxley"
        },
        "badge" => 1,
        "sound" => "default"
      }
    }

    temp_file = "/tmp/push_notification_payload.json"
    File.write(temp_file, JSON.pretty_generate(payload))

    temp_file
  end

  def parse_options(args, required_keys)
    opts = {}

    parser = OptionParser.new do |p|
      # Common options
      p.on('--simulator NAME_OR_UDID', 'Simulator name or UDID') { |v| opts[:simulator] = v }

      # Network options
      p.on('--profile PROFILE', 'Network profile (3g, edge, lte, 5g, wifi, off)') { |v| opts[:profile] = v }

      # Location options
      p.on('--latitude LAT', 'Latitude coordinate') { |v| opts[:latitude] = v }
      p.on('--longitude LON', 'Longitude coordinate') { |v| opts[:longitude] = v }
      p.on('--gpx-file PATH', 'GPX route file') { |v| opts[:gpx_file] = v }

      # Environment options
      p.on('--mode MODE', 'Appearance mode (dark/light)') { |v| opts[:mode] = v }
      p.on('--size SIZE', 'Text size (XS, S, M, L, XL, XXL, XXXL, AccessibilityM/L/XL/XXL/XXXL)') { |v| opts[:size] = v }
      p.on('--feature FEATURE', 'Accessibility feature') { |v| opts[:feature] = v }
      p.on('--enabled BOOL', 'Enable/disable feature (true/false)') { |v| opts[:enabled] = v }

      # Quick Actions
      p.on('--bundle-id ID', 'App bundle identifier') { |v| opts[:bundle_id] = v }
      p.on('--payload PATH', 'Push notification payload JSON file') { |v| opts[:payload] = v }
      p.on('--url URL', 'URL to open') { |v| opts[:url] = v }

      # User Defaults
      p.on('--key KEY', 'UserDefaults key') { |v| opts[:key] = v }
      p.on('--value VALUE', 'UserDefaults value') { |v| opts[:value] = v }
      p.on('--type TYPE', 'UserDefaults value type (string, bool, int, float)') { |v| opts[:type] = v }

      # Status Bar
      p.on('--time TIME', 'Status bar time (default: 9:41)') { |v| opts[:time] = v }
      p.on('--battery LEVEL', 'Battery level 0-100 (default: 100)') { |v| opts[:battery] = v }
      p.on('--wifi BARS', 'WiFi bars 0-3 (default: 3)') { |v| opts[:wifi] = v }
      p.on('--cellular BARS', 'Cellular bars 0-4 (default: 4)') { |v| opts[:cellular] = v }

      # Global options
      p.on('--verbose', 'Verbose output') { @options[:verbose] = true }
      p.on('--dry-run', 'Preview changes without executing') { @options[:dry_run] = true }
      p.on('--json', 'JSON output') { @options[:json_output] = true }
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

    prefix = @options[:dry_run] ? '[DRY RUN] ' : ''
    puts "#{prefix}#{message}" if @options[:verbose] || @options[:dry_run]
  end

  def output_result(data)
    if @options[:json_output]
      puts JSON.pretty_generate(data)
    else
      data.each do |key, value|
        if value.is_a?(Array)
          puts "#{key}: (#{value.count} items)"
          value.each { |item| puts "  - #{item.is_a?(Hash) ? item.inspect : item}" }
        elsif value.is_a?(Hash)
          puts "#{key}:"
          value.each { |k, v| puts "  #{k}: #{v}" }
        else
          puts "#{key}: #{value}"
        end
      end
    end
  end

  def show_help
    puts <<~HELP
      Huxley Simulator Control v#{VERSION}
      Comprehensive iOS simulator enhancement tool for Mobile Dev agent

      USAGE:
        simulator_control.rb COMMAND [OPTIONS]

      NETWORK COMMANDS:
        network-throttle       Simulate network conditions (3G, Edge, LTE, etc.)
        network-reset          Reset network to default

      LOCATION COMMANDS:
        set-location           Set GPS coordinates
        simulate-route         Play GPX route file
        reset-location         Clear location override

      ENVIRONMENT COMMANDS:
        set-appearance         Switch Dark/Light mode
        set-text-size          Adjust Dynamic Type size
        toggle-accessibility   Enable accessibility features
        reset-environment      Reset all environment overrides

      QUICK ACTIONS:
        send-push             Send push notification
        open-url              Open URL or deep link

      USER DEFAULTS:
        read-defaults         Read app preferences
        write-defaults        Write app preferences
        delete-defaults       Delete preference key

      SIMULATOR MANAGEMENT:
        list-simulators       List all available simulators
        boot-simulator        Boot a simulator
        shutdown-simulator    Shut down a simulator
        erase-simulator       Erase simulator (delete all data)

      CAMERA:
        set-camera            Instructions for camera setup

      STATUS BAR:
        override-status-bar   Set status bar appearance
        clear-status-bar      Reset status bar to default

      UTILITY:
        get-udid              Get simulator UDID from name
        version               Show version
        help                  Show this help

      GLOBAL OPTIONS:
        --verbose             Verbose output
        --dry-run             Preview changes without executing
        --json                JSON output format

      EXAMPLES:
        # Throttle network to 3G
        simulator_control.rb network-throttle \\
          --simulator "iPhone 16" \\
          --profile 3g

        # Set location to San Francisco
        simulator_control.rb set-location \\
          --simulator "iPhone 16" \\
          --latitude 37.7749 \\
          --longitude -122.4194

        # Enable Dark Mode
        simulator_control.rb set-appearance \\
          --simulator "iPhone 16" \\
          --mode dark

        # Set largest accessibility text size
        simulator_control.rb set-text-size \\
          --simulator "iPhone 16" \\
          --size AccessibilityXXXL

        # Send push notification
        simulator_control.rb send-push \\
          --simulator "iPhone 16" \\
          --bundle-id com.example.MyApp \\
          --payload notification.json

        # Open deep link
        simulator_control.rb open-url \\
          --simulator "iPhone 16" \\
          --url "myapp://settings/account"

        # Write UserDefaults
        simulator_control.rb write-defaults \\
          --simulator "iPhone 16" \\
          --bundle-id com.example.MyApp \\
          --key isDarkModeEnabled \\
          --value true \\
          --type bool

        # List all simulators
        simulator_control.rb list-simulators --json

        # Boot simulator
        simulator_control.rb boot-simulator \\
          --simulator "iPhone 16"

        # Override status bar (perfect for screenshots)
        simulator_control.rb override-status-bar \\
          --simulator "iPhone 16" \\
          --time "9:41" \\
          --battery 100 \\
          --wifi 3 \\
          --cellular 4
    HELP
  end
end

# Run the tool
if __FILE__ == $0
  tool = SimulatorControl.new
  tool.run(ARGV)
end
