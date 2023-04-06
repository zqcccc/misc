const NF = async () => {
  const data = await fetch(process.env.TEST_ENDPOINT as string, {
    cache: 'no-store',
  })

  const text = await data.text().then((text) => {
    console.log(
      '%c text: ',
      'font-size:12px;background-color: #A8978E;color:#fff;',
      text
    )
    return text
  })

  return <div>text from server:{text}</div>
}

export default NF
