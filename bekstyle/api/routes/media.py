import os
import logging
from pathlib import Path
from fastapi import APIRouter, Response, Depends, HTTPException
from fastapi.responses import FileResponse

from bekstyle.config import settings
from bekstyle.api.auth import TelegramUser, get_current_user
from bekstyle.db import Order, get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger("bekstyle")

MEDIA_DIR = Path(settings.DATA_DIR) / "media_cache"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

RECEIPTS_DIR = Path(settings.DATA_DIR) / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/receipts/{filename}")
async def get_receipt_file(filename: str, user: TelegramUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    clean_name = Path(filename).name
    try:
        order_id = int(clean_name.split("_")[1])
    except (IndexError, ValueError):
        raise HTTPException(status_code=404, detail="Receipt not found")
    order = await db.get(Order, order_id)
    if not order or (order.user_id != user.id and not user.is_admin):
        raise HTTPException(status_code=404, detail="Receipt not found")
    if not order.receipt_url or order.receipt_url.rsplit("/", 1)[-1] != clean_name:
        raise HTTPException(status_code=404, detail="Chek topilmadi")
    private_headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                       "Content-Disposition": f'attachment; filename="{clean_name}"'}
    if order.receipt_bytes:
        return Response(content=order.receipt_bytes, media_type=order.receipt_content_type or "application/octet-stream", headers=private_headers)
    receipt_path = RECEIPTS_DIR / clean_name
    if receipt_path.is_file():
        return FileResponse(str(receipt_path), headers=private_headers)
    return Response(content="File not found", status_code=404)

FALLBACK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">
  <rect width="100%" height="100%" fill="#f0f3e9"/>
  <rect x="20" y="20" width="360" height="360" rx="16" fill="#f7f8f4" stroke="#dce5d3" stroke-width="2"/>
  <text x="50%" y="45%" text-anchor="middle" font-family="sans-serif" font-weight="900" font-size="28" fill="#173e30">BEK STYLE</text>
  <rect x="140" y="200" width="120" height="6" rx="3" fill="#8eab76"/>
  <text x="50%" y="240" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#89967c">Rasm tayyorlanmoqda</text>
</svg>"""


@router.get("/{file_id}")
async def get_media_file(file_id: str):
    clean_id = Path(file_id).name
    cached_path = MEDIA_DIR / clean_id
    if cached_path.is_file():
        return FileResponse(str(cached_path))

    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        alt = MEDIA_DIR / f"{clean_id}{ext}"
        if alt.is_file():
            return FileResponse(str(alt))

    # Try bot download if bot instance is available
    from bekstyle.api.server import bot_instance
    if bot_instance:
        try:
            tg_file = await bot_instance.get_file(file_id)
            if tg_file and tg_file.file_path:
                ext = Path(tg_file.file_path).suffix or ".jpg"
                save_dest = MEDIA_DIR / f"{clean_id}{ext}"
                await bot_instance.download_file(tg_file.file_path, destination=str(save_dest))
                if save_dest.is_file():
                    return FileResponse(str(save_dest))
        except Exception as e:
            logger.warning("Could not download file_id '%s': %s", file_id, e)

    return Response(content=FALLBACK_SVG, media_type="image/svg+xml")
