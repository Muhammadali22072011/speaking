from fastapi import APIRouter

router = APIRouter()


@router.get("/audio/_stub")
async def stub() -> dict:
    return {"router": "audio", "status": "not implemented"}
