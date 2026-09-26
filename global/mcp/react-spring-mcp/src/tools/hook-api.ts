import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js'
import type { DataLoader } from '../data-loader.js'

export async function getHookApi(
  loader: DataLoader,
  hookName: string
): Promise<CallToolResult> {
  try {
    const docs = await loader.getHookDocs(hookName)

    if (!docs) {
      const availableHooks = await loader.listHooks()
      return {
        content: [{
          type: "text",
          text: `Hook '${hookName}' not found.\n\nAvailable hooks: ${availableHooks.join(", ")}\n\nFor more info: https://react-spring.dev`
        }]
      }
    }

    // Format documentation nicely
    let output = `# ${docs.name}\n\n`
    output += `${docs.description}\n\n`

    if (docs.signature) {
      output += `## Signature\n\`\`\`typescript\n${docs.signature}\n\`\`\`\n\n`
    }

    // Handle parameters (for config, this includes all properties)
    if (docs.parameters && docs.parameters.length > 0) {
      output += `## Configuration Properties\n\n`
      docs.parameters.forEach((param: any) => {
        output += `### ${param.name}\n`
        output += `- **Type**: \`${param.type}\`\n`
        if (param.default !== undefined && param.default !== null) {
          output += `- **Default**: \`${param.default}\`\n`
        }
        output += `- **Description**: ${param.description}\n`
        if (param.physics) {
          output += `- **Physics**: ${param.physics}\n`
        }
        output += `\n`

        if (param.properties && param.properties.length > 0) {
          param.properties.forEach((prop: any) => {
            output += `  - **${prop.name}** (\`${prop.type}\`): ${prop.description}\n`
          })
          output += `\n`
        }
      })
    }

    // Handle presets (for config)
    if (docs.presets && docs.presets.length > 0) {
      output += `## Presets\n\n`
      docs.presets.forEach((preset: any) => {
        output += `### ${preset.name}\n`
        output += `\`\`\`javascript\n${JSON.stringify(preset.values, null, 2)}\n\`\`\`\n`
        output += `${preset.description}\n`
        output += `**Use Case**: ${preset.useCase}\n\n`
      })
    }

    // Handle methods (for useSpringRef)
    if (docs.methods && docs.methods.length > 0) {
      output += `## Methods\n\n`
      docs.methods.forEach((method: any) => {
        output += `### ${method.name}\n`
        output += `${method.description}\n`
        if (method.signature) {
          output += `\`\`\`typescript\n${method.signature}\n\`\`\`\n\n`
        }
      })
    }

    if (docs.returns) {
      output += `## Returns\n**${docs.returns.type}**: ${docs.returns.description}\n\n`
    }

    // Physics explanation (for config)
    if (docs.physicsExplanation) {
      output += `## Physics Explanation\n\n`
      const pe = docs.physicsExplanation
      if (pe.springPhysics) {
        output += `**Spring Physics**: ${pe.springPhysics}\n\n`
      }
      if (pe.tuningGuidance) {
        output += `**Tuning Guidance**: ${pe.tuningGuidance}\n\n`
      }
      if (pe.whenToUsePhysics) {
        output += `**When to Use Physics**: ${pe.whenToUsePhysics}\n\n`
      }
      if (pe.whenToUseDuration) {
        output += `**When to Use Duration**: ${pe.whenToUseDuration}\n\n`
      }
    }

    // Key differences (for useSpringRef)
    if (docs.keyDifferences) {
      output += `## Key Differences\n\n`
      output += `**Declarative**: ${docs.keyDifferences.declarative}\n\n`
      output += `**Imperative**: ${docs.keyDifferences.imperative}\n\n`
    }

    // Performance benefits (for useSpringRef)
    if (docs.performanceBenefits && docs.performanceBenefits.length > 0) {
      output += `## Performance Benefits\n${docs.performanceBenefits.map((b: any) => `- ${b}`).join('\n')}\n\n`
    }

    if (docs.examples && docs.examples.length > 0) {
      output += `## Examples\n\n`
      docs.examples.forEach((example: any) => {
        output += `### ${example.title}\n\`\`\`tsx\n${example.code}\n\`\`\`\n\n`
      })
    }

    if (docs.commonPatterns && docs.commonPatterns.length > 0) {
      output += `## Common Patterns\n${docs.commonPatterns.map((p: any) => `- ${p}`).join('\n')}\n\n`
    }

    // Important notes (for useSpringRef)
    if (docs.importantNotes && docs.importantNotes.length > 0) {
      output += `## Important Notes\n${docs.importantNotes.map((n: any) => `- ${n}`).join('\n')}\n\n`
    }

    if (docs.relatedHooks && docs.relatedHooks.length > 0) {
      output += `## Related Hooks\n${docs.relatedHooks.join(', ')}\n`
    }

    return {
      content: [{
        type: "text",
        text: output
      }]
    }
  } catch (error: any) {
    return {
      content: [{
        type: "text",
        text: `Error loading documentation: ${error.message}`
      }],
      isError: true
    }
  }
}
