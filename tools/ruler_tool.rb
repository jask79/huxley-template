#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'fileutils'

# Ruler Tool for iOS Simulator Design Validation
#
# Purpose: Measure spacing and distances on simulator screenshots
# Use case: UI Designer verifies precise spacing between elements
#
# Requirements:
# - ImageMagick (brew install imagemagick)
# - Active iOS Simulator (optional)
#
# Usage:
#   ruby ruler_tool.rb measure --file screenshot.png --from 100,200 --to 300,400
#   ruby ruler_tool.rb measure --simulator "iPhone 16" --from 100,200 --to 300,400 --annotate
#   ruby ruler_tool.rb interactive --file screenshot.png

class RulerTool
  RULER_COLOR = 'rgba(255,0,255,0.8)'.freeze
  TEXT_COLOR = 'white'.freeze
  ARROW_COLOR = 'rgba(255,0,255,1.0)'.freeze

  def initialize
    check_dependencies
  end

  def measure(options)
    input_file = if options[:file]
                   validate_input_file(options[:file])
                 elsif options[:simulator]
                   capture_simulator_screenshot(options[:simulator])
                 else
                   capture_default_simulator
                 end

    unless options[:from] && options[:to]
      abort "❌ Missing coordinates. Use --from x1,y1 --to x2,y2"
    end

    from_x, from_y = parse_coordinates(options[:from])
    to_x, to_y = parse_coordinates(options[:to])

    puts "📏 Measuring distance..."
    puts "   From: (#{from_x}, #{from_y})"
    puts "   To: (#{to_x}, #{to_y})"

    # Calculate distances
    horizontal = (to_x - from_x).abs
    vertical = (to_y - from_y).abs
    diagonal = Math.sqrt(horizontal**2 + vertical**2).round(2)

    puts "\n📐 Results:"
    puts "   Horizontal: #{horizontal}pt"
    puts "   Vertical: #{vertical}pt"
    puts "   Diagonal: #{diagonal}pt"

    # Check grid compliance
    check_grid_compliance(horizontal, vertical)

    # Annotate image if requested
    if options[:annotate]
      output_file = options[:output] || generate_output_path(input_file)
      annotate_measurement(input_file, output_file, from_x, from_y, to_x, to_y, horizontal, vertical, diagonal)
      puts "\n✅ Annotated image saved: #{output_file}"
    end

    {
      horizontal: horizontal,
      vertical: vertical,
      diagonal: diagonal,
      from: { x: from_x, y: from_y },
      to: { x: to_x, y: to_y }
    }
  end

  def interactive(options)
    input_file = if options[:file]
                   validate_input_file(options[:file])
                 elsif options[:simulator]
                   capture_simulator_screenshot(options[:simulator])
                 else
                   capture_default_simulator
                 end

    puts "\n📏 Interactive Ruler Mode"
    puts "   Image: #{File.basename(input_file)}"
    puts "\nInstructions:"
    puts "  1. Enter coordinates in format: x1,y1 x2,y2"
    puts "  2. Or use presets: 'top-margin', 'button-height', etc."
    puts "  3. Type 'help' for preset list"
    puts "  4. Type 'quit' to exit"
    puts ""

    # Get image dimensions for validation
    identify_output = `convert #{input_file} -format "%wx%h" info:`
    width, height = identify_output.strip.split('x').map(&:to_i)

    loop do
      print "\n> "
      input = gets.chomp.strip

      case input.downcase
      when 'quit', 'exit', 'q'
        puts "👋 Goodbye!"
        break
      when 'help', 'h'
        show_presets
      else
        process_interactive_command(input, input_file, width, height)
      end
    end
  end

  def batch_measure(options)
    unless options[:file] && options[:measurements]
      abort "❌ Batch mode requires --file and --measurements (JSON file)"
    end

    input_file = validate_input_file(options[:file])
    measurements_file = validate_input_file(options[:measurements])

    measurements = JSON.parse(File.read(measurements_file))

    puts "📏 Batch measuring #{measurements.length} measurements..."

    results = measurements.map.with_index do |measurement, index|
      from_x, from_y = measurement['from']['x'], measurement['from']['y']
      to_x, to_y = measurement['to']['x'], measurement['to']['y']
      label = measurement['label'] || "Measurement #{index + 1}"

      horizontal = (to_x - from_x).abs
      vertical = (to_y - from_y).abs
      diagonal = Math.sqrt(horizontal**2 + vertical**2).round(2)

      puts "\n#{label}:"
      puts "  Horizontal: #{horizontal}pt"
      puts "  Vertical: #{vertical}pt"

      {
        label: label,
        horizontal: horizontal,
        vertical: vertical,
        diagonal: diagonal,
        from: { x: from_x, y: from_y },
        to: { x: to_x, y: to_y }
      }
    end

    # Save results
    if options[:output]
      output_file = options[:output]
      File.write(output_file, JSON.pretty_generate(results))
      puts "\n✅ Results saved: #{output_file}"
    end

    # Generate annotated image
    if options[:annotate]
      annotated_file = generate_output_path(input_file)
      batch_annotate(input_file, annotated_file, measurements)
      puts "✅ Annotated image saved: #{annotated_file}"
    end

    results
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
    puts "📸 Capturing screenshot from #{simulator_name}..."

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

    temp_screenshot = "/tmp/ruler_tool_#{Time.now.to_i}.png"
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

    temp_screenshot = "/tmp/ruler_tool_#{Time.now.to_i}.png"
    result = system("xcrun simctl io #{booted_device['udid']} screenshot #{temp_screenshot}")

    unless result
      abort "❌ Failed to capture screenshot"
    end

    temp_screenshot
  end

  def parse_coordinates(coord_string)
    coords = coord_string.split(',').map(&:to_i)
    unless coords.length == 2
      abort "❌ Invalid coordinates format. Use: x,y (e.g., 100,200)"
    end
    coords
  end

  def generate_output_path(input_file)
    dir = File.dirname(input_file)
    basename = File.basename(input_file, '.*')
    ext = File.extname(input_file)
    timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
    "#{dir}/#{basename}_measured_#{timestamp}#{ext}"
  end

  def check_grid_compliance(horizontal, vertical)
    puts "\n✅ Grid Compliance:"

    # Check 4px grid
    h_mod_4 = horizontal % 4
    v_mod_4 = vertical % 4
    puts "   4px grid: #{h_mod_4 == 0 && v_mod_4 == 0 ? '✅' : '⚠️'} (H: #{h_mod_4 == 0 ? '✅' : "❌ +#{h_mod_4}pt"}, V: #{v_mod_4 == 0 ? '✅' : "❌ +#{v_mod_4}pt"})"

    # Check 8px grid
    h_mod_8 = horizontal % 8
    v_mod_8 = vertical % 8
    puts "   8px grid: #{h_mod_8 == 0 && v_mod_8 == 0 ? '✅' : '⚠️'} (H: #{h_mod_8 == 0 ? '✅' : "❌ +#{h_mod_8}pt"}, V: #{v_mod_8 == 0 ? '✅' : "❌ +#{v_mod_8}pt"})"

    # Common iOS spacing values
    common_spacing = [4, 8, 12, 16, 20, 24, 32, 44, 48, 64]
    if common_spacing.include?(horizontal) || common_spacing.include?(vertical)
      puts "   ✨ Uses standard iOS spacing"
    end
  end

  def annotate_measurement(input_file, output_file, from_x, from_y, to_x, to_y, horizontal, vertical, diagonal)
    # Draw line with arrows
    mid_x = (from_x + to_x) / 2
    mid_y = (from_y + to_y) / 2

    command = [
      "convert #{input_file}",
      # Draw main line
      "-strokewidth 2 -stroke '#{RULER_COLOR}' -draw \"line #{from_x},#{from_y} #{to_x},#{to_y}\"",
      # Draw start point
      "-fill '#{ARROW_COLOR}' -draw \"circle #{from_x},#{from_y} #{from_x + 5},#{from_y + 5}\"",
      # Draw end point
      "-fill '#{ARROW_COLOR}' -draw \"circle #{to_x},#{to_y} #{to_x + 5},#{to_y + 5}\"",
      # Add measurement text
      "-gravity Center",
      "-pointsize 20",
      "-fill '#{TEXT_COLOR}'",
      "-stroke black -strokewidth 3",
      "-annotate +0+#{mid_y - from_y - 30} 'H: #{horizontal}pt  V: #{vertical}pt'",
      output_file
    ].join(' ')

    result = system(command)

    unless result
      abort "❌ Failed to annotate image"
    end
  end

  def batch_annotate(input_file, output_file, measurements)
    FileUtils.cp(input_file, output_file)

    measurements.each_with_index do |measurement, index|
      from_x = measurement['from']['x']
      from_y = measurement['from']['y']
      to_x = measurement['to']['x']
      to_y = measurement['to']['y']
      label = measurement['label'] || "M#{index + 1}"

      horizontal = (to_x - from_x).abs
      vertical = (to_y - from_y).abs

      mid_x = (from_x + to_x) / 2
      mid_y = (from_y + to_y) / 2

      command = [
        "convert #{output_file}",
        "-strokewidth 2 -stroke '#{RULER_COLOR}' -draw \"line #{from_x},#{from_y} #{to_x},#{to_y}\"",
        "-fill '#{ARROW_COLOR}' -draw \"circle #{from_x},#{from_y} #{from_x + 5},#{from_y + 5}\"",
        "-fill '#{ARROW_COLOR}' -draw \"circle #{to_x},#{to_y} #{to_x + 5},#{to_y + 5}\"",
        "-pointsize 16 -fill '#{TEXT_COLOR}' -stroke black -strokewidth 2",
        "-annotate +#{mid_x}+#{mid_y - 20} '#{label}: #{horizontal}×#{vertical}pt'",
        output_file
      ].join(' ')

      system(command)
    end
  end

  def show_presets
    puts "\n📏 Measurement Presets:\n\n"
    puts "Touch Targets:"
    puts "  ios-button      - 44pt minimum (iOS requirement)"
    puts "  web-button      - 48px minimum (web requirement)"
    puts ""
    puts "Spacing:"
    puts "  micro           - 4pt"
    puts "  small           - 8pt"
    puts "  medium          - 16pt"
    puts "  large           - 24pt"
    puts "  xlarge          - 32pt"
    puts ""
    puts "Status Bar:"
    puts "  statusbar       - 44pt (standard iPhone)"
    puts "  statusbar-pro   - 54pt (iPhone with Dynamic Island)"
  end

  def process_interactive_command(input, image_file, width, height)
    parts = input.split
    if parts.length == 2
      # Format: x1,y1 x2,y2
      from_x, from_y = parse_coordinates(parts[0])
      to_x, to_y = parse_coordinates(parts[1])

      horizontal = (to_x - from_x).abs
      vertical = (to_y - from_y).abs
      diagonal = Math.sqrt(horizontal**2 + vertical**2).round(2)

      puts "\n📐 Measurement:"
      puts "   Horizontal: #{horizontal}pt"
      puts "   Vertical: #{vertical}pt"
      puts "   Diagonal: #{diagonal}pt"
      check_grid_compliance(horizontal, vertical)
    else
      puts "❌ Invalid format. Use: x1,y1 x2,y2 (e.g., 100,200 300,400)"
    end
  rescue StandardError => e
    puts "❌ Error: #{e.message}"
  end
