from syft_client.platforms.google_common.gmail import GmailTransportBase

_DEFAULT_PLATFORM_NAME = "google_org"


class GmailTransport(GmailTransportBase):
    def _get_platform_name(self) -> str:
        # TODO remove dynamic attrs and use a normal typed attribute for _platform_client, _platform_client.platform
        _platform_client = getattr(self, "_platform_client", None)
        if _platform_client is None:
            return _DEFAULT_PLATFORM_NAME

        return getattr(_platform_client, "platform", _DEFAULT_PLATFORM_NAME)
