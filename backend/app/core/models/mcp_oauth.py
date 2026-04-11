"""MCP OAuth models for dynamic client registration, auth codes, and refresh tokens."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MCPOAuthClientDB(Base):
    """Dynamic client registrations (RFC 7591)."""

    __tablename__ = "mcp_oauth_clients"

    client_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_secret: Mapped[str | None] = mapped_column(String(256))
    client_info: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MCPOAuthCodeDB(Base):
    """Authorization codes with PKCE (60-second TTL)."""

    __tablename__ = "mcp_oauth_codes"

    code: Mapped[str] = mapped_column(String(256), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"),
        nullable=False,
    )
    code_challenge: Mapped[str] = mapped_column(String(256), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri_provided_explicitly: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    scopes: Mapped[list[str] | None] = mapped_column(JSONB)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )
    user_email: Mapped[str | None] = mapped_column(String(255))
    user_roles: Mapped[list[str] | None] = mapped_column(JSONB)
    user_permissions: Mapped[list[str] | None] = mapped_column(JSONB)
    resource: Mapped[str | None] = mapped_column(Text)
    mcp_state: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MCPOAuthRefreshTokenDB(Base):
    """Refresh tokens (30-day default TTL)."""

    __tablename__ = "mcp_oauth_refresh_tokens"

    token: Mapped[str] = mapped_column(String(256), primary_key=True)
    client_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("mcp_oauth_clients.client_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )
    user_email: Mapped[str | None] = mapped_column(String(255))
    user_roles: Mapped[list[str] | None] = mapped_column(JSONB)
    user_permissions: Mapped[list[str] | None] = mapped_column(JSONB)
    scopes: Mapped[list[str] | None] = mapped_column(JSONB)
    resource: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