end

# CLI Interface
def main
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: ruler_tool.rb [command] [options]"
    opts.separator ""
    opts.separator "Commands:"
    opts.separator "  measure       Measure distance between two points"
    opts.separator "  interactive   Interactive measurement mode"
    opts.separator "  batch         Batch measure from JSON file"
    opts.separator ""
    opts.separator "Options:"

    opts.on('-s', '--simulator NAME', 'Simulator name (e.g., "iPhone 16")') do |v|
      options[:simulator] = v
    end

    opts.on('-f', '--file PATH', 'Use existing screenshot file') do |v|
      options[:file] = v
    end

    opts.on('--from X,Y', 'Starting coordinates (e.g., 100,200)') do |v|
      options[:from] = v
    end

    opts.on('--to X,Y', 'Ending coordinates (e.g., 300,400)') do |v|
      options[:to] = v
    end

    opts.on('-m', '--measurements PATH', 'JSON file with batch measurements') do |v|
      options[:measurements] = v
    end

    opts.on('-o', '--output PATH', 'Output file path') do |v|
      options[:output] = File.expand_path(v)
    end

    opts.on('-a', '--annotate', 'Save annotated image with measurement overlay') do
      options[:annotate] = true
    end

    opts.on('-h', '--help', 'Show this help message') do
      puts opts
      exit
    end
  end.parse!

  command = ARGV[0]

  case command
  when 'measure'
    tool = RulerTool.new
    tool.measure(options)
  when 'interactive'
    tool = RulerTool.new
    tool.interactive(options)
  when 'batch'
    tool = RulerTool.new
    tool.batch_measure(options)
  else
    puts "❌ Unknown command: #{command}"
    puts "Usage: ruler_tool.rb [measure|interactive|batch] [options]"
    puts "Run 'ruler_tool.rb --help' for more information"
    exit 1
  end
end

main if __FILE__ == $PROGRAM_NAME
