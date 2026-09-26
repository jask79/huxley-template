# frozen_string_literal: true

require 'json'
require 'fileutils'
require 'shellwords'

module IOSTesting
  # Automatically runs all 5 design validation tools
  class DesignValidator
    TOOLS_DIR = File.expand_path('../../', __dir__)

    def initialize(state_dir:, project_path:)
      @state_dir = state_dir
      @project_path = project_path
      @validation_dir = File.join(state_dir, 'validation')
      FileUtils.mkdir_p(@validation_dir)

      # Try to find design system files
      @design_system_colors = find_design_system_colors
    end

    # Run complete validation suite after screenshot capture
    def validate(screenshot_path, iteration:)
      return nil unless screenshot_path && File.exist?(screenshot_path)

      timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
      validation_results = {
        timestamp: Time.now.utc.iso8601,
        iteration: iteration,
        screenshot: screenshot_path,
        tools: {}
      }

      puts ""
      puts "=" * 80
      puts "  DESIGN VALIDATION (Iteration #{iteration})"
      puts "=" * 80
      puts ""

      # 1. Grid Overlay - Check spacing alignment
      grid_result = run_grid_overlay(screenshot_path, timestamp)
      validation_results[:tools][:grid_overlay] = grid_result

      # 2. Ruler Tool - Measure key elements (if spec file exists)
      ruler_result = run_ruler_measurements(screenshot_path, timestamp)
      validation_results[:tools][:ruler] = ruler_result if ruler_result

      # 3. Color Picker - Verify design system colors
      color_result = run_color_verification(screenshot_path, timestamp)
      validation_results[:tools][:color_picker] = color_result if color_result

      # 4. Device Bezel - Professional screenshot
      bezel_result = run_device_bezel(screenshot_path, timestamp)
      validation_results[:tools][:device_bezel] = bezel_result

      # 5. Screen Recorder - Mark for recording if needed
      validation_results[:tools][:screen_recorder] = {
        status: 'manual',
        note: 'Run screen_recorder.rb manually for animation demos'
      }

      # Save validation report
      report_file = File.join(@validation_dir, "validation_#{timestamp}.json")
      File.write(report_file, JSON.pretty_generate(validation_results))

      # Create validation manifest
      update_manifest(validation_results)

      puts ""
      puts "✅ Validation complete! Report saved to: #{report_file}"
      puts ""

      validation_results
    end

    private

    def run_grid_overlay(screenshot_path, timestamp)
      puts "🔍 Running grid overlay (8px grid)..."

      output_file = File.join(@validation_dir, "grid_#{timestamp}.png")
      grid_tool = File.join(TOOLS_DIR, 'grid_overlay.rb')

      cmd = [
        'ruby', grid_tool,
        'overlay',
        '--file', screenshot_path,
        '--grid', '8',
        '--color', 'red',
        '--output', output_file
      ]

      output = `#{cmd.shelljoin} 2>&1`
      success = $?.success?

      if success && File.exist?(output_file)
        puts "   ✅ Grid overlay saved: #{output_file}"
        {
          status: 'success',
          output_file: output_file,
          grid_size: 8,
          note: 'Visual inspection recommended - check alignment'
        }
      else
        puts "   ⚠️  Grid overlay failed: #{output}"
        {
          status: 'failed',
          error: output
        }
      end
    end

    def run_ruler_measurements(screenshot_path, timestamp)
      # Check if measurement spec exists
      spec_file = File.join(@project_path, 'docs', 'measurements.json')
      return nil unless File.exist?(spec_file)

      puts "📏 Running ruler measurements from spec..."

      begin
        spec = JSON.parse(File.read(spec_file))
        measurements = spec['measurements'] || []

        if measurements.empty?
          puts "   ⚠️  No measurements defined in spec"
          return nil
        end

        ruler_tool = File.join(TOOLS_DIR, 'ruler_tool.rb')
        results = []

        measurements.each do |measurement|
          from = measurement['from']  # "x,y"
          to = measurement['to']      # "x,y"
          label = measurement['label'] || 'measurement'

          cmd = [
            'ruby', ruler_tool,
            'measure',
            '--file', screenshot_path,
            '--from', from,
            '--to', to
          ]

          output = `#{cmd.shelljoin} 2>&1`
          success = $?.success?

          if success
            # Parse measurement from output
            if output =~ /Horizontal:\s+(\d+)pt/
              horizontal = $1.to_i
              puts "   ✅ #{label}: #{horizontal}pt"
              results << {
                label: label,
                measurement: horizontal,
                unit: 'pt',
                status: check_grid_compliance(horizontal)
              }
            end
          else
            puts "   ⚠️  Failed to measure #{label}"
          end
        end

        {
          status: 'success',
          measurements: results
        }
      rescue => e
        puts "   ⚠️  Measurement spec error: #{e.message}"
        nil
      end
    end

    def run_color_verification(screenshot_path, timestamp)
      return nil unless @design_system_colors

      puts "🎨 Verifying design system colors..."

      # Check if color check points exist in spec
      spec_file = File.join(@project_path, 'docs', 'color_checks.json')
      return nil unless File.exist?(spec_file)

      begin
        spec = JSON.parse(File.read(spec_file))
        check_points = spec['check_points'] || []

        if check_points.empty?
          puts "   ⚠️  No color check points defined"
          return nil
        end

        color_tool = File.join(TOOLS_DIR, 'color_picker.rb')
        results = []

        check_points.each do |check|
          at = check['at']  # "x,y"
          expected = check['expected']
          label = check['label'] || 'color'

          cmd = [
            'ruby', color_tool,
            'verify',
            '--file', screenshot_path,
            '--at', at,
            '--design-system', @design_system_colors
          ]

          output = `#{cmd.shelljoin} 2>&1`
          success = $?.success?

          if output =~ /EXACT MATCH: (\w+)/
            color_name = $1
            puts "   ✅ #{label}: #{color_name} (exact match)"
            results << {
              label: label,
              color: color_name,
              match: 'exact'
            }
          elsif output =~ /CLOSE MATCH: (\w+)/
            color_name = $1
            puts "   ⚠️  #{label}: #{color_name} (close match)"
            results << {
              label: label,
              color: color_name,
              match: 'close'
            }
          else
            puts "   ❌ #{label}: No match found"
            results << {
              label: label,
              match: 'none'
            }
          end
        end

        {
          status: 'success',
          checks: results
        }
      rescue => e
        puts "   ⚠️  Color check error: #{e.message}"
        nil
      end
    end

    def run_device_bezel(screenshot_path, timestamp)
      puts "📱 Creating professional screenshot with device bezel..."

      output_file = File.join(@validation_dir, "handoff_#{timestamp}.png")
      bezel_tool = File.join(TOOLS_DIR, 'device_bezel.rb')

      cmd = [
        'ruby', bezel_tool,
        'frame',
        '--file', screenshot_path,
        '--device', 'iPhone 16 Pro',
        '--background', 'white',
        '--shadow',
        '--output', output_file
      ]

      output = `#{cmd.shelljoin} 2>&1`
      success = $?.success?

      if success && File.exist?(output_file)
        puts "   ✅ Professional screenshot: #{output_file}"
        {
          status: 'success',
          output_file: output_file,
          device: 'iPhone 16 Pro'
        }
      else
        puts "   ⚠️  Device bezel failed: #{output}"
        {
          status: 'failed',
          error: output
        }
      end
    end

    def find_design_system_colors
      # Look for Colors.swift in common locations
      possible_paths = [
        File.join(@project_path, 'src', 'DesignSystem', 'Colors.swift'),
        File.join(@project_path, 'DesignSystem', 'Colors.swift'),
        File.join(@project_path, 'Sources', 'DesignSystem', 'Colors.swift')
      ]

      possible_paths.each do |path|
        return path if File.exist?(path)
      end

      nil
    end

    def check_grid_compliance(value)
      if value % 8 == 0
        '8px grid ✅'
      elsif value % 4 == 0
        '4px grid ✅'
      else
        'off-grid ⚠️'
      end
    end

    def update_manifest(validation_results)
      manifest_file = File.join(@validation_dir, 'validation_manifest.json')

      manifest = if File.exist?(manifest_file)
                   JSON.parse(File.read(manifest_file))
                 else
                   {
                     'project': File.basename(@project_path),
                     'validations': []
                   }
                 end

      manifest['validations'] << {
        'timestamp': validation_results[:timestamp],
        'iteration': validation_results[:iteration],
        'screenshot': validation_results[:screenshot],
        'grid_overlay': validation_results[:tools][:grid_overlay][:output_file],
        'device_bezel': validation_results[:tools][:device_bezel][:output_file],
        'status': determine_overall_status(validation_results)
      }

      # Keep only last 10 validations
      manifest['validations'] = manifest['validations'].last(10)

      File.write(manifest_file, JSON.pretty_generate(manifest))
    end

    def determine_overall_status(results)
      tools = results[:tools]

      # Check if any tools failed
      failed = tools.values.any? { |t| t.is_a?(Hash) && t[:status] == 'failed' }

      failed ? 'warning' : 'success'
    end
  end
end
