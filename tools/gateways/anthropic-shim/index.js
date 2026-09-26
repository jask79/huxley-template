#!/usr/bin/env node
/**
 * Minimal Anthropic-compatible proxy that forwards requests to an OpenAI-style backend.
 * Based on maxnowack/anthropic-proxy with local tweaks:
 *  - Allows forwarding to arbitrary base URLs (LiteLLM/Bifrost) with optional Bearer auth.
 *  - Reads completion/reasoning model IDs from environment variables.
 */
import Fastify from 'fastify'
import { TextDecoder } from 'util'

const baseUrl = process.env.ANTHROPIC_PROXY_BASE_URL || 'https://openrouter.ai/api'
const requiresApiKey = !process.env.ANTHROPIC_PROXY_BASE_URL
const key = requiresApiKey ? process.env.OPENROUTER_API_KEY : null
const forwardAuth = process.env.ANTHROPIC_PROXY_AUTH_TOKEN || null

const defaultModel = process.env.DEFAULT_COMPLETION_MODEL || 'openai/gpt-4o'
const models = {
  reasoning: process.env.REASONING_MODEL || defaultModel,
  completion: process.env.COMPLETION_MODEL || defaultModel,
}

const fastify = Fastify({
  logger: process.env.DEBUG ? true : false
})

const debug = (...args) => {
  if (!process.env.DEBUG) return
  console.log(...args)
}

const sendSSE = (reply, event, data) => {
  const sseMessage = `event: ${event}\n` +
                     `data: ${JSON.stringify(data)}\n\n`
  reply.raw.write(sseMessage)
  if (typeof reply.raw.flush === 'function') {
    reply.raw.flush()
  }
}

const mapStopReason = finishReason => {
  switch (finishReason) {
    case 'tool_calls': return 'tool_use'
    case 'stop': return 'end_turn'
    case 'length': return 'max_tokens'
    default: return 'end_turn'
  }
}

