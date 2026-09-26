import { z } from 'zod'

// Zod Schemas for Runtime Validation
export const PropertyDocSchema = z.object({
  name: z.string(),
  type: z.string(),
  description: z.string()
})

export const ParameterSchema = z.object({
  name: z.string(),
  type: z.string(),
  description: z.string(),
  default: z.union([z.string(), z.number(), z.boolean(), z.null()]).optional(),
  physics: z.string().optional(),
  properties: z.array(PropertyDocSchema).optional()
})

export const ReturnTypeSchema = z.object({
  type: z.string(),
  description: z.string()
})

export const CodeExampleSchema = z.object({
  title: z.string(),
  code: z.string()
})

export const MethodSchema = z.object({
  name: z.string(),
  description: z.string(),
  signature: z.string().optional()
})

export const PresetSchema = z.object({
  name: z.string(),
  values: z.record(z.any()),
  description: z.string(),
  useCase: z.string()
})

export const PhysicsExplanationSchema = z.object({
  springPhysics: z.string().optional(),
  tuningGuidance: z.string().optional(),
  whenToUsePhysics: z.string().optional(),
  whenToUseDuration: z.string().optional()
})

export const KeyDifferencesSchema = z.object({
  declarative: z.string(),
  imperative: z.string()
})

export const HookDocumentationSchema = z.object({
  name: z.string(),
  signature: z.string(),
  description: z.string(),
  parameters: z.array(ParameterSchema),
  returns: ReturnTypeSchema.optional(),
  examples: z.array(CodeExampleSchema),
  commonPatterns: z.array(z.string()),
  relatedHooks: z.array(z.string()),
  // Optional fields for specific hooks
  methods: z.array(MethodSchema).optional(),
  presets: z.array(PresetSchema).optional(),
  physicsExplanation: PhysicsExplanationSchema.optional(),
  keyDifferences: KeyDifferencesSchema.optional(),
  performanceBenefits: z.array(z.string()).optional(),
  importantNotes: z.array(z.string()).optional()
})

export const ConceptSectionSchema = z.object({
  title: z.string(),
  content: z.string()
})

export const ConceptDocumentationSchema = z.object({
  name: z.string(),
  title: z.string(),
  description: z.string(),
  sections: z.array(ConceptSectionSchema),
  examples: z.array(CodeExampleSchema).optional(),
  relatedHooks: z.array(z.string()).optional(),
  furtherReading: z.array(z.string()).optional()
})

// TypeScript Types (inferred from Zod schemas)
export type PropertyDoc = z.infer<typeof PropertyDocSchema>
export type Parameter = z.infer<typeof ParameterSchema>
export type ReturnType = z.infer<typeof ReturnTypeSchema>
export type CodeExample = z.infer<typeof CodeExampleSchema>
export type Method = z.infer<typeof MethodSchema>
export type Preset = z.infer<typeof PresetSchema>
export type PhysicsExplanation = z.infer<typeof PhysicsExplanationSchema>
export type KeyDifferences = z.infer<typeof KeyDifferencesSchema>
export type HookDocumentation = z.infer<typeof HookDocumentationSchema>
export type ConceptSection = z.infer<typeof ConceptSectionSchema>
export type ConceptDocumentation = z.infer<typeof ConceptDocumentationSchema>

export interface AnimationPattern {
  name: string
  description: string
  code: string
  tags: string[]
  difficulty: "beginner" | "intermediate" | "advanced"
}
