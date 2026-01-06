from typing import Any, List

GDRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


def listify(obj: Any) -> List[Any]:
    if isinstance(obj, list):
        return obj
    else:
        return [obj]


def gather_all_file_and_folder_ids_recursive(service, folder_id) -> List[str]:
    res = set([folder_id])
    query = f"'{folder_id}' in parents"
    results = (
        service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    )
    for item in results.get("files", []):
        if item["mimeType"] == GDRIVE_FOLDER_MIME_TYPE:
            nested_ids = gather_all_file_and_folder_ids_recursive(service, item["id"])
            res.update(nested_ids)
        else:
            res.add(item["id"])
    return list(res)
