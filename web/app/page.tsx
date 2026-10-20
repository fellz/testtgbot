type Product = { id: number; name: string; image_url: string }

// Каталог рендерится на каждый запрос: реплики не держат кэш, новый товар виден сразу.
export const dynamic = 'force-dynamic'

const API_URL = process.env.API_INTERNAL_URL ?? 'http://127.0.0.1:5218/api'

async function loadProducts(): Promise<Product[] | null> {
  try {
    const res = await fetch(`${API_URL}/products`, { cache: 'no-store' })
    if (!res.ok) return null
    return (await res.json()) as Product[]
  } catch {
    return null
  }
}

export default async function CatalogPage() {
  const products = await loadProducts()
  return (
    <main>
      <h1>Каталог</h1>
      {products === null ? (
        <p className="empty">Каталог временно недоступен.</p>
      ) : products.length === 0 ? (
        <p className="empty">Товаров пока нет.</p>
      ) : (
        <ul className="grid">
          {products.map((p) => (
            <li key={p.id} className="card" data-testid="product">
              <img src={p.image_url} alt={p.name} />
              <div className="name">{p.name}</div>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
