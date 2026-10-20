// E2E-проверка запущенного стека (./ctl.sh start): API, каталог в браузере,
// идемпотентность и переживание падения реплик api/web.
// Запуск: NODE_PATH="$(npm root -g)" node e2e/check.mjs
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
const { chromium } = createRequire(import.meta.url)('playwright')

const env = Object.fromEntries(
  (() => { try { return readFileSync(new URL('../.env', import.meta.url), 'utf8') } catch { return '' } })()
    .split('\n').filter((l) => /^\w+=/.test(l)).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]),
)
const BASE = `http://127.0.0.1:${env.LB_PORT || 5218}`
const TOKEN = env.INTERNAL_TOKEN || 'change-me'

let failed = 0
const check = (cond, label) => { console.log(`${cond ? '✓' : '✗'} ${label}`); if (!cond) failed++ }

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 480, height: 800 } })

// Картинка товара — скриншот цветной плашки.
await page.setContent(`<div style="width:320px;height:200px;background:#C77D3A;color:#fff;
  font:bold 32px sans-serif;display:flex;align-items:center;justify-content:center">e2e</div>`)
const png = await page.locator('div').screenshot()

const name = `e2e-товар-${Date.now()}`
const create = async (key) => {
  const form = new FormData()
  form.set('name', name)
  form.set('idempotency_key', key)
  form.set('image', new Blob([png], { type: 'image/png' }), 'p.png')
  return fetch(`${BASE}/api/products`, { method: 'POST', body: form, headers: { 'X-Internal-Token': TOKEN } })
}

const noAuth = await fetch(`${BASE}/api/products`, { method: 'POST', body: new FormData() })
check(noAuth.status === 401, `POST без токена → 401 (${noAuth.status})`)

const key = `e2e:${Date.now()}`
const r1 = await create(key)
const p1 = await r1.json()
check(r1.status === 201 && p1.name === name, `POST /api/products → 201, id=${p1.id}`)
const p2 = await (await create(key)).json()
check(p2.id === p1.id, `повтор с тем же idempotency_key → тот же id (${p2.id})`)

const img = await fetch(`${BASE}${p1.image_url}`)
check(img.ok && img.headers.get('content-type') === 'image/png', `картинка из MinIO ${p1.image_url} → ${img.status}`)

const instances = new Set()
for (let i = 0; i < 10; i++) instances.add((await fetch(`${BASE}/api/products`)).headers.get('x-instance'))
check(instances.size >= 2, `запросы расходятся по репликам api: ${instances.size}`)

async function catalogShows(label) {
  await page.goto(BASE)
  const h1 = await page.locator('h1').innerText()
  const item = page.locator('[data-testid=product]', { hasText: name })
  const visible = await item.count() === 1
  const loaded = visible && await item.locator('img').evaluate((el) => el.complete && el.naturalWidth > 0)
  check(h1 === 'Каталог' && visible && loaded, `${label}: «Каталог», товар и картинка на месте`)
}
await catalogShows('браузер')
await page.screenshot({ path: new URL('catalog.png', import.meta.url).pathname })

// Отказоустойчивость: гасим по реплике api и web — каталог и API должны продолжать отвечать.
const victims = ['testtgbot-api-1', 'testtgbot-web-1']
execSync(`docker kill ${victims.join(' ')}`, { stdio: 'ignore' })
try {
  let ok = 0
  for (let i = 0; i < 10; i++) if ((await fetch(`${BASE}/api/products`)).ok) ok++
  check(ok === 10, `после kill ${victims.join(', ')}: API ${ok}/10`)
  let pages = 0
  for (let i = 0; i < 5; i++) if ((await fetch(BASE)).ok) pages++
  check(pages === 5, `после kill: страница каталога ${pages}/5`)
  await catalogShows('после kill')
} finally {
  execSync(`docker start ${victims.join(' ')}`, { stdio: 'ignore' })
}

await browser.close()
console.log(failed ? `\n${failed} проверок упало` : '\nвсё прошло')
process.exit(failed ? 1 : 0)
