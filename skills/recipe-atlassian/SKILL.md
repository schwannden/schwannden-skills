---
name: recipe-atlassian
description: >
  Direct REST API recipes for Jira Cloud and Confluence Cloud via curl.
  Use when any skill or task needs to read or write Jira issues, Confluence pages,
  comments, attachments, or labels without an MCP server or SDK. Covers auth,
  JQL/CQL search, issue and page CRUD, transitions, links, sprints, and attachments.
---

# Atlassian REST API Recipes

Direct `curl` calls via the Bash tool. No MCP server, no SDK, no wrapper scripts.

Throughout, replace placeholders with your own values: `PROJ` (your Jira project key), `user@example.com` (a real account), and the `customfield_XXXXX` IDs (these are instance-specific — see "Discovering custom field IDs" below).

## Authentication

Both Jira and Confluence use Basic auth with an API token (create one at
https://id.atlassian.com/manage-profile/security/api-tokens). Export these
environment variables before running the recipes:

```bash
export JIRA_USERNAME="user@example.com"
export JIRA_API_TOKEN="<your-api-token>"
export JIRA_URL="https://your-org.atlassian.net"

export CONFLUENCE_USERNAME="user@example.com"
export CONFLUENCE_API_TOKEN="<your-api-token>"   # same token works
export CONFLUENCE_URL="https://your-org.atlassian.net/wiki"
```

```bash
# Jira
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/..."

# Confluence
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -H "Accept: application/json" \
  "${CONFLUENCE_URL}/api/v2/..."
```

Always use `-s` (silent) to suppress progress bars. Add `-w "\n%{http_code}"` when you need to check the status code.

**URL format note:** `JIRA_URL` includes the scheme and domain (e.g., `https://your-org.atlassian.net`). `CONFLUENCE_URL` includes the scheme, domain, AND `/wiki` suffix (e.g., `https://your-org.atlassian.net/wiki`). Do NOT add `/wiki/` again in Confluence paths.

**Never commit your API token.** Keep it in an environment variable or secret store, not in scripts or version control.

---

## Jira Operations

All rich text fields (description, comment body) use **ADF** (Atlassian Document Format). See `references/adf-schema.md` for the full schema and examples.

### Search Issues (JQL)

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "jql": "project = PROJ AND status = Open",
    "maxResults": 50,
    "fields": ["summary", "status", "assignee"]
  }' \
  "${JIRA_URL}/rest/api/3/search/jql"
```

Pagination: response includes `nextPageToken`. Pass it in subsequent requests:
```json
{"jql": "...", "maxResults": 50, "nextPageToken": "TOKEN_FROM_PREVIOUS"}
```

Common JQL patterns:
- **By fix version (release)**: `project = PROJ AND fixVersion = "1.2.3"` or `fixVersion = 65903` (version ID)
- **By sprint**: `project = PROJ AND sprint = "Sprint 42"`
- **By component**: `project = PROJ AND component = Backend`
- **Exclude issue types**: `project = PROJ AND fixVersion = "1.2.3" AND issuetype != Sub-task`

### Get Single Version (by ID)

Use this when you already have a version ID (e.g., from a release URL):
```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/version/{versionId}"
```

Returns `id`, `name`, `released`, `releaseDate`, `projectId`.

### List Recent Project Versions

Lists versions ordered by most recent. For projects with many versions, prefer "Get Single Version" above when you have a specific ID.
```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/project/PROJ/version?orderBy=-sequence&maxResults=50"
```

Returns versions with `id`, `name`, `released`, `releaseDate`. Use the version `name` in JQL `fixVersion` queries. Paginate with `startAt` if needed.

### Create Version

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"name":"v1.2.0","projectId":10000,"released":false}' \
  "${JIRA_URL}/rest/api/3/version"
```

`projectId` is the numeric project ID (not the key). Look up via `GET /rest/api/3/project/PROJ` → `id`. Returns the new version with its assigned `id`.

### Add Related Work to a Version

Attaches a link to a Jira version. Useful to wire up a bidirectional Jira ↔ Confluence link for release notes — Jira's own "Create Release Notes in Confluence" UI flow uses this same endpoint with the `Communication` category.

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "Communication",
    "title": "https://your-confluence-page-url",
    "url":   "https://your-confluence-page-url"
  }' \
  "${JIRA_URL}/rest/api/3/version/{versionId}/relatedwork"
