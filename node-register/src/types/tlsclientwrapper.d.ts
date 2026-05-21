declare module 'tlsclientwrapper' {
  interface SessionOpts {
    tlsClientIdentifier?: string
    timeoutSeconds?: number
    followRedirects?: boolean
    insecureSkipVerify?: boolean
    proxyUrl?: string
  }

  interface RequestOpts {
    headers?: Record<string, string>
  }

  interface Response {
    status: number
    body?: string
    headers?: Record<string, string | string[]>
  }

  export class ModuleClient {
    open(): Promise<void>
    terminate(): Promise<void>
    getPoolStats(): unknown
  }

  export class SessionClient {
    constructor(client: ModuleClient, opts?: SessionOpts)
    get(url: string, opts?: RequestOpts): Promise<Response>
    post(url: string, body: string, opts?: RequestOpts): Promise<Response>
    destroySession(): Promise<void>
  }
}
