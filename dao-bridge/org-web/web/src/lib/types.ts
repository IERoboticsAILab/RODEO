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
