from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from org_code import (
    register_task, remove_task, activate_task, unassign_task, submit_proof_as_executor,
    register_service, activate_service, remove_service, set_service_busy,
    list_all_tasks, get_tasks_by_creator,
    list_all_services, get_services_by_creator,
    manager_addresses, ORG_CONTRACT_ADDR, Web3,
    list_iecoin_holders, IECOIN_ADDR,
    TOKEN_SYMBOL, TOKEN_DECIMALS,
    deposit_to_organization, iecoin, organization
)

app = FastAPI(title="Organization Console API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskCreate(BaseModel):
    description: str
    category: str
    taskType: str
    rewardIec: float = Field(gt=0)

class TaskId(BaseModel):
    taskId: int

class Proof(BaseModel):
    taskId: int
    proofURI: str

class ServiceCreate(BaseModel):
    name: str
    description: str
    category: str
    serviceType: str
    priceIec: float = Field(gt=0)

class ServiceId(BaseModel):
    serviceId: int

class Busy(BaseModel):
    index: int
    isBusy: bool

class DepositAmount(BaseModel):
    amountIec: float = Field(gt=0)

@app.get("/contracts")
def contracts() -> Dict[str, str]:
    return manager_addresses()

# ---------- Task reads ----------

@app.get("/tasks")
def tasks() -> List[Dict[str, Any]]:
    return list_all_tasks()

@app.get("/tasks/by-creator")
def tasks_by_creator(creator: str = ORG_CONTRACT_ADDR) -> List[Dict[str, Any]]:
    return get_tasks_by_creator(creator)

@app.get("/tasks/assigned-to-org")
def tasks_assigned_to_org() -> List[Dict[str, Any]]:
    rows = list_all_tasks()
    return [t for t in rows if t["active"] and t["status"] == 1 and t["executor"].lower() == ORG_CONTRACT_ADDR.lower()]

# ---------- Task writes ----------

@app.post("/tasks/register")
def tasks_register(body: TaskCreate) -> Dict[str, str]:
    try:
        tx = register_task(body.description, body.category, body.taskType, body.rewardIec)
        return {"txHash": tx}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/tasks/remove")
def tasks_remove(body: TaskId) -> Dict[str, str]:
    try:
        return {"txHash": remove_task(body.taskId)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/tasks/activate")
def tasks_activate(body: TaskId) -> Dict[str, str]:
    try:
        return {"txHash": activate_task(body.taskId)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/tasks/unassign")
def tasks_unassign(body: TaskId) -> Dict[str, str]:
    try:
        return {"txHash": unassign_task(body.taskId)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/tasks/submit-proof")
def tasks_submit_proof(body: Proof) -> Dict[str, str]:
    try:
        return {"txHash": submit_proof_as_executor(body.taskId, body.proofURI)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------- Service reads ----------

@app.get("/services")
def services() -> List[Dict[str, Any]]:
    return list_all_services()

@app.get("/services/by-creator")
def services_by_creator(creator: str = ORG_CONTRACT_ADDR) -> List[Dict[str, Any]]:
    return get_services_by_creator(creator)

# ---------- Service writes ----------

@app.post("/services/register")
def services_register(body: ServiceCreate) -> Dict[str, str]:
    try:
        return {"txHash": register_service(body.name, body.description, body.category, body.serviceType, body.priceIec)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/services/remove")
def services_remove(body: ServiceId) -> Dict[str, str]:
    try:
        return {"txHash": remove_service(body.serviceId)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/services/activate")
def services_activate(body: ServiceId) -> Dict[str, str]:
    try:
        return {"txHash": activate_service(body.serviceId)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/services/set-busy")
def services_set_busy(body: Busy) -> Dict[str, str]:
    try:
        return {"txHash": set_service_busy(body.index, body.isBusy)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.get("/token/holders")
def token_holders(startBlock: Optional[int] = None,
                  endBlock:   Optional[int] = None,
                  verify:     bool = True) -> Dict[str, Any]:
    """
    Return IECoin holders with nonzero balances.
    Query params:
      startBlock  optional, default uses iecoin_deploy_block from config or zero
      endBlock    optional, defaults to latest
      verify      if true, cross check with balanceOf
    """
    holders = list_iecoin_holders(start_block=startBlock, end_block=endBlock, verify_with_balance_of=verify)
    return {
        "token": {
            "address": IECOIN_ADDR,
            "symbol": TOKEN_SYMBOL,
            "decimals": TOKEN_DECIMALS,
        },
        "holders": holders,
    }

@app.get("/organization/balance")
def organization_balance() -> Dict[str, Any]:
    """Get Organization contract IEC balance and info"""
    try:
        org_balance = iecoin.functions.balanceOf(organization.address).call()
        tm_addr = organization.functions.taskManager().call()
        allowance = iecoin.functions.allowance(organization.address, tm_addr).call()
        
        web3 = Web3()
        return {
            "organizationAddress": organization.address,
            "taskManagerAddress": tm_addr,
            "balanceWei": str(org_balance),
            "balanceIec": float(web3.from_wei(org_balance, "ether")),
            "allowanceWei": str(allowance),
            "allowanceIec": float(web3.from_wei(allowance, "ether")),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/organization/deposit")
def organization_deposit(body: DepositAmount) -> Dict[str, str]:
    """Deposit IEC tokens into Organization contract for task funding"""
    try:
        return {"txHash": deposit_to_organization(body.amountIec)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))