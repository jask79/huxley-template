#!/usr/bin/env ruby
# frozen_string_literal: true

require 'xcodeproj'
require 'optparse'
require 'json'
require 'pathname'

# Dynamic Xcode Project Management CLI Tool
# Reusable tool for managing Xcode projects programmatically
class XcodeProjectTool
  VERSION = '2.1.0'

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
    when 'add-files'
      add_files_command(args)
    when 'list-targets'
      list_targets_command(args)
    when 'list-files'
      list_files_command(args)
    when 'remove-files'
      remove_files_command(args)
    when 'update-build-settings'
      update_build_settings_command(args)
    when 'find-missing-files'
      find_missing_files_command(args)
    when 'sync-directory'
      sync_directory_command(args)
    when 'add-framework'
      add_framework_command(args)
    when 'add-build-phase'
      add_build_phase_command(args)
    when 'create-group'
      create_group_command(args)
    when 'update-info-plist'
      update_info_plist_command(args)
    when 'list-build-settings'
      list_build_settings_command(args)
    when 'get-issues'
      get_issues_command(args)
    when 'version', '-v', '--version'
      puts "xcode_project_tool v#{VERSION}"
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

  def add_files_command(args)
    opts = parse_options(args, %i[project target files create_groups create_references])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])
    files = expand_file_patterns(opts[:files])

    log "Adding #{files.count} files to target '#{opts[:target]}'"

    files.each do |file|
      add_file_to_target(project, target, file, opts)
    end

    save_project(project) unless @options[:dry_run]

    output_result(success: true, message: "Added #{files.count} files to target", files: files)
  end

  def list_targets_command(args)
    opts = parse_options(args, %i[project])

    project = open_project(opts[:project])
    targets = project.targets.map(&:name)

    output_result(targets: targets)
  end

  def list_files_command(args)
    opts = parse_options(args, %i[project target])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])

    files = target.source_build_phase.files.map do |build_file|
      build_file.file_ref.real_path.to_s
    end.compact

    output_result(target: opts[:target], file_count: files.count, files: files)
  end

  def remove_files_command(args)
    opts = parse_options(args, %i[project target files])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])
    files = expand_file_patterns(opts[:files])

    log "Removing #{files.count} files from target '#{opts[:target]}'"

    removed = []
    files.each do |file|
      if remove_file_from_target(project, target, file)
        removed << file
      end
    end

    save_project(project) unless @options[:dry_run]

    output_result(success: true, message: "Removed #{removed.count} files from target", files: removed)
  end

  def update_build_settings_command(args)
    opts = parse_options(args, %i[project target setting value])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])

    log "Updating build setting '#{opts[:setting]}' to '#{opts[:value]}'"

    target.build_configurations.each do |config|
      config.build_settings[opts[:setting]] = opts[:value]
    end

    save_project(project) unless @options[:dry_run]

    output_result(success: true, message: "Updated build setting", setting: opts[:setting], value: opts[:value])
  end

  def find_missing_files_command(args)
    opts = parse_options(args, %i[project target directory])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])
    directory = opts[:directory]

    # Get all Swift files in directory
    all_files = Dir.glob("#{directory}/**/*.swift").map { |f| File.absolute_path(f) }

    # Get files already in target
    target_files = target.source_build_phase.files.map do |build_file|
      build_file.file_ref.real_path.to_s if build_file.file_ref.respond_to?(:real_path)
    end.compact

    # Find missing files
    missing = all_files - target_files

    log "Found #{missing.count} files not in target (#{all_files.count} total, #{target_files.count} in target)"

    output_result(
      total_files: all_files.count,
      files_in_target: target_files.count,
      missing_files_count: missing.count,
      missing_files: missing
    )
  end

  def sync_directory_command(args)
    opts = parse_options(args, %i[project target directory])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])
    directory = opts[:directory]

    # Get all Swift files in directory
    all_files = Dir.glob("#{directory}/**/*.swift").map { |f| File.absolute_path(f) }

    # Get files already in target
    target_files = target.source_build_phase.files.map do |build_file|
      build_file.file_ref.real_path.to_s if build_file.file_ref.respond_to?(:real_path)
    end.compact

    # Find missing files
    missing = all_files - target_files

    log "Syncing directory: #{missing.count} files to add"

    missing.each do |file|
      add_file_to_target(project, target, file, opts)
    end

    save_project(project) unless @options[:dry_run]

    output_result(
      success: true,
      message: "Synced directory to target",
      files_added: missing.count,
      files: missing
    )
  end

  def add_framework_command(args)
    opts = parse_options(args, %i[project target framework])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])
    framework_name = opts[:framework]

    log "Adding framework '#{framework_name}' to target '#{opts[:target]}'"

    unless @options[:dry_run]
      # Check if framework is already added
      existing = target.frameworks_build_phase.files.find do |build_file|
        build_file.display_name == framework_name
      end

      if existing
        log "Framework '#{framework_name}' already exists in target"
      else
        # Add framework (SPM package or system framework)
        if opts[:package_url]
          # Swift Package Manager
          package_ref = project.root_object.package_references.find do |ref|
            ref.repositoryURL == opts[:package_url]
          end

          unless package_ref
            package_ref = project.new(Xcodeproj::Project::Object::XCRemoteSwiftPackageReference)
            package_ref.repositoryURL = opts[:package_url]
            package_ref.requirement = { 'kind' => 'upToNextMajorVersion', 'minimumVersion' => opts[:version] || '1.0.0' }
            project.root_object.package_references << package_ref
          end

          product_ref = target.package_product_dependencies.find { |p| p.product_name == framework_name }
          unless product_ref
            product_ref = project.new(Xcodeproj::Project::Object::XCSwiftPackageProductDependency)
            product_ref.product_name = framework_name
            product_ref.package = package_ref
            target.package_product_dependencies << product_ref
          end
        else
          # System framework
          file_ref = project.frameworks_group.new_reference("System/Library/Frameworks/#{framework_name}.framework")
          file_ref.source_tree = 'SDKROOT'
          target.frameworks_build_phase.add_file_reference(file_ref)
        end
      end
    end

    save_project(project) unless @options[:dry_run]

    output_result(
      success: true,
      message: "Added framework to target",
      framework: framework_name,
      type: opts[:package_url] ? 'SPM' : 'System'
    )
  end

  def add_build_phase_command(args)
    opts = parse_options(args, %i[project target phase_name])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])
    phase_name = opts[:phase_name]
    script = opts[:script] || ''

    log "Adding build phase '#{phase_name}' to target '#{opts[:target]}'"

    unless @options[:dry_run]
      # Check if phase already exists
      existing = target.shell_script_build_phases.find { |phase| phase.name == phase_name }

      if existing
        log "Build phase '#{phase_name}' already exists"
        if opts[:script]
          existing.shell_script = script
          log "Updated script for existing phase"
        end
      else
        # Create new run script phase
        phase = target.new_shell_script_build_phase(phase_name)
        phase.shell_script = script
        phase.show_env_vars_in_log = '0'

        # Optional: set input/output files
        if opts[:input_files]
          opts[:input_files].each { |f| phase.input_paths << f }
        end
        if opts[:output_files]
          opts[:output_files].each { |f| phase.output_paths << f }
        end
      end
    end

    save_project(project) unless @options[:dry_run]

    output_result(
      success: true,
      message: "Added build phase to target",
      phase_name: phase_name,
      script_length: script.length
    )
  end

  def create_group_command(args)
    opts = parse_options(args, %i[project group_path])

    project = open_project(opts[:project])
    group_path = opts[:group_path]

    log "Creating group at path '#{group_path}'"

    unless @options[:dry_run]
      # Split path into components
      components = group_path.split('/')
      current_group = project.main_group

      components.each do |component|
        # Find or create subgroup
        subgroup = current_group.children.find { |child| child.display_name == component }

        unless subgroup
          subgroup = current_group.new_group(component)
          log "Created group: #{component}"
        end

        current_group = subgroup
      end
    end

    save_project(project) unless @options[:dry_run]

    output_result(
      success: true,
      message: "Created group",
      group_path: group_path
    )
  end

  def update_info_plist_command(args)
    opts = parse_options(args, %i[project target key value])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])
    key = opts[:key]
    value = opts[:value]

    log "Updating Info.plist key '#{key}' to '#{value}'"

    unless @options[:dry_run]
      # Get Info.plist path from build settings
      info_plist_path = target.build_configurations.first.build_settings['INFOPLIST_FILE']

      if info_plist_path
        full_path = File.join(File.dirname(opts[:project]), info_plist_path)

        if File.exist?(full_path)
          require 'plist'

          # Read plist
          plist = Plist.parse_xml(full_path)

          # Parse value type
          parsed_value = case value
          when 'true', 'YES'
            true
          when 'false', 'NO'
            false
          when /^\d+$/
            value.to_i
          when /^\d+\.\d+$/
            value.to_f
          else
            value
          end

          # Update key
          plist[key] = parsed_value

          # Write back
          File.write(full_path, Plist::Emit.dump(plist))
          log "Updated Info.plist at #{full_path}"
        else
          raise "Info.plist not found at #{full_path}"
        end
      else
        raise "INFOPLIST_FILE not set in build settings"
      end
    end

    output_result(
      success: true,
      message: "Updated Info.plist",
      key: key,
      value: value
    )
  end

  def list_build_settings_command(args)
    opts = parse_options(args, %i[project target])

    project = open_project(opts[:project])
    target = find_target(project, opts[:target])

    settings = {}

    target.build_configurations.each do |config|
      settings[config.name] = config.build_settings
    end

    output_result(
      target: opts[:target],
      configurations: settings.keys,
      settings: settings
    )
  end

  def get_issues_command(args)
    opts = parse_options(args, %i[project])

    project_path = opts[:project]
    scheme = opts[:scheme]
    xcresult_path = opts[:xcresult]

    log "Getting build issues for project"

    # Strategy 1: Use provided xcresult path
    if xcresult_path && File.exist?(xcresult_path)
      log "Using provided xcresult: #{xcresult_path}"
      issues = parse_xcresult(xcresult_path)
    # Strategy 2: Find latest xcresult in DerivedData
    elsif !xcresult_path
      log "Finding latest build result..."
      xcresult_path = find_latest_xcresult(project_path, scheme)

      if xcresult_path
        log "Found xcresult: #{xcresult_path}"
        issues = parse_xcresult(xcresult_path)
      else
        # Strategy 3: Run a fresh build to generate xcresult
        log "No recent build found. Running build to generate issues..."
        issues = build_and_get_issues(project_path, scheme, opts[:configuration] || 'Debug')
      end
    else
      raise "xcresult file not found: #{xcresult_path}"
    end

    # Summarize results
    errors = issues.select { |i| i[:type] == 'error' }
    warnings = issues.select { |i| i[:type] == 'warning' }

    output_result(
      total_issues: issues.count,
      errors: errors.count,
      warnings: warnings.count,
      issues: issues,
      summary: {
        clean: issues.empty?,
        buildable: errors.empty?,
        message: issues.empty? ? "No issues found! ✅" : "Found #{errors.count} errors, #{warnings.count} warnings"
      }
    )
  end

  # Helper methods

  def find_latest_xcresult(project_path, scheme = nil)
    # Get project directory
    project_dir = File.dirname(File.absolute_path(project_path))

    # Common DerivedData locations
    derived_data_paths = [
      File.join(project_dir, 'build'),
      File.expand_path('~/Library/Developer/Xcode/DerivedData')
    ]

    latest_xcresult = nil
    latest_mtime = nil

    derived_data_paths.each do |base_path|
      next unless Dir.exist?(base_path)

      # Find all .xcresult bundles
      xcresults = Dir.glob("#{base_path}/**/Logs/Build/*.xcresult")

      xcresults.each do |path|
        mtime = File.mtime(path)
        if latest_mtime.nil? || mtime > latest_mtime
          latest_mtime = mtime
          latest_xcresult = path
        end
      end
    end

    latest_xcresult
  end

  def parse_xcresult(xcresult_path)
    require 'json'

    log "Parsing xcresult bundle..."

    # Use Apple's xcresulttool to extract issues
    # Get the bundle's action record
    cmd = "xcrun xcresulttool get --path '#{xcresult_path}' --format json 2>&1"
    output = `#{cmd}`

    unless $?.success?
      log "Warning: xcresulttool failed, trying alternative method"
      return parse_xcresult_simple(xcresult_path)
    end

    begin
      data = JSON.parse(output)

      issues = []

      # Navigate the xcresult structure to find issues
      # Structure: actions -> buildResult -> issues
      if data['actions']
        data['actions']['_values'].each do |action|
          next unless action['buildResult']

          build_result = action['buildResult']

          # Get issues from build result
          if build_result['issues']
            extract_issues_from_result(build_result['issues'], issues)
          end
        end
      end

      issues
    rescue JSON::ParserError => e
      log "Failed to parse xcresult JSON: #{e.message}"
      parse_xcresult_simple(xcresult_path)
    end
  end

  def extract_issues_from_result(issues_data, issues)
    return unless issues_data['_values']

    issues_data['_values'].each do |issue_summary|
      next unless issue_summary['issueType']

      issue_type = issue_summary['issueType']['_value']
      message = issue_summary['message'] ? issue_summary['message']['_value'] : 'Unknown issue'

      # Get document location (file, line, column)
      location = {}
      if issue_summary['documentLocationInCreatingWorkspace']
        loc = issue_summary['documentLocationInCreatingWorkspace']
        location[:file] = loc['url']['_value'].gsub('file://', '') if loc['url']
        location[:line] = loc['startingLineNumber']['_value'] if loc['startingLineNumber']
        location[:column] = loc['startingColumnNumber']['_value'] if loc['startingColumnNumber']
      end

      issues << {
        type: issue_type.downcase,
        message: message,
        file: location[:file],
        line: location[:line],
        column: location[:column]
      }
    end
  end

  def parse_xcresult_simple(xcresult_path)
    # Fallback: Use xcresulttool to get diagnostics in text format
    log "Using simple text parsing as fallback..."

    cmd = "xcrun xcresulttool get --path '#{xcresult_path}' --legacy 2>&1"
    output = `#{cmd}`

    issues = []

    # Parse text output for errors and warnings
    output.scan(/^(.*?):(\d+):(\d+):\s+(error|warning):\s+(.*)$/) do |match|
      file, line, column, type, message = match

      issues << {
        type: type,
        message: message.strip,
        file: file.strip,
        line: line.to_i,
        column: column.to_i
      }
    end

    issues
  end

  def build_and_get_issues(project_path, scheme, configuration)
    log "Building project to generate issue list..."

    # Determine build command
    if scheme
      build_cmd = "xcodebuild -project '#{project_path}' -scheme '#{scheme}' -configuration #{configuration} build 2>&1"
    else
      build_cmd = "xcodebuild -project '#{project_path}' -configuration #{configuration} build 2>&1"
    end

    output = `#{build_cmd}`
    build_status = $?.success?

    log "Build #{build_status ? 'succeeded' : 'failed'}"

    # Parse build output for issues
    issues = []

    output.scan(/^(.*?):(\d+):(\d+):\s+(error|warning):\s+(.*)$/) do |match|
      file, line, column, type, message = match

      issues << {
        type: type,
        message: message.strip,
        file: file.strip,
        line: line.to_i,
        column: column.to_i
      }
    end

    # Also look for linker errors and other build failures
    if !build_status && issues.empty?
      # Extract general build failure message
      if output =~ /\*\* BUILD FAILED \*\*/
        issues << {
          type: 'error',
          message: 'Build failed - check build output for details',
          file: nil,
          line: nil,
          column: nil
        }
      end
    end

    issues
  end

  # Helper methods

  def open_project(project_path)
    unless File.exist?(project_path)
      raise "Project not found: #{project_path}"
    end

    log "Opening project: #{project_path}"
    Xcodeproj::Project.open(project_path)
  end

  def find_target(project, target_name)
    target = project.targets.find { |t| t.name == target_name }
    raise "Target '#{target_name}' not found. Available: #{project.targets.map(&:name).join(', ')}" unless target

    log "Found target: #{target_name}"
    target
  end

  def add_file_to_target(project, target, file_path, opts = {})
    file_path = File.absolute_path(file_path)

    unless File.exist?(file_path)
      log "Warning: File not found: #{file_path}"
      return false
    end

    # Check if file already in target
    existing = target.source_build_phase.files.find do |build_file|
      build_file.file_ref.respond_to?(:real_path) &&
        build_file.file_ref.real_path.to_s == file_path
    end

    if existing
      log "Skipping (already in target): #{file_path}"
      return false
    end

    log "Adding file: #{file_path}"

    unless @options[:dry_run]
      # Add file reference to project
      file_ref = project.main_group.new_reference(file_path)

      # Add to target's sources build phase
      target.source_build_phase.add_file_reference(file_ref)
    end

    true
  end

  def remove_file_from_target(project, target, file_path)
    file_path = File.absolute_path(file_path)

    build_file = target.source_build_phase.files.find do |bf|
      bf.file_ref.respond_to?(:real_path) &&
        bf.file_ref.real_path.to_s == file_path
    end

    if build_file
      log "Removing file: #{file_path}"
      target.source_build_phase.files.delete(build_file) unless @options[:dry_run]
      true
    else
      log "File not in target: #{file_path}"
      false
    end
  end

  def save_project(project)
    log "Saving project..."
    project.save
    log "Project saved successfully"
  end

  def expand_file_patterns(patterns)
    patterns = [patterns] unless patterns.is_a?(Array)

    files = []
    patterns.each do |pattern|
      if pattern.include?('*')
        files.concat(Dir.glob(pattern))
      else
        files << pattern
      end
    end

    files.map { |f| File.absolute_path(f) }.uniq
  end

  def parse_options(args, required_keys)
    opts = {}

    parser = OptionParser.new do |p|
      p.on('--project PATH', 'Path to .xcodeproj file') { |v| opts[:project] = v }
      p.on('--target NAME', 'Target name') { |v| opts[:target] = v }
      p.on('--scheme NAME', 'Scheme name') { |v| opts[:scheme] = v }
      p.on('--configuration NAME', 'Build configuration (Debug/Release)') { |v| opts[:configuration] = v }
      p.on('--xcresult PATH', 'Path to .xcresult bundle') { |v| opts[:xcresult] = v }
      p.on('--files FILES', Array, 'Files to process (comma-separated or glob)') { |v| opts[:files] = v }
      p.on('--directory PATH', 'Directory path') { |v| opts[:directory] = v }
      p.on('--setting NAME', 'Build setting name') { |v| opts[:setting] = v }
      p.on('--value VALUE', 'Build setting value') { |v| opts[:value] = v }
      p.on('--framework NAME', 'Framework name') { |v| opts[:framework] = v }
      p.on('--package-url URL', 'SPM package URL') { |v| opts[:package_url] = v }
      p.on('--version VERSION', 'SPM package version') { |v| opts[:version] = v }
      p.on('--phase-name NAME', 'Build phase name') { |v| opts[:phase_name] = v }
      p.on('--script SCRIPT', 'Build phase script') { |v| opts[:script] = v }
      p.on('--input-files FILES', Array, 'Build phase input files') { |v| opts[:input_files] = v }
      p.on('--output-files FILES', Array, 'Build phase output files') { |v| opts[:output_files] = v }
      p.on('--group-path PATH', 'Group path (e.g., Views/Components)') { |v| opts[:group_path] = v }
      p.on('--key KEY', 'Info.plist key') { |v| opts[:key] = v }
      p.on('--create-groups', 'Create groups (default)') { opts[:create_groups] = true }
      p.on('--create-references', 'Create folder references') { opts[:create_references] = true }
      p.on('--verbose', 'Verbose output') { @options[:verbose] = true }
      p.on('--dry-run', 'Preview changes without saving') { @options[:dry_run] = true }
      p.on('--json', 'JSON output') { @options[:json_output] = true }
    end

    parser.parse!(args)

    # Validate required options
    missing = required_keys.select { |key| opts[key].nil? }
    unless missing.empty?
      raise "Missing required options: #{missing.map { |k| "--#{k}" }.join(', ')}"
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
          value.each { |item| puts "  - #{item}" }
        else
          puts "#{key}: #{value}"
        end
      end
    end
  end

  def show_help
    puts <<~HELP
      Xcode Project Tool v#{VERSION}
      Dynamic Xcode project management CLI

      USAGE:
        xcode_project_tool.rb COMMAND [OPTIONS]

      COMMANDS:
        add-files              Add files to a target
        list-targets           List all targets in a project
        list-files             List all files in a target
        remove-files           Remove files from a target
        update-build-settings  Modify build settings
        find-missing-files     Find files not in target
        sync-directory         Add all files from directory to target
        add-framework          Add SPM package or system framework
        add-build-phase        Add run script build phase
        create-group           Create file group in navigator
        update-info-plist      Modify Info.plist keys
        list-build-settings    List all build settings
        get-issues             Get build errors and warnings
        version                Show version
        help                   Show this help

      GLOBAL OPTIONS:
        --verbose              Verbose output
        --dry-run              Preview changes without saving
        --json                 JSON output format

      EXAMPLES:
        # Find missing files
        xcode_project_tool.rb find-missing-files \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --directory src/

        # Sync all Swift files from directory
        xcode_project_tool.rb sync-directory \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --directory src/ \\
          --dry-run

        # Add specific files
        xcode_project_tool.rb add-files \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --files "Views/NewView.swift,Models/NewModel.swift"

        # List all targets
        xcode_project_tool.rb list-targets \\
          --project MyApp.xcodeproj

        # Update build setting
        xcode_project_tool.rb update-build-settings \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --setting SWIFT_VERSION \\
          --value 5.9

        # Add SPM framework
        xcode_project_tool.rb add-framework \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --framework Inject \\
          --package-url https://github.com/krzysztofzablocki/Inject \\
          --version 1.5.0

        # Add system framework
        xcode_project_tool.rb add-framework \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --framework UIKit

        # Add run script build phase
        xcode_project_tool.rb add-build-phase \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --phase-name "SwiftLint" \\
          --script "swiftlint"

        # Create group
        xcode_project_tool.rb create-group \\
          --project MyApp.xcodeproj \\
          --group-path "Views/Components"

        # Update Info.plist
        xcode_project_tool.rb update-info-plist \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --key NSCameraUsageDescription \\
          --value "We need camera access"

        # List build settings
        xcode_project_tool.rb list-build-settings \\
          --project MyApp.xcodeproj \\
          --target MyApp \\
          --json

        # Get build issues (auto-finds latest build)
        xcode_project_tool.rb get-issues \\
          --project MyApp.xcodeproj \\
          --verbose

        # Get issues from specific build result
        xcode_project_tool.rb get-issues \\
          --project MyApp.xcodeproj \\
          --xcresult path/to/build.xcresult
    HELP
  end
end

# Run the tool
if __FILE__ == $0
  tool = XcodeProjectTool.new
  tool.run(ARGV)
end
