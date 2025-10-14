# TODO remove redirected import and use google_common directly.
# TODO remove dynamic importing (__import__(...)) in syft_client and use static imports instead

from syft_client.platforms.google_common.gdrive_files import (
    GDriveFilesTransport,  # noqa F401
)
