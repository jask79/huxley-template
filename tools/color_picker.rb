#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'fileutils'

# Color Picker Tool for iOS Simulator Design Validation
#
# Purpose: Extract and verify colors from simulator screenshots
# Use case: UI Designer confirms design system color compliance
#
# Requirements:
# - ImageMagick (brew install imagemagick)
# - Active iOS Simulator (optional)
#
# Usage:
#   ruby color_picker.rb pick --file screenshot.png --at 100,200
#   ruby color_picker.rb pick --simulator "iPhone 16" --at 100,200 --format swift
#   ruby color_picker.rb verify --file screenshot.png --at 100,200 --design-system Colors.swift
#   ruby color_picker.rb batch --file screenshot.png --points points.json

class ColorPicker
  OUTPUT_FORMATS = %w[hex rgb rgba swift uicolor nscolor css].freeze

  def initialize
    check_dependencies
  end

  def pick(options)
    input_file = if options[:file]
                   validate_input_file(options[:file])
                 elsif options[:simulator]
                   capture_simulator_screenshot(options[:simulator])
                 else
                   capture_default_simulator
                 end

    unless options[:at]
      abort "❌ Missing coordinates. Use --at x,y"
    end

    x, y = parse_coordinates(options[:at])

    puts "🎨 Picking color at (#{x}, #{y})..."

    color = extract_color(input_file, x, y)
    format = options[:format] || 'hex'

    puts "\n📊 Color Information:"
    display_color_info(color, format)

    # Verify against design system if provided
    if options[:design_system]
      verify_against_design_system(color, options[:design_system])
    end

    # Check accessibility contrast if background color provided
    if options[:background]
      check_contrast(color, options[:background])
    end

    color
  end

  def verify(options)
    unless options[:file] && options[:at] && options[:design_system]
      abort "❌ Verify mode requires --file, --at, and --design-system"
    end

    input_file = validate_input_file(options[:file])
    design_system_file = validate_input_file(options[:design_system])

    x, y = parse_coordinates(options[:at])

    puts "🔍 Verifying color at (#{x}, #{y}) against design system..."

    color = extract_color(input_file, x, y)
    design_colors = parse_design_system(design_system_file)

    match = find_closest_match(color, design_colors)

    puts "\n📊 Extracted Color:"
    display_color_info(color, 'hex')

    if match[:exact]
      puts "\n✅ EXACT MATCH: #{match[:name]}"
      puts "   Design System Color: #{match[:hex]}"
    elsif match[:close]
      puts "\n⚠️  CLOSE MATCH: #{match[:name]}"
      puts "   Design System Color: #{match[:hex]}"
      puts "   Difference: ΔE = #{match[:delta_e].round(2)}"
      puts "   (ΔE < 3.0 = Visually similar, < 1.0 = Imperceptible)"
    else
      puts "\n❌ NO MATCH FOUND"
      puts "   Closest: #{match[:name]} (ΔE = #{match[:delta_e].round(2)})"
      puts "   Recommendation: Use design system color or add new color"
    end

    match
  end

  def batch_pick(options)
    unless options[:file] && options[:points]
      abort "❌ Batch mode requires --file and --points (JSON file)"
    end

    input_file = validate_input_file(options[:file])
    points_file = validate_input_file(options[:points])

    points = JSON.parse(File.read(points_file))

    puts "🎨 Batch picking #{points.length} colors..."

    results = points.map.with_index do |point, index|
      x, y = point['x'], point['y']
      label = point['label'] || "Color #{index + 1}"

      color = extract_color(input_file, x, y)

      puts "\n#{label} (#{x}, #{y}):"
      puts "  Hex: #{color[:hex]}"
      puts "  RGB: rgb(#{color[:r]}, #{color[:g]}, #{color[:b]})"

      {
        label: label,
        x: x,
        y: y,
        hex: color[:hex],
        rgb: { r: color[:r], g: color[:g], b: color[:b] },
        rgba: { r: color[:r], g: color[:g], b: color[:b], a: color[:a] }
      }
    end

    # Save results
    if options[:output]
      output_file = options[:output]
      File.write(output_file, JSON.pretty_generate(results))
      puts "\n✅ Results saved: #{output_file}"
    end

    # Verify against design system if provided
    if options[:design_system]
      design_colors = parse_design_system(options[:design_system])
      verify_batch_colors(results, design_colors)
    end

    results
  end

  def palette(options)
    input_file = if options[:file]
                   validate_input_file(options[:file])
                 elsif options[:simulator]
                   capture_simulator_screenshot(options[:simulator])
                 else
                   capture_default_simulator
                 end

    colors_count = options[:colors] || 10

    puts "🎨 Extracting #{colors_count} dominant colors..."

    # Use ImageMagick to extract dominant colors
    command = "convert #{input_file} -colors #{colors_count} -unique-colors txt:-"
    output = `#{command}`

    colors = []
    output.each_line do |line|
      next unless line =~ /(\d+),(\d+),(\d+)/

      r, g, b = $1.to_i, $2.to_i, $3.to_i
      hex = rgb_to_hex(r, g, b)

      colors << { r: r, g: g, b: b, hex: hex }
    end

    puts "\n📊 Dominant Colors:"
    colors.each_with_index do |color, index|
      puts "  #{index + 1}. #{color[:hex]} - rgb(#{color[:r]}, #{color[:g]}, #{color[:b]})"
    end

    # Save palette if output specified
    if options[:output]
      output_file = options[:output]
      File.write(output_file, JSON.pretty_generate(colors))
      puts "\n✅ Palette saved: #{output_file}"
    end

    colors
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

    temp_screenshot = "/tmp/color_picker_#{Time.now.to_i}.png"
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

    temp_screenshot = "/tmp/color_picker_#{Time.now.to_i}.png"
    result = system("xcrun simctl io #{booted_device['udid']} screenshot #{temp_screenshot}")

    unless result
      abort "❌ Failed to capture screenshot"
    end

    temp_screenshot
  end

  def parse_coordinates(coord_string)
    coords = coord_string.split(',').map(&:to_i)
    unless coords.length == 2
      abort "❌ Invalid coordinates format. Use: x,y"
    end
    coords
  end

  def extract_color(image_file, x, y)
    # Use ImageMagick to get pixel color
    command = "convert #{image_file} -format '%[pixel:p{#{x},#{y}}]' info:"
    output = `#{command}`.strip

    # Parse color output (format: srgb(r,g,b))
    if output =~ /srgba?\((\d+),(\d+),(\d+)(?:,([0-9.]+))?\)/
      r, g, b = $1.to_i, $2.to_i, $3.to_i
      a = $4 ? $4.to_f : 1.0

      hex = rgb_to_hex(r, g, b)

      {
        r: r,
        g: g,
        b: b,
        a: a,
        hex: hex
      }
    else
      abort "❌ Failed to extract color at (#{x}, #{y})"
    end
  end

  def rgb_to_hex(r, g, b)
    "#%02x%02x%02x" % [r, g, b]
  end

  def hex_to_rgb(hex)
    hex = hex.gsub('#', '')
    r = hex[0..1].to_i(16)
    g = hex[2..3].to_i(16)
    b = hex[4..5].to_i(16)
    { r: r, g: g, b: b }
  end

  def display_color_info(color, format)
    case format
    when 'hex'
      puts "  Hex: #{color[:hex]}"
    when 'rgb'
      puts "  RGB: rgb(#{color[:r]}, #{color[:g]}, #{color[:b]})"
    when 'rgba'
      puts "  RGBA: rgba(#{color[:r]}, #{color[:g]}, #{color[:b]}, #{color[:a]})"
    when 'swift'
      r = (color[:r] / 255.0).round(3)
      g = (color[:g] / 255.0).round(3)
      b = (color[:b] / 255.0).round(3)
      puts "  Swift Color: Color(red: #{r}, green: #{g}, blue: #{b})"
    when 'uicolor'
      r = (color[:r] / 255.0).round(3)
      g = (color[:g] / 255.0).round(3)
      b = (color[:b] / 255.0).round(3)
      puts "  UIColor: UIColor(red: #{r}, green: #{g}, blue: #{b}, alpha: #{color[:a]})"
    when 'nscolor'
      r = (color[:r] / 255.0).round(3)
      g = (color[:g] / 255.0).round(3)
      b = (color[:b] / 255.0).round(3)
      puts "  NSColor: NSColor(red: #{r}, green: #{g}, blue: #{b}, alpha: #{color[:a]})"
    when 'css'
      puts "  CSS: rgb(#{color[:r]}, #{color[:g]}, #{color[:b]})"
    end

    puts "  All formats:"
    puts "    Hex:     #{color[:hex]}"
    puts "    RGB:     rgb(#{color[:r]}, #{color[:g]}, #{color[:b]})"
    puts "    RGBA:    rgba(#{color[:r]}, #{color[:g]}, #{color[:b]}, #{color[:a]})"
    puts "    Swift:   Color(red: #{(color[:r] / 255.0).round(3)}, green: #{(color[:g] / 255.0).round(3)}, blue: #{(color[:b] / 255.0).round(3)})"
  end

  def parse_design_system(file_path)
    content = File.read(file_path)
    colors = {}

    # Parse Swift color definitions
    # Example: static let primaryBlue = Color(red: 0.2, green: 0.4, blue: 0.8)
    content.scan(/let\s+(\w+)\s*=\s*Color\(red:\s*([0-9.]+),\s*green:\s*([0-9.]+),\s*blue:\s*([0-9.]+)/) do |name, r, g, b|
      colors[name] = {
        r: (r.to_f * 255).round,
        g: (g.to_f * 255).round,
        b: (b.to_f * 255).round,
        hex: rgb_to_hex((r.to_f * 255).round, (g.to_f * 255).round, (b.to_f * 255).round)
      }
    end

    # Parse hex color definitions
    # Example: static let primaryBlue = Color(hex: "#3366CC")
    content.scan(/let\s+(\w+)\s*=\s*Color\(hex:\s*"([#a-fA-F0-9]+)"/) do |name, hex|
      rgb = hex_to_rgb(hex)
      colors[name] = rgb.merge(hex: hex.downcase)
    end

    colors
  end

  def find_closest_match(color, design_colors)
    best_match = nil
    min_delta_e = Float::INFINITY

    design_colors.each do |name, design_color|
      delta_e = calculate_delta_e(color, design_color)

      if delta_e < min_delta_e
        min_delta_e = delta_e
        best_match = {
          name: name,
          hex: design_color[:hex],
          delta_e: delta_e,
          exact: delta_e < 1.0,
          close: delta_e < 3.0
        }
      end
    end

    best_match || { name: 'none', hex: '#000000', delta_e: Float::INFINITY, exact: false, close: false }
  end

  def calculate_delta_e(color1, color2)
    # Simplified Delta E (CIE76) calculation
    # Good enough for design system verification
    dr = color1[:r] - color2[:r]
    dg = color1[:g] - color2[:g]
    db = color1[:b] - color2[:b]

    Math.sqrt(dr**2 + dg**2 + db**2)
  end

  def verify_against_design_system(color, design_system_file)
    design_colors = parse_design_system(design_system_file)
    match = find_closest_match(color, design_colors)

    puts "\n🔍 Design System Verification:"
    if match[:exact]
      puts "  ✅ Matches: #{match[:name]}"
    elsif match[:close]
      puts "  ⚠️  Close to: #{match[:name]} (ΔE = #{match[:delta_e].round(2)})"
    else
      puts "  ❌ No match (Closest: #{match[:name]}, ΔE = #{match[:delta_e].round(2)})"
    end
  end

  def check_contrast(foreground, background_hex)
    bg = hex_to_rgb(background_hex)
    fg = { r: foreground[:r], g: foreground[:g], b: foreground[:b] }

    # Calculate relative luminance
    fg_lum = relative_luminance(fg)
    bg_lum = relative_luminance(bg)

    # Calculate contrast ratio
    lighter = [fg_lum, bg_lum].max
    darker = [fg_lum, bg_lum].min
    contrast = (lighter + 0.05) / (darker + 0.05)

    puts "\n♿ Accessibility Contrast:"
    puts "  Contrast Ratio: #{contrast.round(2)}:1"
    puts "  WCAG AA (Normal Text ≥4.5:1): #{contrast >= 4.5 ? '✅ Pass' : '❌ Fail'}"
    puts "  WCAG AA (Large Text ≥3:1): #{contrast >= 3.0 ? '✅ Pass' : '❌ Fail'}"
    puts "  WCAG AAA (Normal Text ≥7:1): #{contrast >= 7.0 ? '✅ Pass' : '⚠️  Fail'}"
    puts "  WCAG AAA (Large Text ≥4.5:1): #{contrast >= 4.5 ? '✅ Pass' : '⚠️  Fail'}"
  end

  def relative_luminance(color)
    # Convert RGB to relative luminance (WCAG formula)
    r = color[:r] / 255.0
    g = color[:g] / 255.0
    b = color[:b] / 255.0

    r = r <= 0.03928 ? r / 12.92 : ((r + 0.055) / 1.055)**2.4
    g = g <= 0.03928 ? g / 12.92 : ((g + 0.055) / 1.055)**2.4
    b = b <= 0.03928 ? b / 12.92 : ((b + 0.055) / 1.055)**2.4

    0.2126 * r + 0.7152 * g + 0.0722 * b
  end

  def verify_batch_colors(results, design_colors)
    puts "\n🔍 Design System Verification:"

    results.each do |result|
      color = { r: result[:rgb][:r], g: result[:rgb][:g], b: result[:rgb][:b] }
      match = find_closest_match(color, design_colors)

      status = if match[:exact]
                 "✅ #{match[:name]}"
               elsif match[:close]
                 "⚠️  #{match[:name]} (ΔE=#{match[:delta_e].round(1)})"
               else
                 "❌ No match"
               end

      puts "  #{result[:label]}: #{status}"
    end
  end
end

# CLI Interface
def main
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: color_picker.rb [command] [options]"
    opts.separator ""
    opts.separator "Commands:"
    opts.separator "  pick        Pick color at specific coordinates"
    opts.separator "  verify      Verify color against design system"
    opts.separator "  batch       Batch pick colors from JSON file"
    opts.separator "  palette     Extract dominant color palette"
    opts.separator ""
    opts.separator "Options:"

    opts.on('-s', '--simulator NAME', 'Simulator name (e.g., "iPhone 16")') do |v|
      options[:simulator] = v
    end

    opts.on('-f', '--file PATH', 'Use existing screenshot file') do |v|
      options[:file] = v
    end

    opts.on('--at X,Y', 'Coordinates to pick color from (e.g., 100,200)') do |v|
      options[:at] = v
    end

    opts.on('-p', '--points PATH', 'JSON file with coordinates for batch picking') do |v|
      options[:points] = v
    end

    opts.on('-d', '--design-system PATH', 'Design system file (Colors.swift) for verification') do |v|
      options[:design_system] = v
    end

    opts.on('-b', '--background HEX', 'Background color for contrast check (e.g., #FFFFFF)') do |v|
      options[:background] = v
    end

    opts.on('--format FORMAT', ColorPicker::OUTPUT_FORMATS, "Output format (#{ColorPicker::OUTPUT_FORMATS.join(', ')})") do |v|
      options[:format] = v
    end

    opts.on('-c', '--colors N', Integer, 'Number of dominant colors to extract (palette mode)') do |v|
      options[:colors] = v
    end

    opts.on('-o', '--output PATH', 'Output file path (JSON)') do |v|
      options[:output] = File.expand_path(v)
    end

    opts.on('-h', '--help', 'Show this help message') do
      puts opts
      exit
    end
  end.parse!

  command = ARGV[0]

  case command
  when 'pick'
    tool = ColorPicker.new
    tool.pick(options)
  when 'verify'
    tool = ColorPicker.new
    tool.verify(options)
  when 'batch'
    tool = ColorPicker.new
    tool.batch_pick(options)
  when 'palette'
    tool = ColorPicker.new
    tool.palette(options)
  else
    puts "❌ Unknown command: #{command}"
    puts "Usage: color_picker.rb [pick|verify|batch|palette] [options]"
    puts "Run 'color_picker.rb --help' for more information"
    exit 1
  end
end

main if __FILE__ == $PROGRAM_NAME
