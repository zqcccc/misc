export function formatReadingTime(minutes: number) {
  minutes = Math.round(minutes)
  let cups = Math.round(minutes / 5)
  let bowls = 0
  if (cups > 5) {
    return `${new Array(Math.round(cups / Math.E))
      .fill('🍱')
      .join('')} ${minutes} min read`
  } else {
    return `${new Array(cups || 1).fill('☕️').join('')} ${minutes} min read`
  }
}

// `lang` is optional and will default to the current user agent locale
export function formatPostDate(date: string, lang: string) {
  if (typeof Date.prototype.toLocaleDateString !== 'function') {
    return date
  }

  const d = new Date(date)
  const args = [
    lang,
    { day: 'numeric', month: 'long', year: 'numeric' },
  ].filter(Boolean) as any
  return d.toLocaleDateString(...args)
}

function createFakeElement(value) {
  const isRTL = document.documentElement.getAttribute('dir') === 'rtl'
  const fakeElement = document.createElement('textarea')
  // Prevent zooming on iOS
  fakeElement.style.fontSize = '12pt'
  // Reset box model
  fakeElement.style.border = '0'
  fakeElement.style.padding = '0'
  fakeElement.style.margin = '0'
  // Move element out of screen horizontally
  fakeElement.style.position = 'absolute'
  fakeElement.style[isRTL ? 'right' : 'left'] = '-9999px'
  // Move element to the same position vertically
  const yPosition = window.pageYOffset || document.documentElement.scrollTop
  fakeElement.style.top = `${yPosition}px`

  fakeElement.setAttribute('readonly', '')
  fakeElement.value = value

  return fakeElement
}

function select(element) {
  const isReadOnly = element.hasAttribute('readonly')
  if (!isReadOnly) {
    element.setAttribute('readonly', '')
  }
  element.select()
  element.setSelectionRange(0, element.value.length)
  if (!isReadOnly) {
    element.removeAttribute('readonly')
  }

  return element.value
}

export function copy(content: any) {
  const toCopy = createFakeElement(content)
  document.documentElement.appendChild(toCopy)
  select(toCopy)

  document.execCommand('copy')
  toCopy.remove()
}
