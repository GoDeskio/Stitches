from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from models import *

router = APIRouter()


# ---------------- Assets / Files ----------------
@router.post("/assets/upload")
async def upload_asset(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    await ensure_feature("assets")
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    path = f"{APP_NAME}/uploads/{user['user_id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type or "application/octet-stream")
    doc = {"asset_id": f"asset_{uuid.uuid4().hex[:12]}", "storage_path": result["path"],
           "original_filename": file.filename, "content_type": file.content_type,
           "size": result.get("size", len(data)), "owner_id": user["user_id"],
           "shared_with": [], "is_shared": False, "is_deleted": False, "created_at": now_iso()}
    await db.assets.insert_one(doc)
    await log_activity(user["user_id"], "asset_upload", {"name": file.filename})
    doc.pop("_id", None)
    return doc


@router.get("/assets")
async def list_assets(user: dict = Depends(get_current_user)):
    assets = await db.assets.find(
        {"is_deleted": False, "$or": [{"owner_id": user["user_id"]},
                                      {"shared_with": user["user_id"]}, {"is_shared": True}]},
        {"_id": 0}).sort("created_at", -1).to_list(500)
    return assets


@router.get("/assets/{asset_id}/download")
async def download_asset(asset_id: str, authorization: str = Header(None), auth: str = Query(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif auth:
        token = auth
    user = await resolve_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    record = await db.assets.find_one({"asset_id": asset_id, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="Asset not found")
    data, content_type = get_object(record["storage_path"])
    return FastResponse(content=data, media_type=record.get("content_type") or content_type,
                        headers={"Content-Disposition": f'inline; filename="{record["original_filename"]}"'})


@router.post("/assets/{asset_id}/share")
async def share_asset(asset_id: str, user: dict = Depends(get_current_user)):
    await db.assets.update_one({"asset_id": asset_id, "owner_id": user["user_id"]},
                               {"$set": {"is_shared": True}})
    a = await db.assets.find_one({"asset_id": asset_id}, {"_id": 0})
    return a


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, user: dict = Depends(get_current_user)):
    await db.assets.update_one({"asset_id": asset_id, "owner_id": user["user_id"]},
                               {"$set": {"is_deleted": True}})
    return {"ok": True}


