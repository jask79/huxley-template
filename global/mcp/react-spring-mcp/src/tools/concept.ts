import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js'
import type { DataLoader } from '../data-loader.js'

export async function getConcept(
  loader: DataLoader,
  conceptName: string
): Promise<CallToolResult> {
  try {
    const docs = await loader.getConceptDocs(conceptName)

    if (!docs) {
      const availableConcepts = await loader.listConcepts()
      return {
        content: [{
          type: "text",
          text: `Concept '${conceptName}' not found.\n\nAvailable concepts: ${availableConcepts.join(", ")}\n\nFor more info: https://react-spring.dev`
        }]
      }
    }

    // Format concept documentation
    let output = `# ${docs.title}\n\n`
    output += `${docs.description}\n\n`

    if (docs.sections && docs.sections.length > 0) {
      docs.sections.forEach((section: any) => {
        output += `## ${section.title}\n\n`
        output += `${section.content}\n\n`
      })
    }

    if (docs.examples && docs.examples.length > 0) {
      output += `## Code Examples\n\n`
      docs.examples.forEach((example: any) => {
        output += `### ${example.title}\n\`\`\`tsx\n${example.code}\n\`\`\`\n\n`
      })
    }

    if (docs.relatedHooks && docs.relatedHooks.length > 0) {
      output += `## Related Hooks\n${docs.relatedHooks.join(', ')}\n\n`
    }

    if (docs.furtherReading && docs.furtherReading.length > 0) {
      output += `## Further Reading\n${docs.furtherReading.map((r: any) => `- ${r}`).join('\n')}\n`
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
        text: `Error loading concept: ${error.message}`
      }],
      isError: true
    }
  }
}
