from pathlib import Path
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator
from syft_client.syncv2.connections.connection_router import ConnectionRouter
from syft_client.syncv2.callback_mixin import BaseModelCallbackMixin
from syft_client.syncv2.messages.proposed_filechange import (
    ProposedFileChange,
    ProposedFileChangesMessage,
)
from syft_client.syncv2.sync.caches.datasite_watcher_cache import DataSiteWatcherCache


class DatasiteOutboxPuller(BaseModelCallbackMixin):
    connection_router: ConnectionRouter
    datasite_watcher_cache: DataSiteWatcherCache