```

- `category` — `Communication` is what Jira's auto-flow uses for Confluence release-note pages. There's also a `Release notes` category but the auto-flow doesn't use it; match the auto-flow convention so entries show up in the same slot on the Jira release page.
- `title` — display label. Atlassian's auto-flow sets this to the URL itself (so it looks ugly but unambiguous); set it to whatever you want.
- HTTP 201 on success. Response includes `relatedWorkId` (use this for later delete/update).

To list / verify:
```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  "${JIRA_URL}/rest/api/3/version/{versionId}/relatedwork"
```

### Get Issue

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/issue/PROJ-12345?fields=summary,status,description,assignee,components"
```

### Create Issue

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "project": {"key": "PROJ"},
      "summary": "Issue title",
      "issuetype": {"name": "Task"},
      "components": [{"name": "Backend"}],
      "description": <ADF_DOCUMENT>
    }
  }' \
  "${JIRA_URL}/rest/api/3/issue"
```

Replace `<ADF_DOCUMENT>` with a valid ADF object. See `references/adf-schema.md`.

**Note on ADF-typed custom fields:** Some Jira instances make custom fields ADF-typed (rich text). These do NOT accept empty strings (`""`) — the API returns 400. Passing `null` fills them with the project default template. To clear one on create, pass an empty ADF document: `{"version": 1, "type": "doc", "content": []}`.

**Assignee**: Use `"assignee": {"accountId": "..."}` if you have the account ID, or look up the user first via search (see "User Lookup" below).

### Update Issue

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "summary": "Updated title"
    }
  }' \
  "${JIRA_URL}/rest/api/3/issue/PROJ-12345"
```

Only send fields you want to change. Absent fields are left unchanged. Returns `204 No Content` on success.

### Add Comment

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "body": <ADF_DOCUMENT>
  }' \
  "${JIRA_URL}/rest/api/3/issue/PROJ-12345/comment"
```

### Edit Comment

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X PUT \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "body": <ADF_DOCUMENT>
  }' \
  "${JIRA_URL}/rest/api/3/issue/PROJ-12345/comment/{commentId}"
```

### Get Transitions

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/issue/PROJ-12345/transitions"
```

Returns `{"transitions": [{"id": "31", "name": "Done", "to": {"name": "Done"}}, ...]}`.

### Transition Issue

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"transition": {"id": "31"}}' \
  "${JIRA_URL}/rest/api/3/issue/PROJ-12345/transitions"
```

### Link to Parent / Epic

Set the parent via update. Use the `parent` field (the epic-link custom field varies by instance):

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X PUT \
  -H "Content-Type: application/json" \
  -d '{"fields": {"parent": {"key": "PROJ-100"}}}' \
  "${JIRA_URL}/rest/api/3/issue/PROJ-12345"
```

### Create Issue Link

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "type": {"name": "Blocks"},
    "inwardIssue": {"key": "PROJ-100"},
    "outwardIssue": {"key": "PROJ-200"}
  }' \
  "${JIRA_URL}/rest/api/3/issueLink"
```

### Add Issues to Sprint (Agile API)

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"issues": ["PROJ-100", "PROJ-101"]}' \
  "${JIRA_URL}/rest/agile/1.0/sprint/{sprintId}/issue"
```

### Discovering custom field IDs

Custom field IDs (`customfield_XXXXX`) are unique per Jira instance. To find them:

```bash
# List all fields with their ids and names
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/field" | jq '.[] | {id, name}'

# Field options for a select/multiselect custom field
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/field/{fieldId}/context/{contextId}/option"

# Project-scoped create metadata (which fields a given issue type accepts)
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/issue/createmeta/PROJ/issuetypes/{issueTypeId}"
```

### User Lookup (for assignee accountId)

```bash
curl -s -u "${JIRA_USERNAME}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/user/search?query=user@example.com"
```

Returns an array of user objects with `accountId`.

---

## Confluence Operations

All page content uses **storage format** (Confluence XHTML) by default. See `references/storage-format.md` for the full element reference and examples. Use ADF (`atlas_doc_format`) only if a specific endpoint requires it.

### Search Pages (CQL)

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -H "Accept: application/json" \
  "${CONFLUENCE_URL}/rest/api/search?cql=type%3Dpage+AND+space%3DSPACEKEY+AND+title%3D%22Page+Title%22&limit=25"
```

CQL examples:
- `type=page AND space=SPACEKEY AND title="Exact Title"`
- `type=page AND space=SPACEKEY AND text~"search term"`

### Get Page

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -H "Accept: application/json" \
  "${CONFLUENCE_URL}/api/v2/pages/{pageId}?body-format=storage"
