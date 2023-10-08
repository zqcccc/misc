export const getClipboardText = async () => {
  try {
    const text = await navigator.clipboard.readText()
    return text
  } catch (error) {
    console.error('Failed to read clipboard contents: ', error)
    return ''
  }
}
