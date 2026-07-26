from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response

from app.embed import service as embed_service
from app.embed.widget_js import render_widget_js

router = APIRouter(prefix="/public/widget", tags=["public-widget"])


@router.get("/{widget_id}/config")
async def get_widget_config(widget_id: UUID):
    config = await embed_service.get_widget_config(str(widget_id))
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )
    return JSONResponse(content=config)


@router.get("/{widget_id}/widget.js")
async def get_widget_js(
    widget_id: UUID,
    v: int | None = Query(None),
):
    raw = await embed_service.get_raw_widget(str(widget_id))
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    active = raw.get("active", False)
    if not active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Widget has been deleted",
        )

    config = raw.get("config", {})
    js_version = raw.get("js_version", 1)
    js_content = render_widget_js(str(widget_id), config, js_version)

    return Response(
        content=js_content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )
