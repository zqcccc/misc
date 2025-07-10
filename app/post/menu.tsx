import React from 'react'
import Link from 'next/link'

import './menu.css'

const Menu = () => {
  return (
    <ul className='menuList'>
      <li>
        <Link href='/'>home</Link>
      </li>
      <li>
        <Link href="/tools">Tools</Link>
      </li>
      <li>
        <Link href='/vmess'>Vmess(deprecated)</Link>
      </li>
      <li>
        <p>awesome collections</p>
        <p className='sub'>
          <a
            target='_blank'
            href='https://paveldogreat.github.io/WebGL-Fluid-Simulation/'
          >
            WebGL Fluid
          </a>
        </p>
      </li>
    </ul>
  )
}

export default Menu
