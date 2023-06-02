import { NextResponse } from 'next/server'

var body = {
  messages: [
    {
      role: 'system',
      content: 'You are an AI assistant that helps people find information.',
    },
    {
      role: 'user',
      content: '你是谁？',
    },
  ],
  max_tokens: 800,
  temperature: 0.7,
  frequency_penalty: 0,
  presence_penalty: 0,
  top_p: 0.95,
  stop: null,
}

export async function POST(request: Request) {
  const comingBody = await request.json()
  console.log('comingBody: ', comingBody)
  // request.headers.get('api-key')
  const apiKey = request.headers.get('api-key')
  if (apiKey?.length === 32) {
    const requestHeaders = new Headers()
    // requestHeaders.append('api-key', process.env.GPT_API_KEY || '')
    requestHeaders.append('User-Agent', 'Apifox/1.0.0 (https://www.apifox.cn)')
    requestHeaders.append('Content-Type', 'application/json')
    requestHeaders.append('Accept', '*/*')
    requestHeaders.append('Host', 'rinna-openai-test.openai.azure.com')
    requestHeaders.append('Connection', 'keep-alive')
    requestHeaders.append('api-key', apiKey)
    return fetch(
      'https://rinna-openai-test.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2023-03-15-preview',
      {
        method: 'POST',
        headers: requestHeaders,
        body: JSON.stringify({
          ...body,
          ...comingBody,
        }),
        redirect: 'follow',
      }
    )
      .then((response) => response.json())
      .then((json) => NextResponse.json(json))
      .catch((error) => NextResponse.json(error))
  } else {
    return NextResponse.error()
  }
}
