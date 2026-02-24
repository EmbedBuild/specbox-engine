# Arquitectura React - Overview

## Stack Principal

| Tecnologia | Version | Proposito |
|------------|---------|-----------|
| React | 19.x | UI Library |
| Next.js | 15.x | Framework (App Router) |
| TypeScript | 5.x | Type safety |
| TanStack Query | 5.x | Server state |
| Zustand | 5.x | Client state |
| Tailwind CSS | 4.x | Styling |
| Zod | 3.x | Schema validation |
| react-hook-form | 7.x | Forms |

## Principios

### 1. Server Components por defecto

Todo componente es Server Component a menos que necesite:
- Event handlers (onClick, onChange)
- useState, useEffect, useReducer
- Browser APIs (window, localStorage)

Solo entonces usar `'use client'`.

### 2. App Router (NO Pages Router)

- Layouts compartidos con `layout.tsx`
- Loading states con `loading.tsx`
- Error boundaries con `error.tsx`
- Route groups con `(grupo)/`

### 3. Separacion clara

```
Server Components → Data fetching, SEO, static content
Client Components → Interactividad, formularios, estado local
Server Actions → Mutaciones (POST, PUT, DELETE)
API Routes → Webhooks, integraciones externas
```

## Estructura de Carpetas

```
src/
├── app/                    # App Router
│   ├── (auth)/             # Route group: auth
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── register/
│   │       └── page.tsx
│   ├── (dashboard)/        # Route group: authenticated
│   │   ├── layout.tsx      # Dashboard layout con sidebar
│   │   ├── page.tsx        # Dashboard home
│   │   └── {feature}/
│   │       ├── page.tsx
│   │       ├── [id]/
│   │       │   └── page.tsx
│   │       ├── loading.tsx
│   │       └── error.tsx
│   ├── api/                # API routes (webhooks)
│   │   └── webhooks/
│   ├── layout.tsx          # Root layout
│   └── page.tsx            # Landing page
│
├── components/
│   ├── ui/                 # Primitivos reutilizables
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   └── data-table.tsx
│   └── features/           # Componentes de dominio
│       └── {feature}/
│           ├── {feature}-list.tsx
│           ├── {feature}-card.tsx
│           └── {feature}-form.tsx
│
├── hooks/                  # Custom hooks
│   ├── use-{feature}.ts   # Hook por feature (TanStack Query)
│   └── use-media-query.ts
│
├── lib/                    # Utilidades
│   ├── api-client.ts       # Fetch wrapper
│   ├── utils.ts            # Helpers
│   └── cn.ts               # className merger (clsx + twMerge)
│
├── services/               # External services
│   ├── supabase.ts
│   ├── stripe.ts
│   └── neon.ts
│
├── stores/                 # Zustand stores
│   └── use-{store}.ts
│
├── types/                  # TypeScript types
│   ├── {feature}.ts
│   └── api.ts
│
└── styles/
    └── globals.css         # Tailwind imports + custom tokens
```

## Patrones Clave

### Data Fetching (Server Components)

```tsx
// app/(dashboard)/products/page.tsx
import { getProducts } from '@/services/supabase';
import { ProductList } from '@/components/features/products/product-list';

export default async function ProductsPage() {
  const products = await getProducts();
  return <ProductList products={products} />;
}
```

### Client State (Zustand)

```tsx
// stores/use-sidebar-store.ts
import { create } from 'zustand';

interface SidebarStore {
  isOpen: boolean;
  toggle: () => void;
}

export const useSidebarStore = create<SidebarStore>((set) => ({
  isOpen: true,
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
}));
```

### Server State (TanStack Query)

```tsx
// hooks/use-products.ts
'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: () => fetch('/api/products').then(r => r.json()),
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProductInput) =>
      fetch('/api/products', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
  });
}
```

### Forms (react-hook-form + Zod)

```tsx
// components/features/products/product-form.tsx
'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const productSchema = z.object({
  name: z.string().min(1, 'Nombre requerido'),
  price: z.number().positive('Precio debe ser positivo'),
  description: z.string().optional(),
});

type ProductForm = z.infer<typeof productSchema>;

export function ProductForm({ onSubmit }: { onSubmit: (data: ProductForm) => void }) {
  const { register, handleSubmit, formState: { errors } } = useForm<ProductForm>({
    resolver: zodResolver(productSchema),
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('name')} />
      {errors.name && <span>{errors.name.message}</span>}
      {/* ... */}
    </form>
  );
}
```

## Reglas

1. **Server Components** por defecto, 'use client' solo cuando necesario
2. **TanStack Query** para server state, **Zustand** para client state
3. **Zod** para TODA validacion de datos
4. **Tailwind CSS** para estilos, NO styled-components
5. **TypeScript strict** siempre habilitado
6. Componentes UI en `components/ui/`, features en `components/features/`
7. Un hook custom por feature en `hooks/`
8. Server Actions para mutaciones simples, API Routes para webhooks

## Anti-Patrones

| Anti-Patron | Alternativa |
|-------------|-------------|
| `'use client'` en todo | Server Components por defecto |
| Redux en proyecto nuevo | Zustand + TanStack Query |
| fetch en useEffect | TanStack Query |
| Validacion manual | Zod schemas |
| CSS-in-JS (styled-components) | Tailwind CSS |
| Barrel exports (index.ts) | Imports directos |
