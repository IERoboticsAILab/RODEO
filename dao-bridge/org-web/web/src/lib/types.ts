export type Task = {
  id: number
  description: string
  taskCategory: string
  taskType: string
  rewardWei: string
  creator: string
  status: number
  executor: string
  active: boolean
  proofURI: string
  verified: boolean
}

export type Service = {
  id: number
  name: string
  description: string
  serviceCategory: string
  serviceType: string
  priceWei: string
  creator: string
  active: boolean
  providerType: number
  busy: boolean
}

export type Contracts = {
  organization: string
  taskManager: string
  serviceManager: string
}

// GET /catalog: one entry per kind of active service (see backend/catalog.py)
export type ParamSpec = {
  type: "place" | "text" | "number"
  label: string
  optional: boolean
  default?: string | number
}

export type CatalogEntry = {
  key: string
  category: string
  taskType: string
  name: string
  summary: string
  robot: string
  structured: boolean
  minPriceWei: string
  minPriceIec: number
  pickPriceIec: number
  providers: number
  free: number
  params: Record<string, ParamSpec>
  places: Record<string, { label: string }>
}
