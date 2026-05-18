from fastapi import APIRouter

router = APIRouter()


@router.get("/_stub_scoring")
async def stub() -> dict:
    return {"router": "scoring", "status": "not implemented"}
