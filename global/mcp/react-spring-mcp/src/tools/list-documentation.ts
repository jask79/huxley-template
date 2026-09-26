import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js'
import type { DataLoader } from '../data-loader.js'

export async function listDocumentation(
  loader: DataLoader,
  category: 'hooks' | 'concepts' | 'all' = 'all'
): Promise<CallToolResult> {
  try {
    let output = '# React-Spring Documentation\n\n'
    output += 'Available documentation for the react-spring animation library.\n\n'

    if (category === 'hooks' || category === 'all') {
      const hooks = await loader.listHooks()
      output += '## Hooks\n\n'

      if (hooks.length === 0) {
        output += '_No hooks available_\n\n'
      } else {
        // Load brief descriptions for each hook
        for (const hook of hooks) {
          const doc = await loader.getHookDocs(hook)
          if (doc) {
            output += `### ${doc.name}\n`
            output += `${doc.description}\n\n`
            if (doc.commonPatterns && doc.commonPatterns.length > 0) {
              output += `**Common Use Cases:** ${doc.commonPatterns.slice(0, 3).join(', ')}\n\n`
            }
          } else {
            output += `### ${hook}\n`
            output += `_Documentation not available_\n\n`
          }
        }
      }
    }

    if (category === 'concepts' || category === 'all') {
      const concepts = await loader.listConcepts()
      output += '## Concepts\n\n'

      if (concepts.length === 0) {
        output += '_No concepts available_\n\n'
      } else {
        // Load brief descriptions for each concept
        for (const concept of concepts) {
          const doc = await loader.getConceptDocs(concept)
          if (doc) {
            output += `### ${doc.title}\n`
            output += `${doc.description}\n\n`
          } else {
            output += `### ${concept}\n`
            output += `_Documentation not available_\n\n`
          }
        }
      }
    }

    output += '---\n\n'
    output += '**Usage:**\n'
    output += '- Get hook details: Use `get_hook_api` with a hook name\n'
    output += '- Get concept details: Use `get_concept` with a concept name\n'
    output += '- Official docs: https://react-spring.dev\n'

    return {
      content: [{
        type: 'text',
        text: output
      }]
    }
  } catch (error: any) {
    return {
      content: [{
        type: 'text',
        text: `Error listing documentation: ${error.message}`
      }],
      isError: true
    }
  }
}
