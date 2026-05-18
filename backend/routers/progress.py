from fastapi import APIRouter

router = APIRouter()


@router.get("/_stub")
async def stub() -> dict:
    return {"router": "progress", "status": "not implemented"}