fastify.post('/v1/messages', async (request, reply) => {
  try {
    const payload = request.body

    const normalizeContent = content => {
      if (typeof content === 'string') return content
      if (Array.isArray(content)) {
        return content.map(item => {
          if (typeof item === 'string') return item
          if (item && typeof item.text === 'string') return item.text
          return ''
        }).join(' ')
      }
      return null
    }

    const messages = []
    if (payload.system) {
      const systems = Array.isArray(payload.system) ? payload.system : [payload.system]
      systems.forEach(sysMsg => {
        const normalized = normalizeContent(sysMsg.text || sysMsg.content || sysMsg)
        if (normalized) {
          messages.push({
            role: 'system',
            content: normalized
          })
        }
      })
    }

    if (payload.messages && Array.isArray(payload.messages)) {
      payload.messages.forEach(msg => {
        const newMsg = { role: msg.role }
        const normalized = normalizeContent(msg.content)
        if (normalized) newMsg.content = normalized

        const toolCalls = (Array.isArray(msg.content) ? msg.content : [])
          .filter(item => item.type === 'tool_use')
          .map(toolCall => ({
            id: toolCall.id,
            type: 'function',
            function: {
              name: toolCall.name,
              arguments: JSON.stringify(toolCall.input || {})
            }
          }))
        if (toolCalls.length > 0) newMsg.tool_calls = toolCalls

        if (newMsg.content || newMsg.tool_calls) messages.push(newMsg)

        if (Array.isArray(msg.content)) {
          const toolResults = msg.content.filter(item => item.type === 'tool_result')
          toolResults.forEach(result => {
            messages.push({
              role: 'tool',
              content: typeof result.content === 'string'
                ? result.content
                : (Array.isArray(result.content)
                  ? result.content.map(r => r.text || '').join('\n')
                  : result.text || ''),
              tool_call_id: result.tool_use_id,
            })
          })
        }
      })
    }

    const removeUriFormat = schema => {
      if (!schema || typeof schema !== 'object') return schema
      if (schema.type === 'string' && schema.format === 'uri') {
        const { format, ...rest } = schema
        return rest
      }
      if (Array.isArray(schema)) return schema.map(removeUriFormat)
      const result = {}
      for (const key of Object.keys(schema)) {
        if (key === 'properties' && typeof schema[key] === 'object') {
          result[key] = {}
          for (const propKey of Object.keys(schema[key])) {
            result[key][propKey] = removeUriFormat(schema[key][propKey])
          }
        } else if (key === 'items' && typeof schema[key] === 'object') {
          result[key] = removeUriFormat(schema[key])
        } else if (['anyOf', 'allOf', 'oneOf'].includes(key) && Array.isArray(schema[key])) {
          result[key] = schema[key].map(removeUriFormat)
        } else {
          result[key] = removeUriFormat(schema[key])
        }
      }
      return result
    }

    const tools = (payload.tools || [])
      .filter(tool => tool && tool.name !== 'BatchTool')
      .map(tool => ({
        type: 'function',
        function: {
          name: tool.name,
          description: tool.description,
          parameters: removeUriFormat(tool.input_schema),
        },
      }))

    const openaiPayload = {
      model: payload.thinking ? models.reasoning : models.completion,
      messages,
      max_tokens: payload.max_tokens,
      temperature: payload.temperature !== undefined ? payload.temperature : 1,
      stream: payload.stream === true,
    }
    if (tools.length > 0) openaiPayload.tools = tools

    const headers = {
      'Content-Type': 'application/json'
    }
    if (requiresApiKey) {
      headers['Authorization'] = `Bearer ${key}`
    } else if (forwardAuth) {
      headers['Authorization'] = `Bearer ${forwardAuth}`
    }

    const openaiResponse = await fetch(`${baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers,
      body: JSON.stringify(openaiPayload)
    })

    if (!openaiResponse.ok) {
      const errorDetails = await openaiResponse.text()
      reply.code(openaiResponse.status)
      return { error: errorDetails }
    }

    if (!openaiPayload.stream) {
      const data = await openaiResponse.json()
      if (data.error) {
        throw new Error(data.error.message)
      }
      const choice = data.choices[0]
      const openaiMessage = choice.message
      const toolCalls = openaiMessage.tool_calls || []
      const messageId = data.id
        ? data.id.replace('chatcmpl', 'msg')
        : 'msg_' + Math.random().toString(36).slice(2, 26)

      return {
        content: [
          {
            text: openaiMessage.content,
            type: 'text'
          },
          ...toolCalls.map(toolCall => ({
            type: 'tool_use',
            id: toolCall.id,
            name: toolCall.function.name,
            input: JSON.parse(toolCall.function.arguments || '{}'),
          })),
        ],
        id: messageId,
        model: openaiPayload.model,
        role: openaiMessage.role,
        stop_reason: mapStopReason(choice.finish_reason),
        stop_sequence: null,
        type: 'message',
        usage: data.usage || null
      }
    }

    // Handle streaming
    reply.raw.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive'
    })

    const sendMessageStart = () => {
      const messageId = 'msg_' + Math.random().toString(36).slice(2, 26)
      sendSSE(reply, 'message_start', {
        type: 'message_start',
        message: {
          id: messageId,
          type: 'message',
          role: 'assistant',
          model: openaiPayload.model,
          content: [],
          stop_reason: null,
          stop_sequence: null,
          usage: { input_tokens: 0, output_tokens: 0 },
        }
      })
      sendSSE(reply, 'ping', { type: 'ping' })
      return messageId
    }

    const decoder = new TextDecoder('utf-8')
    const reader = openaiResponse.body.getReader()
    let done = false
    let messageId = null
    let usage = null
    const toolCallAccumulators = {}
    let textBlockStarted = false
    let encounteredToolCall = false

    while (!done) {
      const { value, done: doneReading } = await reader.read()
      done = doneReading
      if (!value) continue
      if (!messageId) {
        messageId = sendMessageStart()
      }
      const chunk = decoder.decode(value)
      const lines = chunk.split('\n')
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const dataStr = trimmed.replace(/^data:\s*/, '')
        if (dataStr === '[DONE]') {
          if (encounteredToolCall) {
            Object.keys(toolCallAccumulators).forEach(idx => {
              sendSSE(reply, 'content_block_stop', {
                type: 'content_block_stop',
                index: parseInt(idx, 10)
              })
            })
          } else if (textBlockStarted) {
            sendSSE(reply, 'content_block_stop', {
              type: 'content_block_stop',
              index: 0
            })
          }
          sendSSE(reply, 'message_delta', {
            type: 'message_delta',
            delta: {
              stop_reason: encounteredToolCall ? 'tool_use' : 'end_turn',
              stop_sequence: null
            },
            usage: usage ? { output_tokens: usage.completion_tokens } : null
          })
          sendSSE(reply, 'message_stop', { type: 'message_stop' })
          reply.raw.end()
          return
        }

        const parsed = JSON.parse(dataStr)
        if (parsed.error) {
          throw new Error(parsed.error.message)
        }
        if (parsed.usage) usage = parsed.usage
        const delta = parsed.choices[0].delta
        if (delta?.tool_calls) {
          for (const toolCall of delta.tool_calls) {
            encounteredToolCall = true
            const idx = toolCall.index
            if (!toolCallAccumulators[idx]) {
              toolCallAccumulators[idx] = ''
              sendSSE(reply, 'content_block_start', {
                type: 'content_block_start',
                index: idx,
                content_block: {
                  type: 'tool_use',
                  id: toolCall.id,
                  name: toolCall.function.name,
                  input: {}
                }
              })
            }
            const newArgs = toolCall.function.arguments || ''
            const oldArgs = toolCallAccumulators[idx]
            if (newArgs.length > oldArgs.length) {
              const deltaText = newArgs.substring(oldArgs.length)
              sendSSE(reply, 'content_block_delta', {
                type: 'content_block_delta',
                index: idx,
                delta: {
                  type: 'input_json_delta',
                  partial_json: deltaText
                }
              })
              toolCallAccumulators[idx] = newArgs
            }
          }
        } else if (delta?.content) {
          if (!textBlockStarted) {
            textBlockStarted = true
            sendSSE(reply, 'content_block_start', {
              type: 'content_block_start',
              index: 0,
              content_block: {
                type: 'text',
                text: ''
              }
            })
          }
          sendSSE(reply, 'content_block_delta', {
            type: 'content_block_delta',
            index: 0,
            delta: {
              type: 'text_delta',
              text: delta.content
            }
          })
        }
      }
    }
  } catch (error) {
    reply.code(500)
    return { error: error.message }
  }
})

const port = parseInt(process.env.PORT || '3000', 10)
fastify.listen({ port, host: process.env.HOST || '127.0.0.1' })
  .then(address => {
    console.log(`Anthropic shim listening on ${address}, forwarding to ${baseUrl}`)
  })
  .catch(err => {
    fastify.log.error(err)
    process.exit(1)
  })
