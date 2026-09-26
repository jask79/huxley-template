#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'fileutils'

# Device Bezel Tool for Professional iOS Screenshots
#
# Purpose: Add device bezels (frames) around simulator screenshots
# Use case: Professional marketing materials and presentations
#
# Requirements:
# - ImageMagick (brew install imagemagick)
# - Active iOS Simulator (optional)
#
# Usage:
#   ruby device_bezel.rb frame --file screenshot.png --device "iPhone 16 Pro"
#   ruby device_bezel.rb frame --simulator "iPhone 16" --device "iPhone 16" --background white
#   ruby device_bezel.rb list-devices

class DeviceBezel
  DEVICE_SPECS = {
    'iPhone 16 Pro Max' => {
      screen_width: 1320,
      screen_height: 2868,
      bezel_top: 60,
      bezel_bottom: 60,
      bezel_sides: 20,
      corner_radius: 55,
      notch: true,
      notch_width: 400,
      notch_height: 37
    },
    'iPhone 16 Pro' => {
      screen_width: 1206,
      screen_height: 2622,
      bezel_top: 55,
      bezel_bottom: 55,
      bezel_sides: 18,
      corner_radius: 50,
      notch: true,
      notch_width: 380,
      notch_height: 37
    },
    'iPhone 16' => {
      screen_width: 1179,
      screen_height: 2556,
      bezel_top: 50,
      bezel_bottom: 50,
      bezel_sides: 15,
      corner_radius: 47,
      notch: true,
      notch_width: 340,
      notch_height: 35
    },
    'iPhone SE' => {
      screen_width: 750,
      screen_height: 1334,
      bezel_top: 120,
      bezel_bottom: 120,
      bezel_sides: 20,
      corner_radius: 20,
      notch: false,
      home_button: true
    },
    'iPad Pro 13' => {
      screen_width: 2064,
      screen_height: 2752,
      bezel_top: 40,
      bezel_bottom: 40,
      bezel_sides: 40,
      corner_radius: 30,
      notch: false
    },
    'iPad Pro 11' => {
      screen_width: 1668,
      screen_height: 2388,
      bezel_top: 35,
      bezel_bottom: 35,
      bezel_sides: 35,
      corner_radius: 28,
      notch: false
    }
  }.freeze

  BACKGROUND_PRESETS = {
    'white' => '#FFFFFF',
    'black' => '#000000',
    'light-gray' => '#F5F5F5',
    'dark-gray' => '#1C1C1E',
    'gradient-blue' => 'gradient:blue',
    'gradient-purple' => 'gradient:purple',
    'transparent' => 'none'
  }.freeze

  def initialize
    check_dependencies
  end

  def frame(options)
    input_file = if options[:file]
                   validate_input_file(options[:file])
                 elsif options[:simulator]
                   capture_simulator_screenshot(options[:simulator])
                 else
                   capture_default_simulator
                 end

    unless options[:device]
      abort "❌ Missing device type. Use --device (e.g., 'iPhone 16 Pro')"
    end

    device_specs = DEVICE_SPECS[options[:device]]
    unless device_specs
      abort "❌ Unknown device: #{options[:device]}\nRun 'device_bezel.rb list-devices' for available devices"
    end

    background = BACKGROUND_PRESETS[options[:background]] || options[:background] || 'white'
    output_file = options[:output] || generate_output_path(input_file, options[:device])

    puts "📱 Adding #{options[:device]} bezel..."

    # Resize screenshot to match device screen if needed
    resized_screenshot = resize_screenshot(input_file, device_specs[:screen_width], device_specs[:screen_height])

    # Create device frame
    create_device_frame(resized_screenshot, output_file, device_specs, background, options)

    puts "✅ Device frame added: #{output_file}"
    puts "   Device: #{options[:device]}"
    puts "   Background: #{options[:background] || 'white'}"

    output_file
  end

  def list_devices
    puts "\n📱 Available Devices:\n\n"
    DEVICE_SPECS.keys.sort.each do |device|
      specs = DEVICE_SPECS[device]
      features = []
      features << 'Dynamic Island' if specs[:notch]
      features << 'Home Button' if specs[:home_button]
      feature_str = features.empty? ? '' : " (#{features.join(', ')})"

      puts "  #{device}#{feature_str}"
      puts "    Resolution: #{specs[:screen_width]}×#{specs[:screen_height]}"
    end

    puts "\n🎨 Background Presets:\n\n"
    BACKGROUND_PRESETS.each do |name, value|
      puts "  #{name.ljust(20)} - #{value}"
    end
    puts ""
  end

  private

  def check_dependencies
    unless system('which convert > /dev/null 2>&1')
      abort "❌ ImageMagick not found. Install with: brew install imagemagick"
    end

    unless system('which xcrun > /dev/null 2>&1')
      abort "❌ Xcode Command Line Tools not found. Install with: xcode-select --install"
    end
  end

  def validate_input_file(file_path)
    expanded_path = File.expand_path(file_path)
    unless File.exist?(expanded_path)
      abort "❌ Input file not found: #{expanded_path}"
    end
    expanded_path
  end

  def capture_simulator_screenshot(simulator_name)
    list_output = `xcrun simctl list devices available -j`
    devices = JSON.parse(list_output)['devices']

    device_udid = nil
    devices.each do |runtime, device_list|
      device = device_list.find { |d| d['name'] == simulator_name && d['state'] == 'Booted' }
      if device
        device_udid = device['udid']
        break
      end
    end

    unless device_udid
      abort "❌ Simulator '#{simulator_name}' not found or not booted."
    end

    temp_screenshot = "/tmp/device_bezel_#{Time.now.to_i}.png"
    result = system("xcrun simctl io #{device_udid} screenshot #{temp_screenshot}")

    unless result
      abort "❌ Failed to capture screenshot"
    end

    temp_screenshot
  end

  def capture_default_simulator
    list_output = `xcrun simctl list devices available -j`
    devices = JSON.parse(list_output)['devices']

    booted_device = nil
    devices.each do |runtime, device_list|
      device = device_list.find { |d| d['state'] == 'Booted' }
      if device
        booted_device = device
        break
      end
    end

    unless booted_device
      abort "❌ No booted simulator found."
    end

    temp_screenshot = "/tmp/device_bezel_#{Time.now.to_i}.png"
    result = system("xcrun simctl io #{booted_device['udid']} screenshot #{temp_screenshot}")

    unless result
      abort "❌ Failed to capture screenshot"
    end

    temp_screenshot
  end

  def generate_output_path(input_file, device_name)
    dir = File.dirname(input_file)
    basename = File.basename(input_file, '.*')
    ext = File.extname(input_file)
    device_slug = device_name.downcase.gsub(/\s+/, '_')
    timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
    "#{dir}/#{basename}_#{device_slug}_#{timestamp}#{ext}"
  end

  def resize_screenshot(input_file, target_width, target_height)
    # Get current dimensions
    identify_output = `convert #{input_file} -format "%wx%h" info:`
    current_width, current_height = identify_output.strip.split('x').map(&:to_i)

    # Only resize if dimensions don't match
    if current_width != target_width || current_height != target_height
      puts "   Resizing screenshot: #{current_width}×#{current_height} → #{target_width}×#{target_height}"

      resized_file = "/tmp/resized_#{Time.now.to_i}.png"
      command = "convert #{input_file} -resize #{target_width}x#{target_height}! #{resized_file}"
      result = system(command)

      unless result
        abort "❌ Failed to resize screenshot"
      end

      resized_file
    else
      input_file
    end
  end

  def create_device_frame(screenshot, output_file, specs, background, options)
    # Calculate total dimensions with bezels
    total_width = specs[:screen_width] + (specs[:bezel_sides] * 2)
    total_height = specs[:screen_height] + specs[:bezel_top] + specs[:bezel_bottom]

    # Add padding if requested
    padding = options[:padding] || 50
    canvas_width = total_width + (padding * 2)
    canvas_height = total_height + (padding * 2)

    # Create background
    if background.start_with?('gradient:')
      gradient_type = background.split(':')[1]
      create_gradient_background(canvas_width, canvas_height, gradient_type, output_file)
    elsif background == 'none'
      # Transparent background
      command = "convert -size #{canvas_width}x#{canvas_height} xc:none #{output_file}"
      system(command)
    else
      # Solid color background
      command = "convert -size #{canvas_width}x#{canvas_height} xc:#{background} #{output_file}"
      system(command)
    end

    # Create device bezel shape
    bezel_file = create_bezel_shape(specs, total_width, total_height)

    # Composite screenshot onto bezel
    temp_with_screenshot = "/tmp/with_screenshot_#{Time.now.to_i}.png"
    command = [
      "convert #{bezel_file}",
      screenshot,
      "-geometry +#{specs[:bezel_sides]}+#{specs[:bezel_top]}",
      "-composite",
      temp_with_screenshot
    ].join(' ')
    system(command)

    # Add Dynamic Island/notch if applicable
    if specs[:notch]
      add_dynamic_island(temp_with_screenshot, specs)
    end

    # Add home button if applicable
    if specs[:home_button]
      add_home_button(temp_with_screenshot, specs, total_width, total_height)
    end

    # Composite device onto background
    command = [
      "convert #{output_file}",
      temp_with_screenshot,
      "-gravity center",
      "-composite",
      output_file
    ].join(' ')
    system(command)

    # Add shadow if requested
    if options[:shadow]
      add_drop_shadow(output_file)
    end

    # Clean up temp files
    FileUtils.rm_f(bezel_file)
    FileUtils.rm_f(temp_with_screenshot)
  end

  def create_bezel_shape(specs, width, height)
    bezel_file = "/tmp/bezel_#{Time.now.to_i}.png"

    # Create rounded rectangle for bezel
    command = [
      "convert",
      "-size #{width}x#{height}",
      "xc:none",
      "-fill '#1C1C1E'",
      "-draw \"roundrectangle 0,0 #{width},#{height} #{specs[:corner_radius]},#{specs[:corner_radius]}\"",
      bezel_file
    ].join(' ')

    result = system(command)
    unless result
      abort "❌ Failed to create bezel shape"
    end

    bezel_file
  end

  def add_dynamic_island(image_file, specs)
    # Add black pill shape at top center (Dynamic Island)
    island_width = specs[:notch_width]
    island_height = specs[:notch_height]
    island_x = (specs[:screen_width] - island_width) / 2 + specs[:bezel_sides]
    island_y = specs[:bezel_top] + 20

    command = [
      "convert #{image_file}",
      "-fill black",
      "-draw \"roundrectangle #{island_x},#{island_y} #{island_x + island_width},#{island_y + island_height} 18,18\"",
      image_file
    ].join(' ')

    system(command)
  end

  def add_home_button(image_file, specs, width, height)
    # Add circular home button at bottom center
    button_radius = 30
    button_x = width / 2
    button_y = height - specs[:bezel_bottom] / 2

    command = [
      "convert #{image_file}",
      "-fill '#333333'",
      "-draw \"circle #{button_x},#{button_y} #{button_x + button_radius},#{button_y}\"",
      "-fill '#555555'",
      "-draw \"circle #{button_x},#{button_y} #{button_x + button_radius - 5},#{button_y}\"",
      image_file
    ].join(' ')

    system(command)
  end

  def create_gradient_background(width, height, gradient_type, output_file)
    case gradient_type
    when 'blue'
      command = "convert -size #{width}x#{height} gradient:'#4A90E2'-'#1E3A8A' #{output_file}"
    when 'purple'
      command = "convert -size #{width}x#{height} gradient:'#9333EA'-'#4C1D95' #{output_file}"
    when 'pink'
      command = "convert -size #{width}x#{height} gradient:'#EC4899'-'#9F1239' #{output_file}"
    when 'green'
      command = "convert -size #{width}x#{height} gradient:'#10B981'-'#064E3B' #{output_file}"
    else
      command = "convert -size #{width}x#{height} gradient:'#6B7280'-'#1F2937' #{output_file}"
    end

    system(command)
  end

  def add_drop_shadow(image_file)
    # Add subtle drop shadow
    command = [
      "convert #{image_file}",
      "\\( +clone -background black -shadow 60x20+0+10 \\)",
      "+swap -background none -layers merge +repage",
      image_file
    ].join(' ')

    system(command)
  end
