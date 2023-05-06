'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import * as ECharts from 'echarts'
import { useMemoizedFn } from 'ahooks'

function getShare(id: string) {
  return fetch('/api/share?id=' + id).then((res) => res.json())
}

const prepareSeries = (data: any) => {
  return [
    {
      data: data.pe.map((pe: number, index: number) => [
        data.date[index],
        pe > 0 ? pe : null,
      ]),
      name: data.name + ' pe',
      smooth: true,
      showSymbol: false,
      yAxisIndex: 0, // 指定使用第一个y轴
      type: 'line',
    },
    {
      data: data.price.map((price: string, index: number) => [
        data.date[index],
        price,
      ]),
      name: data.name + ' price',
      smooth: true,
      showSymbol: false,
      yAxisIndex: 1, // 指定使用第二个y轴
      type: 'line',
    },
  ]
}
const option = {
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'cross',
      label: {
        backgroundColor: '#6a7985',
      },
    },
  },
  xAxis: {
    splitLine: {
      show: false,
    },
    type: 'time',
  },
  yAxis: [
    {
      type: 'value',
      name: 'PE(TTM)',
      splitLine: {
        show: false,
      },
    },
    {
      type: 'value',
      name: 'Price',
      splitLine: {
        show: false,
      },
    },
  ],
  dataZoom: [
    {
      type: 'inside',
      start: 70,
      end: 100,
    },
    {
      handleIcon:
        'M8.7,3.3c-0.4-0.4-1-0.4-1.4,0L2.3,8.3c-0.4,0.4-0.4,1,0,1.4l1.1,1.1c0.4,0.4,1,0.4,1.4,0l4.3-4.3c0.4-0.4,0.4-1,0-1.4L8.7,3.3z M7.6,8.3L3.3,4l1.4-1.4l4.3,4.3L7.6,8.3z',
      handleSize: '80%',
      handleStyle: {
        color: '#fff',
        shadowBlur: 3,
        shadowColor: 'rgba(0, 0, 0, 0.6)',
        shadowOffsetX: 2,
        shadowOffsetY: 2,
      },
    },
  ],
}

const seriesMap = new Map<string, any[]>()
const PE = () => {
  const [id, setId] = useState('sh600519')
  const hasInit = useRef(false)
  const charts = useRef<ECharts.ECharts | null>(null)
  const [series, setSeries] = useState<any[]>([])

  useEffect(() => {
    if (hasInit.current) return
    hasInit.current = true
    const myChart = ECharts.init(
      document.getElementById('pe') as HTMLDivElement
    )
    myChart.setOption(option)
    charts.current = myChart
    getData()
  }, [])

  const getData = useMemoizedFn(() => {
    if (seriesMap.has(id)) {
      return
    }
    getShare(id).then((data) => {
      const newSeries = prepareSeries(data)
      seriesMap.set(id, newSeries)
      const nextSeries = series.concat(newSeries)
      setSeries((s) => s.concat(newSeries))
      charts.current?.setOption({
        series: nextSeries,
        legend: {
          data: nextSeries.map((s) => s.name),
        },
      })
    })
  })

  return (
    <div className='w-full h-full min-h-screen flex flex-col justify-center items-center'>
      <div className='flex flex-row justify-center items-center mb-3'>
        <input
          className='border-2 border-gray-300 h-10 px-5 pr-16 rounded-lg text-sm focus:outline-none'
          name='search'
          placeholder='Search'
          value={id}
          onChange={(e) => setId(e.target.value)}
        />
        <button
          className='bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded border-solid ml-3'
          onClick={getData}
        >
          Search
        </button>
      </div>
      {/* <h1 className='text-3xl font-bold mb-3'>PE:</h1> */}
      <div id='pe' style={{ width: 1000, height: 800 }}></div>
    </div>
  )
}

export default PE
