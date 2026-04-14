import { Base64 } from 'js-base64'

const PROTOCOL_VMESS = 'vmess'
const PROTOCOL_VLESS = 'vless'
const PROTOCOL_SS = 'ss'
const HASH_SEPARATOR = '#'
const QUERY_SEPARATOR = '?'
const AT_SEPARATOR = '@'
const COLON_SEPARATOR = ':'
const PROTOCOL_SEPARATOR = '://'
const SLASH = '/'
const EMPTY_STRING = ''
const SS_QUERY_PREFIX = '/?'
const SS_AUTHORITY_QUERY_SEPARATOR = '/?'
const BASE64_PADDING = '='
const BASE64_PLUS_RE = /\+/g
const BASE64_SLASH_RE = /\//g
const BASE64_URL_SAFE_PLUS_RE = /-/g
const BASE64_URL_SAFE_SLASH_RE = /_/g
const BASE64_URL_SAFE_PADDING_RE = /=+$/g
const SS_CORE_FIELD_MAP = {
  add: true,
  port: true,
  ps: true,
  method: true,
  password: true,
} as const

export const SUPPORTED_PROTOCOLS = [
  PROTOCOL_VMESS,
  PROTOCOL_VLESS,
  PROTOCOL_SS,
] as const

export type SupportedProtocol = (typeof SUPPORTED_PROTOCOLS)[number]
export type NodeConfig = Record<string, any>
export type ParsedNode = [SupportedProtocol, NodeConfig]

const splitOnce = (value: string, separator: string) => {
  const index = value.indexOf(separator)
  if (index === -1) {
    return [value, EMPTY_STRING] as const
  }
  return [value.slice(0, index), value.slice(index + separator.length)] as const
}

const splitLast = (value: string, separator: string) => {
  const index = value.lastIndexOf(separator)
  if (index === -1) {
    return [value, EMPTY_STRING] as const
  }
  return [value.slice(0, index), value.slice(index + separator.length)] as const
}

