from fastapi import APIRouter, HTTPException, Query

from ..db import db_conn
from ..repo import create_selector, get_selector, list_selectors, update_selector
from ..schemas import Platform, SelectorCreate, SelectorOut, SelectorUpdate


router = APIRouter(tags=["selectors"])


@router.get("/selectors", response_model=list[SelectorOut])
def selectors_list(
    platform: Platform | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with db_conn() as conn:
        rows = list_selectors(conn, platform.value if platform else None, limit, offset)
    return rows


@router.post("/selectors", response_model=SelectorOut, status_code=201)
def selectors_create(payload: SelectorCreate):
    data = payload.model_dump(mode="json")
    with db_conn() as conn:
        created = create_selector(conn, data["platform"], data["name"], data["selectors"])
    return created


@router.get("/selectors/{selector_id}", response_model=SelectorOut)
def selectors_get(selector_id: str):
    with db_conn() as conn:
        selector = get_selector(conn, selector_id)
    if not selector:
        raise HTTPException(status_code=404, detail="Selector not found")
    return selector


@router.patch("/selectors/{selector_id}", response_model=SelectorOut)
def selectors_update(selector_id: str, payload: SelectorUpdate):
    data = payload.model_dump(exclude_unset=True, mode="json")
    with db_conn() as conn:
        selector = get_selector(conn, selector_id)
        if not selector:
            raise HTTPException(status_code=404, detail="Selector not found")
        updated = update_selector(
            conn,
            selector_id,
            data.get("name"),
            data.get("selectors"),
        )
    return updated