```

The response includes `version.number` (needed for updates) and `body.storage.value` (the page content).

### Create Page

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -X POST \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "spaceId": "SPACE_ID",
    "status": "current",
    "title": "Page Title",
    "parentId": "PARENT_PAGE_ID",
    "body": {
      "representation": "storage",
      "value": "<STORAGE_FORMAT_XHTML>"
    }
  }' \
  "${CONFLUENCE_URL}/api/v2/pages"
```

**Note**: `spaceId` is the numeric space ID, not the space key. To find it:
```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -H "Accept: application/json" \
  "${CONFLUENCE_URL}/api/v2/spaces?keys=SPACEKEY"
```

### Update Page

You **must** fetch the current version number first, then increment it.

```bash
# Step 1: Get current version
VERSION=$(curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  "${CONFLUENCE_URL}/api/v2/pages/{pageId}" | jq '.version.number')

# Step 2: Update with incremented version
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -X PUT \
  -H "Content-Type: application/json" \
  -d '{
    "id": "{pageId}",
    "status": "current",
    "title": "Page Title",
    "body": {
      "representation": "storage",
      "value": "<UPDATED_STORAGE_CONTENT>"
    },
    "version": {
      "number": '$((VERSION + 1))',
      "message": "Updated via API"
    }
  }' \
  "${CONFLUENCE_URL}/api/v2/pages/{pageId}"
```

### Upload Attachment

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -X PUT \
  -H "X-Atlassian-Token: nocheck" \
  -F "file=@/tmp/diagram.png" \
  -F "minorEdit=true" \
  "${CONFLUENCE_URL}/rest/api/content/{pageId}/child/attachment"
```

Uses the v1 API. The `X-Atlassian-Token: nocheck` header is required for multipart uploads.

If the attachment already exists (same filename), this creates a new version. If it doesn't exist, it creates it.

### Get Attachments

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -H "Accept: application/json" \
  "${CONFLUENCE_URL}/api/v2/pages/{pageId}/attachments?limit=25"
```

Response includes `title`, `id`, `version.number` for each attachment.

### Delete Attachment

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -X DELETE \
  "${CONFLUENCE_URL}/api/v2/attachments/{attachmentId}"
```

Returns `204 No Content` on success.

### Add Comment (Footer)

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "pageId": "{pageId}",
    "body": {
      "representation": "storage",
      "value": "<p>Comment text here</p>"
    }
  }' \
  "${CONFLUENCE_URL}/api/v2/footer-comments"
```

### Reply to Comment

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "representation": "storage",
      "value": "<p>Reply text</p>"
    }
  }' \
  "${CONFLUENCE_URL}/api/v2/footer-comments/{parentCommentId}/children"
```

### Get Page Children

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -H "Accept: application/json" \
  "${CONFLUENCE_URL}/api/v2/pages/{pageId}/children?limit=25"
```

### Add Label

```bash
curl -s -u "${CONFLUENCE_USERNAME}:${CONFLUENCE_API_TOKEN}" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '[{"prefix": "global", "name": "my-label"}]' \
  "${CONFLUENCE_URL}/rest/api/content/{pageId}/label"
```

---

## Error Reference

| Code | Meaning | Common Cause |
|------|---------|--------------|
| 400 | Bad Request | Invalid ADF structure, missing required field, malformed JSON |
| 401 | Unauthorized | Wrong credentials or expired API token |
| 403 | Forbidden | No permission on the project/space/issue |
| 404 | Not Found | Wrong issue key, page ID, or endpoint path |
| 409 | Conflict | Confluence version conflict (stale version number on update) |
| 429 | Rate Limited | Too many requests; `Retry-After` header indicates wait time |

When a request fails, read the response body — Atlassian returns detailed error messages in `{"errorMessages": [...], "errors": {...}}` (Jira) or `{"message": "...", "data": {...}}` (Confluence).

## Pagination

- **Jira search**: Token-based. Response includes `nextPageToken` when more results exist.
- **Jira other endpoints** (sprints, boards): Offset-based (`startAt`/`maxResults`).
- **Confluence v2**: Cursor-based. Response includes `_links.next` URL for the next page.
- **Confluence v1** (search, labels): Offset-based (`start`/`limit`).

## jq Dependency

These recipes use `jq` for JSON parsing (e.g., extracting version numbers). `jq` is standard on macOS and most Linux distributions. If unavailable, use `python3 -c "import json,sys; ..."` as a fallback.
