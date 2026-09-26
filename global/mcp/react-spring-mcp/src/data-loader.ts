import { readFile, readdir } from 'fs/promises'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import {
  HookDocumentationSchema,
  ConceptDocumentationSchema,
  type HookDocumentation,
  type ConceptDocumentation
} from './types.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DATA_DIR = join(__dirname, '../data')

export class DataLoader {
  private hooksCache = new Map<string, HookDocumentation>()
  private conceptsCache = new Map<string, ConceptDocumentation>()
  private hooksList: string[] | null = null
  private conceptsList: string[] | null = null

  async getHookDocs(hookName: string): Promise<HookDocumentation | null> {
    // Sanitize input - only allow alphanumeric and hyphens
    if (!/^[a-zA-Z0-9-]+$/.test(hookName)) {
      console.error(`Invalid hook name: ${hookName}`)
      return null
    }

    // Check cache
    if (this.hooksCache.has(hookName)) {
      return this.hooksCache.get(hookName)!
    }

    try {
      const filePath = join(DATA_DIR, 'hooks', `${hookName}.json`)
      const content = await readFile(filePath, 'utf-8')
      const raw = JSON.parse(content)

      // Validate with Zod schema
      const docs = HookDocumentationSchema.parse(raw)

      this.hooksCache.set(hookName, docs)
      return docs
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        // File not found - expected for invalid hook names
        return null
      }
      // Unexpected error (validation or I/O) - log to stderr
      console.error(`Error loading hook '${hookName}':`, error.message)
      return null
    }
  }

  async getConceptDocs(conceptName: string): Promise<ConceptDocumentation | null> {
    // Sanitize input - only allow alphanumeric and hyphens
    if (!/^[a-zA-Z0-9-]+$/.test(conceptName)) {
      console.error(`Invalid concept name: ${conceptName}`)
      return null
    }

    // Check cache
    if (this.conceptsCache.has(conceptName)) {
      return this.conceptsCache.get(conceptName)!
    }

    try {
      const filePath = join(DATA_DIR, 'concepts', `${conceptName}.json`)
      const content = await readFile(filePath, 'utf-8')
      const raw = JSON.parse(content)

      // Validate with Zod schema
      const docs = ConceptDocumentationSchema.parse(raw)

      this.conceptsCache.set(conceptName, docs)
      return docs
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        // File not found - expected for invalid concept names
        return null
      }
      // Unexpected error (validation or I/O) - log to stderr
      console.error(`Error loading concept '${conceptName}':`, error.message)
      return null
    }
  }

  async listHooks(): Promise<string[]> {
    // Auto-discover hooks from filesystem
    if (!this.hooksList) {
      try {
        const files = await readdir(join(DATA_DIR, 'hooks'))
        this.hooksList = files
          .filter(f => f.endsWith('.json'))
          .map(f => f.replace('.json', ''))
          .sort()
      } catch (error) {
        console.error('Error listing hooks:', error)
        this.hooksList = []
      }
    }
    return this.hooksList
  }

  async listConcepts(): Promise<string[]> {
    // Auto-discover concepts from filesystem
    if (!this.conceptsList) {
      try {
        const files = await readdir(join(DATA_DIR, 'concepts'))
        this.conceptsList = files
          .filter(f => f.endsWith('.json'))
          .map(f => f.replace('.json', ''))
          .sort()
      } catch (error) {
        console.error('Error listing concepts:', error)
        this.conceptsList = []
      }
    }
    return this.conceptsList
  }

  async warmCache(): Promise<void> {
    // Pre-load common hooks and concepts
    const hooks = await this.listHooks()
    const concepts = await this.listConcepts()

    // Warm cache for the most commonly used items
    const topHooks = hooks.slice(0, 4) // First 4 hooks
    const topConcepts = concepts.slice(0, 2) // First 2 concepts

    await Promise.all([
      ...topHooks.map(hook => this.getHookDocs(hook)),
      ...topConcepts.map(concept => this.getConceptDocs(concept))
    ])
  }
}
