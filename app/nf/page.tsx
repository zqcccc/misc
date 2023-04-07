import { GET } from '../api/nf/route'

const NF = async (req: any) => {
  console.log('%c req: ', 'font-size:12px;background-color: #2EAFB0;color:#fff;', req)
  // const data = await Promise.all(
  //   settles.map((params) => {
  //     return checkNetflix(...params)
  //   })
  // )
  const data = await GET()
  console.log(
    '%c data: ',
    'font-size:12px;background-color: #93C0A4;color:#fff;',
    data
  )

  return (
    <div className='w-full h-full min-h-screen flex flex-col justify-center items-center'>
      <h1 className='text-3xl font-bold mb-3'>Netflix status:</h1>
      {data.map(([isUnlock, countryStr], index) => (
        <p className='mb-3' key={index}>
          {isUnlock ? 'unlock' : 'lock'} - {countryStr}
        </p>
      ))}
    </div>
  )
}

export default NF
