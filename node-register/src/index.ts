import { Registrar, RegistrationResult } from './registrar'
import { newConfig } from './config'
import { OuraihubEmailService } from './email/ouraihub'
import * as fs from 'fs'

function parseArgs(argv: string[]): Record<string, string> {
  const args: Record<string, string> = {}
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      const key = argv[i].slice(2)
      const val = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true'
      args[key] = val
    }
  }
  return args
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const count = parseInt(args['count'] || '1', 10)
  const emailDomain = args['email-domain'] || 'ouraihub.com'
  const emailApiKey = args['email-api-key'] || ''
  const proxy = args['proxy'] || ''
  const output = args['output'] || ''

  if (!emailApiKey) {
    console.error('Usage: node dist/index.js --email-api-key <KEY> [--count N] [--email-domain DOMAIN] [--proxy URL] [--output FILE]')
    process.exit(1)
  }

  const results: RegistrationResult[] = []

  for (let i = 0; i < count; i++) {
    console.log(`\n=== 注册 ${i + 1}/${count} ===`)
    const cfg = newConfig({ proxy })
    const reg = new Registrar(cfg)
    reg.setEmailService(new OuraihubEmailService(emailApiKey, emailDomain))

    const result = await reg.run()
    results.push(result)
    console.log(`结果: ${result.status}${result.error ? ' - ' + result.error : ''}`)
    if (result.status === 'success') {
      console.log(`  email: ${result.email}`)
      console.log(`  password: ${result.password}`)
    }
  }

  if (output) {
    fs.writeFileSync(output, JSON.stringify(results, null, 2))
    console.log(`\n结果已写入: ${output}`)
  } else {
    console.log('\n' + JSON.stringify(results, null, 2))
  }
}

main().catch((err) => {
  console.error('Fatal:', err)
  process.exit(1)
})
