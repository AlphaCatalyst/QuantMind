"""Explicit transaction owner for the asynchronous Ledger Repository."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.shared.database_manager_v2 import DatabaseManager, get_db_manager

from .errors import LedgerTransactionError
from .postgres import PostgresLedgerRepository


SessionFactory = Callable[[], Awaitable[AsyncSession]]


class AsyncLedgerUnitOfWork:
    """Own exactly one Session and require an explicit terminal action."""

    def __init__(
        self,
        *,
        database_manager: DatabaseManager | None = None,
        session_factory: SessionFactory | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        sources = sum(value is not None for value in (database_manager, session_factory, session))
        if sources > 1:
            raise ValueError("choose exactly one Unit of Work Session source")
        self._manager = database_manager
        self._session_factory = session_factory
        self._injected_session = session
        self._owns_session = session is None
        self.session: AsyncSession | None = None
        self.repository: PostgresLedgerRepository | None = None
        self._entered = False
        self._finished = False

    async def __aenter__(self) -> "AsyncLedgerUnitOfWork":
        if self._entered:
            raise LedgerTransactionError("Unit of Work cannot be entered twice", entity_type="unit_of_work")
        self._entered = True
        if self._injected_session is not None:
            self.session = self._injected_session
        elif self._session_factory is not None:
            self.session = await self._session_factory()
        else:
            manager = self._manager or get_db_manager()
            self.session = await manager.create_master_session()
        self.repository = PostgresLedgerRepository(self.session, write_guard=self._ensure_writable)
        return self

    def _ensure_writable(self) -> None:
        if not self._entered or self._finished:
            raise LedgerTransactionError("Unit of Work is no longer writable", entity_type="unit_of_work")

    async def commit(self) -> None:
        self._ensure_writable()
        assert self.session is not None
        try:
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            self._finished = True
            raise LedgerTransactionError("Unit of Work commit failed", entity_type="unit_of_work") from exc
        self._finished = True

    async def rollback(self) -> None:
        self._ensure_writable()
        assert self.session is not None
        await self.session.rollback()
        self._finished = True

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        if self.session is None:
            return
        try:
            if not self._finished:
                await self.session.rollback()
                self._finished = True
        finally:
            if self._owns_session:
                await self.session.close()


def ledger_unit_of_work_factory(
    database_manager: DatabaseManager | None = None,
) -> AsyncLedgerUnitOfWork:
    return AsyncLedgerUnitOfWork(database_manager=database_manager or get_db_manager())
