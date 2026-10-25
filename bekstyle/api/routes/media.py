import os
import logging
from pathlib import Path
from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from bekstyle.config import settings

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger("bekstyle")

MEDIA_DIR = Path(settings.DATA_DIR) / "media_cache"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

FALLBACK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">
  <rect width="100%" height="100%" fill="#111315"/>
  <rect x="20" y="20" width="360" height="360" rx="16" fill="#1A1D20" stroke="#26292E" stroke-width="2"/>
  <text x="50%" y="45%" text-anchor="middle" font-family="sans-serif" font-weight="900" font-size="28" fill="#F5F2E9">BEK STYLE</text>
  <rect x="140" y="200" width="120" height="6" rx="3" fill="#C7F464"/>
  <text x="50%" y="240" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#8E95A0">STREETWEAR &amp; CASUAL</text>
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
