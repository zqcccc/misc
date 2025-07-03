import React from 'react'

const NF = async () => {
  let data: [boolean, string][] | null = null
  try {
    const res = await fetch('/api/nf', { cache: 'no-store' })
    data = await res.json()
  } catch (err) {
    // ignore
  }

  return (
    <div className='w-full h-full min-h-screen flex flex-col justify-center items-center'>
      <h1 className='text-3xl font-bold mb-3'>Netflix status:</h1>
      {data
        ? data.map(([isUnlock, countryStr], index) => (
            <p className='mb-3' key={index}>
              {isUnlock ? 'unlock' : 'lock'} - {countryStr}
            </p>
          ))
        : 'request error, maybe your server can not access netflix.com'}
    </div>
  )
}

export default NF
