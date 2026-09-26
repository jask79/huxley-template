#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'
require 'optparse'
require 'fileutils'

# Screen Recorder Tool for iOS Simulator Animation Demos
#
# Purpose: Record animations and interactions from iOS Simulator
# Use case: Demo animations to Mobile Dev, create video documentation
#
# Requirements:
# - Active iOS Simulator
# - FFmpeg (brew install ffmpeg) for video processing
#
# Usage:
#   ruby screen_recorder.rb record --duration 10 --output demo.mp4
#   ruby screen_recorder.rb record --simulator "iPhone 16" --duration 30 --fps 60
#   ruby screen_recorder.rb convert --input recording.mov --output demo.gif --fps 15

class ScreenRecorder
  SUPPORTED_FORMATS = %w[mov mp4 gif].freeze
  DEFAULT_FPS = 60
  GIF_FPS = 15

  def initialize
    check_dependencies
  end

  def record(options)
    simulator = find_simulator(options[:simulator])

    unless simulator
      abort "❌ No booted simulator found. Boot a simulator first."
    end

    duration = options[:duration] || 10
    output_file = options[:output] || generate_output_path('mov')

    puts "🎬 Recording from #{simulator[:name]}..."
    puts "   Duration: #{duration}s"
    puts "   Output: #{output_file}"

    # Ensure output directory exists
    FileUtils.mkdir_p(File.dirname(output_file))

    # Start recording
    pid = start_recording(simulator[:udid], output_file)

    unless pid
      abort "❌ Failed to start recording"
    end

    puts "\n⏺️  Recording started (PID: #{pid})"
    puts "   Press Ctrl+C to stop early, or wait #{duration}s..."

    # Setup signal handler for early termination
    trap('INT') do
      puts "\n\n⏹️  Stopping recording early..."
      stop_recording(pid)
      exit 0
    end

    # Wait for duration
    sleep(duration)

    # Stop recording
    puts "\n⏹️  Stopping recording..."
    stop_recording(pid)

    # Verify output file
    unless File.exist?(output_file)
      abort "❌ Recording file not created: #{output_file}"
    end

    file_size = File.size(output_file) / 1024.0 / 1024.0
    puts "✅ Recording saved: #{output_file}"
    puts "   Size: #{file_size.round(2)} MB"

    # Convert to GIF if requested
    if options[:gif]
      gif_file = output_file.gsub(/\.(mov|mp4)$/, '.gif')
      convert_to_gif(output_file, gif_file, options[:gif_fps] || GIF_FPS, options)
    end

    # Optimize video if requested
    if options[:optimize]
      optimize_video(output_file, options)
    end

    output_file
  end

  def convert(options)
    unless options[:input]
      abort "❌ Missing input file. Use --input path/to/video.mov"
    end

    input_file = validate_input_file(options[:input])
    output_file = options[:output] || generate_converted_path(input_file, options[:format] || 'gif')

    format = File.extname(output_file).delete('.')
    unless SUPPORTED_FORMATS.include?(format)
      abort "❌ Unsupported format: #{format}. Supported: #{SUPPORTED_FORMATS.join(', ')}"
    end

    puts "🎬 Converting #{File.basename(input_file)} to #{format.upcase}..."

    case format
    when 'gif'
      fps = options[:fps] || GIF_FPS
      convert_to_gif(input_file, output_file, fps, options)
    when 'mp4'
      convert_to_mp4(input_file, output_file, options)
    when 'mov'
      # Just copy if already MOV
      if File.extname(input_file) == '.mov'
        FileUtils.cp(input_file, output_file)
        puts "✅ Copied: #{output_file}"
      else
        convert_to_mov(input_file, output_file, options)
      end
    end

    output_file
  end

  def trim(options)
    unless options[:input] && options[:start]
      abort "❌ Trim requires --input and --start (e.g., --start 00:00:05)"
    end

    input_file = validate_input_file(options[:input])
    output_file = options[:output] || generate_trimmed_path(input_file)

    start_time = options[:start]
    duration = options[:duration]

    puts "✂️  Trimming video..."
    puts "   Start: #{start_time}"
    puts "   Duration: #{duration || 'to end'}"

    ffmpeg_args = [
      "ffmpeg -i #{input_file}",
      "-ss #{start_time}",
      duration ? "-t #{duration}" : nil,
      "-c copy",
      output_file,
      "-y"
    ].compact.join(' ')

    result = system(ffmpeg_args)

    unless result
      abort "❌ Failed to trim video"
    end

    puts "✅ Trimmed video saved: #{output_file}"

    output_file
  end

  def list_devices
    puts "\n📱 Available Simulators:\n\n"

    list_output = `xcrun simctl list devices available -j`
    devices = JSON.parse(list_output)['devices']

    booted_count = 0

    devices.each do |runtime, device_list|
      runtime_name = runtime.gsub('com.apple.CoreSimulator.SimRuntime.', '').gsub('-', ' ')

      device_list.each do |device|
        status_indicator = device['state'] == 'Booted' ? '🟢' : '⚪'
        puts "  #{status_indicator} #{device['name']} (#{runtime_name})"

        if device['state'] == 'Booted'
          booted_count += 1
        end
      end
    end

    if booted_count == 0
      puts "\n⚠️  No simulators currently booted."
      puts "   Boot a simulator before recording."
    else
      puts "\n✅ #{booted_count} simulator#{booted_count > 1 ? 's' : ''} ready for recording"
    end
  end

  private

  def check_dependencies
    unless system('which xcrun > /dev/null 2>&1')
      abort "❌ Xcode Command Line Tools not found. Install with: xcode-select --install"
    end

    unless system('which ffmpeg > /dev/null 2>&1')
      puts "⚠️  FFmpeg not found. Install with: brew install ffmpeg"
      puts "   (Required for GIF conversion and video optimization)"
    end
  end

  def validate_input_file(file_path)
    expanded_path = File.expand_path(file_path)
    unless File.exist?(expanded_path)
      abort "❌ Input file not found: #{expanded_path}"
    end
    expanded_path
  end

  def find_simulator(simulator_name)
    list_output = `xcrun simctl list devices available -j`
    devices = JSON.parse(list_output)['devices']

    # Find booted simulators
    booted_devices = []
    devices.each do |runtime, device_list|
      device_list.each do |device|
        if device['state'] == 'Booted'
          if simulator_name.nil? || device['name'] == simulator_name
            booted_devices << {
              name: device['name'],
              udid: device['udid'],
              runtime: runtime
            }
          end
        end
      end
    end

    if booted_devices.empty?
      nil
    elsif simulator_name
      booted_devices.first
    else
      # Return first booted device
      booted_devices.first
    end
  end

  def generate_output_path(extension)
    timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
    "#{Dir.home}/Desktop/simulator_recording_#{timestamp}.#{extension}"
  end

  def generate_converted_path(input_file, format)
    dir = File.dirname(input_file)
    basename = File.basename(input_file, '.*')
    "#{dir}/#{basename}_converted.#{format}"
  end

  def generate_trimmed_path(input_file)
    dir = File.dirname(input_file)
    basename = File.basename(input_file, '.*')
    ext = File.extname(input_file)
    "#{dir}/#{basename}_trimmed#{ext}"
  end

  def start_recording(udid, output_file)
    # Start recording in background using xcrun simctl io
    command = "xcrun simctl io #{udid} recordVideo #{output_file} > /dev/null 2>&1 &"
    system(command)

    # Get PID of recording process
    sleep(1) # Give it a moment to start
    pid_output = `pgrep -f "recordVideo #{output_file}"`.strip
    pid_output.empty? ? nil : pid_output.to_i
  end

  def stop_recording(pid)
    # Send SIGINT to stop recording gracefully
    Process.kill('INT', pid)
    sleep(2) # Give it time to finalize the file

    # Force kill if still running
    begin
      Process.kill(0, pid)
      Process.kill('KILL', pid)
    rescue Errno::ESRCH
      # Process already stopped
    end
  rescue StandardError => e
    puts "⚠️  Error stopping recording: #{e.message}"
  end

  def convert_to_gif(input_file, output_file, fps, options)
    puts "   Converting to GIF (#{fps} fps)..."

    # Calculate dimensions
    width = options[:width] || 600
    quality = options[:quality] || 80

    # Generate color palette for better GIF quality
    palette_file = "/tmp/palette_#{Time.now.to_i}.png"

    palette_cmd = [
      "ffmpeg -i #{input_file}",
      "-vf \"fps=#{fps},scale=#{width}:-1:flags=lanczos,palettegen\"",
      palette_file,
      "-y"
    ].join(' ')

    system(palette_cmd)

    # Create GIF using palette
    gif_cmd = [
      "ffmpeg -i #{input_file}",
      "-i #{palette_file}",
      "-filter_complex \"fps=#{fps},scale=#{width}:-1:flags=lanczos[x];[x][1:v]paletteuse\"",
      output_file,
      "-y"
    ].join(' ')

    result = system(gif_cmd)

    # Clean up palette
    FileUtils.rm_f(palette_file)

    unless result
      abort "❌ Failed to convert to GIF"
    end

    file_size = File.size(output_file) / 1024.0 / 1024.0
    puts "✅ GIF saved: #{output_file}"
    puts "   Size: #{file_size.round(2)} MB"
  end

  def convert_to_mp4(input_file, output_file, options)
    puts "   Converting to MP4..."

    quality = options[:quality] || 23 # CRF value (lower = better quality)

    command = [
      "ffmpeg -i #{input_file}",
      "-c:v libx264",
      "-crf #{quality}",
      "-preset medium",
      "-c:a aac",
      "-b:a 128k",
      output_file,
      "-y"
    ].join(' ')

    result = system(command)

    unless result
      abort "❌ Failed to convert to MP4"
    end

    file_size = File.size(output_file) / 1024.0 / 1024.0
    puts "✅ MP4 saved: #{output_file}"
    puts "   Size: #{file_size.round(2)} MB"
  end

  def convert_to_mov(input_file, output_file, options)
    puts "   Converting to MOV..."

    command = [
      "ffmpeg -i #{input_file}",
      "-c:v h264",
      "-c:a aac",
      output_file,
      "-y"
    ].join(' ')

    result = system(command)

    unless result
      abort "❌ Failed to convert to MOV"
    end

    puts "✅ MOV saved: #{output_file}"
  end

  def optimize_video(video_file, options)
    puts "   Optimizing video..."

    optimized_file = video_file.gsub(/(\.\w+)$/, '_optimized\1')

    # Use H.264 with better compression
    command = [
      "ffmpeg -i #{video_file}",
      "-c:v libx264",
      "-crf 28",
      "-preset slow",
      "-c:a aac",
      "-b:a 96k",
      optimized_file,
      "-y"
    ].join(' ')

    result = system(command)

    if result
      original_size = File.size(video_file) / 1024.0 / 1024.0
      optimized_size = File.size(optimized_file) / 1024.0 / 1024.0
      savings = ((1 - optimized_size / original_size) * 100).round(1)

      puts "✅ Optimized video saved: #{optimized_file}"
      puts "   Original: #{original_size.round(2)} MB"
      puts "   Optimized: #{optimized_size.round(2)} MB"
      puts "   Savings: #{savings}%"
    else
      puts "⚠️  Optimization failed, using original"
    end
  end
