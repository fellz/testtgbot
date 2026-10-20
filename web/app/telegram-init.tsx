'use client'

import { useEffect } from 'react'

type WebApp = { initData: string; ready(): void; expand(): void }

export function TelegramInit() {
  useEffect(() => {
    const tg = (window as { Telegram?: { WebApp?: WebApp } }).Telegram?.WebApp
    // initData пуст вне Telegram — тогда это обычный браузер.
    if (tg?.initData) {
      tg.ready()
      tg.expand()
    }
  }, [])
  return null
}
