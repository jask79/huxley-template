#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'fileutils'

# Grid Overlay Tool for iOS Simulator Design Validation
#
# Purpose: Overlay 4px/8px grid on simulator screenshots for visual validation
# Use case: UI Designer verifies spacing and alignment compliance
#
# Requirements:
# - ImageMagick (brew install imagemagick)
# - Active iOS Simulator
#
# Usage:
#   ruby grid_overlay.rb capture --simulator "iPhone 16" --grid 8 --output ~/Desktop/grid_overlay.png
#   ruby grid_overlay.rb capture --file ~/Desktop/screenshot.png --grid 4 --output ~/Desktop/with_grid.png

class GridOverlay
  GRID_SIZES = [4, 8, 16, 32].freeze
  GRID_COLORS = {
    'red' => 'rgba(255,0,0,0.3)',
    'blue' => 'rgba(0,0,255,0.3)',
    'green' => 'rgba(0,255,0,0.3)',
    'pink' => 'rgba(255,0,255,0.3)',
    'cyan' => 'rgba(0,255,255,0.3)'
  }.freeze

  def initialize
    check_dependencies
  end

  def capture(options)
    input_file = if options[:file]
                   validate_input_file(options[:file])
                 elsif options[:simulator]
                   capture_simulator_screenshot(options[:simulator])
                 else
                   capture_default_simulator
                 end

    grid_size = options[:grid] || 8
    grid_color = GRID_COLORS[options[:color] || 'red']
    output_file = options[:output] || generate_output_path(input_file, grid_size)

    puts "📐 Applying #{grid_size}px grid overlay..."
    apply_grid_overlay(input_file, output_file, grid_size, grid_color, options)

    puts "✅ Grid overlay complete: #{output_file}"
    puts "   Grid size: #{grid_size}px"
    puts "   Grid color: #{options[:color] || 'red'}"
    puts "   Major lines: #{options[:major] ? 'enabled' : 'disabled'}" if options[:major]

    output_file
  end

  def list_presets
    puts "\n📐 Available Grid Presets:\n\n"
    puts "Standard Grids:"
    puts "  4px  - Micro spacing (buttons, icons)"
    puts "  8px  - Standard spacing (most common)"
    puts "  16px - Major spacing (sections, cards)"
    puts "  32px - Layout spacing (columns, margins)"
    puts "\nColors: #{GRID_COLORS.keys.join(', ')}"
    puts "\nExample:"
    puts "  ruby grid_overlay.rb capture --grid 8 --color blue --major 4"
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

    # Get simulator UDID
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
      abort "❌ Simulator '#{simulator_name}' not found or not booted.\n" \
            "   Boot simulator first or use --file to process existing screenshot."
    end

    # Capture screenshot
    temp_screenshot = "/tmp/grid_overlay_#{Time.now.to_i}.png"
    result = system("xcrun simctl io #{device_udid} screenshot #{temp_screenshot}")

    unless result
      abort "❌ Failed to capture screenshot from simulator"
    end

    temp_screenshot
  end

  def capture_default_simulator
    puts "📸 Capturing screenshot from active simulator..."

    # Get booted simulator
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
      abort "❌ No booted simulator found.\n" \
            "   Boot a simulator first or use --simulator to specify which one."
    end

    puts "   Using: #{booted_device['name']}"

    temp_screenshot = "/tmp/grid_overlay_#{Time.now.to_i}.png"
    result = system("xcrun simctl io #{booted_device['udid']} screenshot #{temp_screenshot}")

    unless result
      abort "❌ Failed to capture screenshot from simulator"
    end

    temp_screenshot
  end

  def generate_output_path(input_file, grid_size)
    dir = File.dirname(input_file)
    basename = File.basename(input_file, '.*')
    ext = File.extname(input_file)
    timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
    "#{dir}/#{basename}_grid#{grid_size}_#{timestamp}#{ext}"
  end

  def apply_grid_overlay(input_file, output_file, grid_size, grid_color, options)
    # Get image dimensions
    identify_output = `convert #{input_file} -format "%wx%h" info:`
    width, height = identify_output.strip.split('x').map(&:to_i)

    unless width > 0 && height > 0
      abort "❌ Failed to read image dimensions from #{input_file}"
    end

    puts "   Image size: #{width}x#{height}"

    # Create grid overlay
    grid_commands = []

    # Vertical lines
    (0..width).step(grid_size).each do |x|
      grid_commands << "-draw \"line #{x},0 #{x},#{height}\""
    end

    # Horizontal lines
    (0..height).step(grid_size).each do |y|
      grid_commands << "-draw \"line 0,#{y} #{width},#{y}\""
    end

    # Major grid lines (thicker, darker) if requested
    if options[:major]
      major_grid = options[:major].to_i
      major_color = grid_color.gsub(/0\.\d+/, '0.5') # Increase opacity

      # Major vertical lines
      (0..width).step(major_grid).each do |x|
        grid_commands << "-strokewidth 2 -stroke #{major_color} -draw \"line #{x},0 #{x},#{height}\""
      end

      # Major horizontal lines
      (0..height).step(major_grid).each do |y|
        grid_commands << "-strokewidth 2 -stroke #{major_color} -draw \"line 0,#{y} #{width},#{y}\""
      end
    end

    # Apply grid using ImageMagick
    command = [
      "convert #{input_file}",
      "-strokewidth 1",
      "-stroke #{grid_color}",
      grid_commands.join(' '),
      output_file
    ].join(' ')

    result = system(command)

    unless result
      abort "❌ Failed to apply grid overlay with ImageMagick"
    end

    # Add metadata annotation if requested
    if options[:annotate]
      annotate_image(output_file, grid_size, width, height)
    end
  end

  def annotate_image(image_file, grid_size, width, height)
    annotation = "Grid: #{grid_size}px | Size: #{width}x#{height}"

    command = [
      "convert #{image_file}",
      "-gravity South",
      "-pointsize 24",
      "-fill white",
      "-stroke black",
      "-strokewidth 2",
      "-annotate +0+10 '#{annotation}'",
      image_file
    ].join(' ')

    system(command)
  end