end

# CLI Interface
def main
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: device_bezel.rb [command] [options]"
    opts.separator ""
    opts.separator "Commands:"
    opts.separator "  frame          Add device bezel to screenshot"
    opts.separator "  list-devices   List available devices and backgrounds"
    opts.separator ""
    opts.separator "Options:"

    opts.on('-s', '--simulator NAME', 'Simulator name (e.g., "iPhone 16")') do |v|
      options[:simulator] = v
    end

    opts.on('-f', '--file PATH', 'Use existing screenshot file') do |v|
      options[:file] = v
    end

    opts.on('-d', '--device DEVICE', 'Device type (e.g., "iPhone 16 Pro")') do |v|
      options[:device] = v
    end

    opts.on('-b', '--background BG', 'Background (white, black, gradient-blue, or hex color)') do |v|
      options[:background] = v
    end

    opts.on('-p', '--padding PX', Integer, 'Padding around device (default: 50px)') do |v|
      options[:padding] = v
    end

    opts.on('--shadow', 'Add drop shadow to device') do
      options[:shadow] = true
    end

    opts.on('-o', '--output PATH', 'Output file path') do |v|
      options[:output] = File.expand_path(v)
    end

    opts.on('-h', '--help', 'Show this help message') do
      puts opts
      exit
    end
  end.parse!

  command = ARGV[0]

  case command
  when 'frame'
    tool = DeviceBezel.new
    tool.frame(options)
  when 'list-devices', 'list'
    tool = DeviceBezel.new
    tool.list_devices
  else
    puts "❌ Unknown command: #{command}"
    puts "Usage: device_bezel.rb [frame|list-devices] [options]"
    puts "Run 'device_bezel.rb --help' for more information"
    exit 1
  end
end

main if __FILE__ == $PROGRAM_NAME
