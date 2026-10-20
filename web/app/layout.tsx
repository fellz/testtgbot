import Script from 'next/script'
import type { ReactNode } from 'react'
import { TelegramInit } from './telegram-init'
import './globals.css'

export const metadata = { title: 'Каталог' }

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <head>
        {/* SDK Mini App; в обычном браузере просто ничего не делает */}
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
      </head>
      <body>
        <TelegramInit />
        {children}
      </body>
    </html>
  )
}