end

# CLI Interface
def main
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: grid_overlay.rb [command] [options]"
    opts.separator ""
    opts.separator "Commands:"
    opts.separator "  capture     Capture simulator screenshot and apply grid overlay"
    opts.separator "  presets     List available grid presets"
    opts.separator ""
    opts.separator "Options:"

    opts.on('-s', '--simulator NAME', 'Simulator name (e.g., "iPhone 16")') do |v|
      options[:simulator] = v
    end

    opts.on('-f', '--file PATH', 'Use existing screenshot file') do |v|
      options[:file] = v
    end

    opts.on('-g', '--grid SIZE', Integer, "Grid size in pixels (4, 8, 16, 32)") do |v|
      unless GridOverlay::GRID_SIZES.include?(v)
        abort "❌ Invalid grid size. Choose from: #{GridOverlay::GRID_SIZES.join(', ')}"
      end
      options[:grid] = v
    end

    opts.on('-c', '--color COLOR', GridOverlay::GRID_COLORS.keys, "Grid color (#{GridOverlay::GRID_COLORS.keys.join(', ')})") do |v|
      options[:color] = v
    end

    opts.on('-m', '--major SIZE', Integer, 'Major grid lines every N pixels (thicker, darker)') do |v|
      options[:major] = v
    end

    opts.on('-o', '--output PATH', 'Output file path') do |v|
      options[:output] = File.expand_path(v)
    end

    opts.on('-a', '--annotate', 'Add grid metadata annotation to image') do
      options[:annotate] = true
    end

    opts.on('-h', '--help', 'Show this help message') do
      puts opts
      exit
    end
  end.parse!

  command = ARGV[0]

  case command
  when 'capture'
    tool = GridOverlay.new
    tool.capture(options)
  when 'presets'
    tool = GridOverlay.new
    tool.list_presets
  else
    puts "❌ Unknown command: #{command}"
    puts "Usage: grid_overlay.rb [capture|presets] [options]"
    puts "Run 'grid_overlay.rb --help' for more information"
    exit 1
  end
end

main if __FILE__ == $PROGRAM_NAME