const decodeUriValue = (value: string) => {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

const normalizeUrlSafeBase64 = (value: string) => {
  const normalizedValue = value
    .replace(BASE64_URL_SAFE_PLUS_RE, '+')
    .replace(BASE64_URL_SAFE_SLASH_RE, '/')
  const paddingLength = normalizedValue.length % 4
  if (!paddingLength) return normalizedValue
  return normalizedValue.padEnd(
    normalizedValue.length + (4 - paddingLength),
    BASE64_PADDING
  )
}

const toUrlSafeBase64 = (value: string) => {
  return Base64.encode(value)
    .replace(BASE64_PLUS_RE, '-')
    .replace(BASE64_SLASH_RE, '_')
    .replace(BASE64_URL_SAFE_PADDING_RE, EMPTY_STRING)
}

const safeBase64Decode = (value: string) => {
  try {
    return Base64.decode(normalizeUrlSafeBase64(value))
  } catch {
    return value
  }
}

const normalizeNodeConfig = (config: NodeConfig) => {
  const nextConfig = Object.assign({}, config)
  nextConfig.ps = typeof nextConfig.ps === 'string' ? nextConfig.ps : EMPTY_STRING
  return nextConfig
}

const parseHostPort = (value: string) => {
  const hostPort = value.trim()
  const separatorIndex = hostPort.lastIndexOf(COLON_SEPARATOR)
  if (separatorIndex === -1) {
    throw new Error('invalid host port')
  }
  return {
    add: hostPort.slice(0, separatorIndex),
    port: hostPort.slice(separatorIndex + 1),
  }
}

const parseQueryParams = (query: string) => {
  if (!query) return {}
  return query.split('&').reduce((acc, pair) => {
    if (!pair) return acc
    const [key, rawValue] = splitOnce(pair, '=')
    if (!key) return acc
    acc[key] = decodeUriValue(rawValue)
    return acc
  }, {} as Record<string, string>)
}

const buildQueryString = (config: NodeConfig, excludedKeys: Record<string, true>) => {
  return Object.entries(config)
    .filter(([key, value]) => {
      return !excludedKeys[key] && value !== undefined && value !== null && value !== EMPTY_STRING
    })
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join('&')
}

const vmessLinkToJson = (link: string) => {
  const base64Value = link.slice(`${PROTOCOL_VMESS}${PROTOCOL_SEPARATOR}`.length)
  return normalizeNodeConfig(JSON.parse(Base64.decode(base64Value)))
}

const vmessJsonToLink = (config: NodeConfig) => {
  return `${PROTOCOL_VMESS}${PROTOCOL_SEPARATOR}${Base64.encode(JSON.stringify(config))}`
}

export const vlessLinkToJson = (link: string) => {
  const rawValue = link.slice(`${PROTOCOL_VLESS}${PROTOCOL_SEPARATOR}`.length)
  const [content, hashValue] = splitOnce(rawValue, HASH_SEPARATOR)
  const [main, queryValue] = splitOnce(content, QUERY_SEPARATOR)
  const [id, hostPort] = splitOnce(main, AT_SEPARATOR)
  const { add, port } = parseHostPort(hostPort)

  return normalizeNodeConfig({
    id,
    add,
    port,
    ...parseQueryParams(queryValue),
    ps: decodeUriValue(hashValue),
  })
}

export const vlessJsonToLink = (config: NodeConfig) => {
  const { id, add, port, ps, ...rest } = config
  const query = buildQueryString(rest, { ps: true })
  const hash = ps ? `${HASH_SEPARATOR}${encodeURIComponent(String(ps))}` : EMPTY_STRING
  return `${PROTOCOL_VLESS}${PROTOCOL_SEPARATOR}${id}${AT_SEPARATOR}${add}${COLON_SEPARATOR}${port}${
    query ? `${QUERY_SEPARATOR}${query}` : EMPTY_STRING
  }${hash}`
}

const parseSsUserInfo = (value: string) => {
  const decodedValue = decodeUriValue(value)
  const directValue = decodedValue.includes(COLON_SEPARATOR)
    ? decodedValue
    : safeBase64Decode(decodedValue)
  const separatorIndex = directValue.indexOf(COLON_SEPARATOR)
  if (separatorIndex === -1) {
    throw new Error('invalid ss user info')
  }
  return {
    method: directValue.slice(0, separatorIndex),
    password: directValue.slice(separatorIndex + 1),
  }
}

const parseSsAuthority = (authority: string) => {
  if (authority.includes(AT_SEPARATOR)) {
    const [userInfo, hostPort] = splitLast(authority, AT_SEPARATOR)
    return {
      ...parseSsUserInfo(userInfo),
      ...parseHostPort(hostPort),
    }
  }

  const decodedAuthority = safeBase64Decode(authority)
  const separatorIndex = decodedAuthority.lastIndexOf(AT_SEPARATOR)
  if (separatorIndex === -1) {
    throw new Error('invalid ss authority')
  }
  const userInfo = decodedAuthority.slice(0, separatorIndex)
  const hostPort = decodedAuthority.slice(separatorIndex + 1)

  return {
    ...parseSsUserInfo(userInfo),
    ...parseHostPort(hostPort),
  }
}

export const ssLinkToJson = (link: string) => {
  const rawValue = link.slice(`${PROTOCOL_SS}${PROTOCOL_SEPARATOR}`.length)
  const [content, hashValue] = splitOnce(rawValue, HASH_SEPARATOR)
  const [authorityWithMaybePath, queryValue] = content.includes(SS_AUTHORITY_QUERY_SEPARATOR)
    ? splitOnce(content, SS_AUTHORITY_QUERY_SEPARATOR)
    : splitOnce(content, QUERY_SEPARATOR)
  const normalizedAuthority = authorityWithMaybePath.endsWith(SLASH)
    ? authorityWithMaybePath.slice(0, -1)
    : authorityWithMaybePath

  return normalizeNodeConfig({
    ...parseSsAuthority(normalizedAuthority),
    ...parseQueryParams(queryValue),
    ps: decodeUriValue(hashValue),
  })
}

export const ssJsonToLink = (config: NodeConfig) => {
  const { add, port, ps, method, password, ...rest } = config
  const encodedUserInfo = toUrlSafeBase64(`${method}:${password}`)
  const query = buildQueryString(rest, SS_CORE_FIELD_MAP)
  const queryPrefix = query ? SS_QUERY_PREFIX : EMPTY_STRING
  const hash = ps ? `${HASH_SEPARATOR}${encodeURIComponent(String(ps))}` : EMPTY_STRING

  return `${PROTOCOL_SS}${PROTOCOL_SEPARATOR}${encodedUserInfo}${AT_SEPARATOR}${add}${COLON_SEPARATOR}${port}${queryPrefix}${query}${hash}`
}

export const parseNodeLine = (line: string): ParsedNode | null => {
  const normalizedLine = line.trim()
  if (!normalizedLine || !normalizedLine.includes(PROTOCOL_SEPARATOR)) {
    return null
  }

  try {
    if (normalizedLine.startsWith(`${PROTOCOL_VMESS}${PROTOCOL_SEPARATOR}`)) {
      return [PROTOCOL_VMESS, vmessLinkToJson(normalizedLine)]
    }
    if (normalizedLine.startsWith(`${PROTOCOL_VLESS}${PROTOCOL_SEPARATOR}`)) {
      return [PROTOCOL_VLESS, vlessLinkToJson(normalizedLine)]
    }
    if (normalizedLine.startsWith(`${PROTOCOL_SS}${PROTOCOL_SEPARATOR}`)) {
      return [PROTOCOL_SS, ssLinkToJson(normalizedLine)]
    }
  } catch {
    return null
  }

  return null
}

export const parseNodeLines = (text: string) => {
  return text
    .split('\n')
    .map(parseNodeLine)
    .filter(Boolean) as ParsedNode[]
}

export const serializeNode = ([protocol, config]: ParsedNode) => {
  if (protocol === PROTOCOL_VMESS) {
    return vmessJsonToLink(config)
  }
  if (protocol === PROTOCOL_VLESS) {
    return vlessJsonToLink(config)
  }
  return ssJsonToLink(config)
}

export const serializeNodeLines = (nodes: ParsedNode[]) => {
  return nodes.map(serializeNode).join('\n')
}

export const stripPathQuery = (path?: string) => {
  return path?.split(QUERY_SEPARATOR)[0]
}

export const getClipboardText = async () => {
  try {
    const text = await navigator.clipboard.readText()
    return text
  } catch (error) {
    console.error('Failed to read clipboard contents: ', error)
    return EMPTY_STRING
  }
}

export function getRandom<T = any>(arr: T[], m: number) {
  const nArray = arr.concat()
  const n = arr.length

  if (n <= m) {
    return nArray
  }

  const resultArray = []

  for (let i = 0; i < m; i++) {
    const randomIndex = Math.floor(Math.random() * nArray.length)
    resultArray.push(nArray[randomIndex])
    nArray.splice(randomIndex, 1)
  }

  return resultArray
}
