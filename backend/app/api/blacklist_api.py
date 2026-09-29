"""Blacklist API — manage user's blacklist rules."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.db.models import User, BlacklistRule
from app.api.deps import require_user

router = APIRouter(prefix="/api/blacklist", tags=["blacklist"])

# The parsed rule set is rebuilt and evaluated against every post on every
# feed/search request, so both the number of rules and the size of each rule
# are bounded.
MAX_RULES_PER_USER = 500
MAX_RULE_LINE_LENGTH = 2000


class BlacklistRuleCreate(BaseModel):
    rule_line: str = Field(min_length=1, max_length=MAX_RULE_LINE_LENGTH)


class BlacklistRuleUpdate(BaseModel):
    is_active: Optional[bool] = None
    rule_line: Optional[str] = Field(default=None, min_length=1, max_length=MAX_RULE_LINE_LENGTH)


@router.get("")
async def list_rules(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """List rules, most recent first, with a stable secondary sort."""
    result = await db.execute(
        select(BlacklistRule)
        .where(BlacklistRule.user_id == user.id)
        .order_by(BlacklistRule.created_at.desc(), BlacklistRule.id.desc())
    )
    rules = result.scalars().all()
    return {
        "rules": [
            {
                "id": r.id,
                "rule_line": r.rule_line,
                "is_active": r.is_active,
            }
            for r in rules
        ]
    }


@router.post("", status_code=201)
async def add_rule(
    body: BlacklistRuleCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    rule_line = body.rule_line.strip()
    if not rule_line:
        raise HTTPException(status_code=422, detail="Rule line cannot be empty")

    count = await db.scalar(
        select(func.count(BlacklistRule.id)).where(BlacklistRule.user_id == user.id)
    )
    if (count or 0) >= MAX_RULES_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Blacklist rule limit reached ({MAX_RULES_PER_USER})",
        )

    rule = BlacklistRule(
        user_id=user.id,
        rule_line=rule_line,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id": rule.id, "message": "Rule added"}


@router.put("/{rule_id}")
async def update_rule(
    rule_id: int,
    body: BlacklistRuleUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BlacklistRule).where(
            BlacklistRule.id == rule_id, BlacklistRule.user_id == user.id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.is_active is not None:
        rule.is_active = body.is_active
    if body.rule_line is not None:
        rule_line = body.rule_line.strip()
        if not rule_line:
            raise HTTPException(status_code=422, detail="Rule line cannot be empty")
        rule.rule_line = rule_line
    await db.commit()
    return {"message": "Rule updated"}


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BlacklistRule).where(
            BlacklistRule.id == rule_id, BlacklistRule.user_id == user.id
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"message": "Rule deleted"}
