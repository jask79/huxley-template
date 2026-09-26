# frozen_string_literal: true

require 'json'
require 'fileutils'

module IOSTesting
  # Handles delegation to Mobile Dev agent via Task tool
  class MobileDevDelegator
    def initialize(project_path:, scheme:)
      @project_path = project_path
      @scheme = scheme
    end

    # Format a delegation request for Mobile Dev agent
    def create_delegation_prompt(issues, diagnostic_bundle, iteration)
      prompt = <<~PROMPT
        # iOS Build/Runtime Issue - Fix Required (Iteration #{iteration})

        ## Project Context
        - **Project:** #{File.basename(@project_path)}
        - **Scheme:** #{@scheme}
        - **Diagnostic Bundle:** `#{diagnostic_bundle}`

        ## Issues Detected (#{issues.length})

        #{format_issues(issues)}

        ## Diagnostic Artifacts Available

        The diagnostic bundle contains:
        - `build_log.txt` - Complete Xcode build log
        - `screenshot.png` - Simulator screenshot at time of issue
        - `ui_tree.json` - UI hierarchy dump
        - `git_diff.patch` - Current uncommitted changes (if any)
        - `issue_summary.json` - Structured issue data

        ## Your Task

        1. **Analyze** the diagnostic bundle to understand root cause
        2. **Fix** the issue(s) in the codebase
        3. **Verify** the fix compiles and runs
        4. **Report** what you changed and why

        ## Expected Response Format

        Return a JSON object with:
        ```json
        {
          "success": true/false,
          "approach": "description of fix approach",
          "files_modified": ["path/to/file1.swift", "path/to/file2.swift"],
          "changes_summary": "What was changed and why",
          "verified": true/false
        }
        ```

        ## Success Criteria

        - Code compiles without errors
        - App launches in simulator
        - Issue no longer occurs
        - Changes follow iOS/Swift best practices

        **Please proceed with the fix.**
      PROMPT

      prompt
    end

    # Save delegation context to JSON file for Task tool invocation
    def save_delegation_context(issues, diagnostic_bundle, iteration)
      context_file = File.join(diagnostic_bundle, 'delegation_context.json')

      context = {
        iteration: iteration,
        timestamp: Time.now.utc.iso8601,
        project_path: @project_path,
        scheme: @scheme,
        diagnostic_bundle: diagnostic_bundle,
        issues: issues.map do |issue|
          {
            type: issue[:type],
            severity: issue[:severity],
            message: issue[:message],
            file: issue[:file],
            line: issue[:line],
            timestamp: issue[:timestamp]
          }
        end,
        prompt: create_delegation_prompt(issues, diagnostic_bundle, iteration)
      }

      File.write(context_file, JSON.pretty_generate(context))
      context_file
    end

    # Parse Mobile Dev agent response
    def parse_agent_response(response_text)
      # Try to extract JSON from response
      json_match = response_text.match(/```json\s*(\{.*?\})\s*```/m)

      if json_match
        begin
          response = JSON.parse(json_match[1])
          return {
            success: response['success'] == true,
            approach: response['approach'] || 'unknown',
            files_modified: response['files_modified'] || [],
            changes_summary: response['changes_summary'] || '',
            verified: response['verified'] == true,
            raw_response: response_text
          }
        rescue JSON::ParserError => e
          # Fall through to text parsing
        end
      end

      # Fallback: infer from text
      success = response_text =~ /✅|success|fixed|resolved/i
      failure = response_text =~ /❌|failed|error|cannot/i

      {
        success: success && !failure,
        approach: extract_approach(response_text),
        files_modified: extract_files(response_text),
        changes_summary: response_text[0..500], # First 500 chars
        verified: false,
        raw_response: response_text
      }
    end

    private

    def format_issues(issues)
      issues.map.with_index do |issue, idx|
        location = if issue[:file] && issue[:line]
                     " (`#{issue[:file]}:#{issue[:line]}`)"
                   else
                     ""
                   end

        "#{idx + 1}. **[#{issue[:severity].upcase}]** #{issue[:type]}#{location}\n" \
        "   ```\n" \
        "   #{issue[:message]}\n" \
        "   ```\n"
      end.join("\n")
    end

    def extract_approach(text)
      # Try to find approach description
      if text =~ /approach[:\s]+([^\n]+)/i
        $1.strip
      elsif text =~ /fixed by[:\s]+([^\n]+)/i
        $1.strip
      else
        'inferred_from_response'
      end
    end

    def extract_files(text)
      # Extract file paths from text
      files = []

      # Match .swift files
      text.scan(%r{[\w/]+\.swift}) do |match|
        files << match
      end

      # Match markdown code blocks with file paths
      text.scan(/```[\w]*\s*(?:\/\/|#)\s*([\w/]+\.\w+)/) do |match|
        files << match[0]
      end

      files.uniq
    end
  end
end