end

# CLI Interface
def main
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: screen_recorder.rb [command] [options]"
    opts.separator ""
    opts.separator "Commands:"
    opts.separator "  record       Record video from simulator"
    opts.separator "  convert      Convert video to another format"
    opts.separator "  trim         Trim video to specific time range"
    opts.separator "  list         List available simulators"
    opts.separator ""
    opts.separator "Options:"

    opts.on('-s', '--simulator NAME', 'Simulator name (default: first booted)') do |v|
      options[:simulator] = v
    end

    opts.on('-d', '--duration SECONDS', Integer, 'Recording duration in seconds (default: 10)') do |v|
      options[:duration] = v
    end

    opts.on('-o', '--output PATH', 'Output file path') do |v|
      options[:output] = File.expand_path(v)
    end

    opts.on('-i', '--input PATH', 'Input file for conversion/trimming') do |v|
      options[:input] = v
    end

    opts.on('--start TIME', 'Start time for trimming (e.g., 00:00:05)') do |v|
      options[:start] = v
    end

    opts.on('-f', '--format FORMAT', ScreenRecorder::SUPPORTED_FORMATS, "Output format (#{ScreenRecorder::SUPPORTED_FORMATS.join(', ')})") do |v|
      options[:format] = v
    end

    opts.on('--fps FPS', Integer, 'Frames per second (default: 60 for video, 15 for GIF)') do |v|
      options[:fps] = v
    end

    opts.on('--gif', 'Also create GIF version after recording') do
      options[:gif] = true
    end

    opts.on('--gif-fps FPS', Integer, 'GIF frame rate (default: 15)') do |v|
      options[:gif_fps] = v
    end

    opts.on('--width PX', Integer, 'Width for GIF conversion (default: 600)') do |v|
      options[:width] = v
    end

    opts.on('--quality N', Integer, 'Quality setting (GIF: 1-100, MP4: 0-51)') do |v|
      options[:quality] = v
    end

    opts.on('--optimize', 'Optimize video file size after recording') do
      options[:optimize] = true
    end

    opts.on('-h', '--help', 'Show this help message') do
      puts opts
      exit
    end
  end.parse!

  command = ARGV[0]

  case command
  when 'record'
    tool = ScreenRecorder.new
    tool.record(options)
  when 'convert'
    tool = ScreenRecorder.new
    tool.convert(options)
  when 'trim'
    tool = ScreenRecorder.new
    tool.trim(options)
  when 'list'
    tool = ScreenRecorder.new
    tool.list_devices
  else
    puts "❌ Unknown command: #{command}"
    puts "Usage: screen_recorder.rb [record|convert|trim|list] [options]"
    puts "Run 'screen_recorder.rb --help' for more information"
    exit 1
  end
end

main if __FILE__ == $PROGRAM_NAME
