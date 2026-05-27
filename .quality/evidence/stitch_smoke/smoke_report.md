# Stitch Native Chain Smoke Test — 2026-05-26T23:39:52Z

**Verdict**: `partial`

## Steps

| # | Step | Status | HTTP | Duration | Notes |
|---|------|--------|------|----------|-------|
| 1 | `list_projects` | ok | 200 | 1545ms | {"project_count":30} |
| 2 | `create_project` | ok | 200 | 1633ms | {"project_name":"projects/8968909107061645047","title":"SmokeTest-NativeChain-1779838793"} |
| 3 | `upload_design_md_batchCreate` | ok | 200 | 4420ms | {"design_md_size_bytes":1462,"response_keys":["results","screenInstances"]} |
| 4 | `get_project_screens` | ok | 200 | 1738ms | {"screen_instances_count":1,"instance_types":[]} |
| 5 | `list_design_systems_pre` | ok | 404 | 206ms | {"design_systems_count_pre":0} |
| 6 | `create_design_system_from_design_md` | error | None | 735ms | RuntimeError: create_design_system_from_design_md: all candidate paths returned non-2xx |
| 7 | `cleanup_delete_project` | warn | 403 | 2511ms | {"deleted":false,"code":403} |

## Raw excerpts

### upload_design_md_batchCreate
```
{
  "results": [
    {
      "screen": {
        "htmlCode": {
          "name": "projects/8968909107061645047/files/12517139344046392614",
          "downloadUrl": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBKNARIhYXBwX2NvbXBhbmlvbl91c2VyX3VwbG9hZGVkX2ZpbGVzGmgKM3VzZXJfdXBsb2FkZWRfaHRtbF8wMDA2NTJjMTAzNDc2NmQ2MDQ3OWM5MjMwNDE5ODZiYhILEgcQ_faDkPoEGAGSASMKCnByb2plY3RfaWQSFUITODk2ODkwOTEwNzA2MTY0NTA0Nw&filename=&opi=96797242",
          "mimeType": "text/markdown"
        },
        "id": "12517139344046393767",
        "width": "780",
        "height": "1768",
        "title": "SmokeTest DESIGN.md",
        "name": "projects/8968909107061645047/screens/12517139344046393767",
        "theme": {},
        "screenType": "DOCUMENT",
        "isCreatedByClient": true,
        "screenMetadata": {
          "status": "COMPLETE",
          "displayMode": "MARKDOWN"
        }
      }
    }
  ],
  "screenInstances": [
    {
      "id": "12517139344046393767",
      "sourceScreen": "projects/8968909107061645047/screens/12517139344046393767",
      "width": 390,
      "height": 884
    }
  ]
}
```

### get_project_screens
```
[
  {
    "id": "12517139344046393767",
    "sourceScreen": "projects/8968909107061645047/screens/12517139344046393767",
    "width": 390,
    "height": 884
  }
]
```

### create_design_system_from_design_md
```
[
  {
    "path": "/v1/projects/8968909107061645047/designSystems:createFromDesignMd",
    "code": 404,
    "body_preview": ""
  },
  {
    "path": "/v1/projects/8968909107061645047:createDesignSystemFromDesignMd",
    "code": 404,
    "body_preview": ""
  },
  {
    "path": "/v1/projects/8968909107061645047/designSystems",
    "code": 404,
    "body_preview": ""
  }
]
```

### cleanup_delete_project
```
{'error': {'code': 403, 'message': 'The caller does not have permission', 'status': 'PERMISSION_DENIED'}}
```
