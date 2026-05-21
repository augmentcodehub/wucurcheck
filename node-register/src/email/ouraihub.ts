import { TempEmailService, extractCode } from './email-service'

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

export class OuraihubEmailService implements TempEmailService {
  private apiKey: string
  private domain: string
  private address = ''
  private emailId = ''
  private baseURL = 'https://mail.ouraihub.com/api'

  constructor(apiKey: string, domain: string) {
    this.apiKey = apiKey
    this.domain = domain
  }

  getAddress(): string {
    return this.address
  }

  async create(): Promise<string> {
    const name = 'kiro' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)

    const resp = await fetch(`${this.baseURL}/emails/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': this.apiKey },
      body: JSON.stringify({ name, expiryTime: 3600000, domain: this.domain })
    })
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(`OurAIHub create email failed (${resp.status}): ${text}`)
    }
    const data = await resp.json() as { id?: string; email?: string; address?: string }
    this.emailId = data.id || ''
    this.address = data.email || data.address || `${name}@${this.domain}`
    return this.address
  }

  async waitForCode(timeoutSec: number, intervalSec: number): Promise<string> {
    if (!this.emailId) throw new Error('emailId 未设置，请先调用 create()')
    const deadline = Date.now() + timeoutSec * 1000
    while (Date.now() < deadline) {
      const resp = await fetch(`${this.baseURL}/emails/${this.emailId}`, {
        headers: { 'X-API-Key': this.apiKey }
      })
      if (resp.ok) {
        const data = await resp.json() as { messages?: Array<{ html?: string; content?: string; text?: string }> }
        if (data.messages && data.messages.length > 0) {
          for (const msg of data.messages) {
            const code = extractCode(msg.html || msg.content || msg.text || '')
            if (code) return code
          }
        }
      }
      await sleep(intervalSec * 1000)
    }
    throw new Error(`等待验证码超时 (${timeoutSec}s)`)
  }
}
