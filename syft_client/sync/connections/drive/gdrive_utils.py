from typing import Any, List


def listify(obj: Any) -> List[Any]:
    if isinstance(obj, list):
        return obj
    else:
        return [obj]


def delete_folder_recursive(service, folder_id, raise_on_error=False, verbose=False):
    query = f"'{folder_id}' in parents"
    results = (
        service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    )
    for item in results.get("files", []):
        if item["mimeType"] == "application/vnd.google-apps.folder":
            print(f"Deleting subfolder: {item['name']}")
            try:
                delete_folder_recursive(service, item["id"])
            except Exception as e:
                if raise_on_error:
                    raise e
                else:
                    if verbose:
                        print(f"Error deleting subfolder: {item['name']}")
        else:
            print(f"Deleting file: {item['name']}")
            try:
                service.files().delete(fileId=item["id"]).execute()
            except Exception as e:
                if raise_on_error:
                    raise e
                else:
                    if verbose:
                        print(f"Error deleting file: {item['name']}")

    service.files().delete(fileId=folder_id).execute()
