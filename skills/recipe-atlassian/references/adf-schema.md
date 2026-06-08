# Atlassian Document Format (ADF) Reference

Jira Cloud API v3 requires ADF for all rich text fields (`description`, `comment.body`). ADF is a JSON document model.

## Contents

- Document Structure
- Block Nodes
- Inline Nodes
- Available Marks
- Complete Example
- Nested Lists
- Validation Rules

## Document Structure

Every ADF document has this wrapper:

```json
{
  "version": 1,
  "type": "doc",
  "content": [ ...block nodes... ]
}
```

## Block Nodes

### Paragraph

```json
{
  "type": "paragraph",
  "content": [ ...inline nodes... ]
}
```

### Heading

```json
{
  "type": "heading",
  "attrs": {"level": 2},
  "content": [{"type": "text", "text": "Section Title"}]
}
```

Levels: 1–6.

### Bullet List

```json
{
  "type": "bulletList",
  "content": [
    {
      "type": "listItem",
      "content": [
        {
          "type": "paragraph",
          "content": [{"type": "text", "text": "Item one"}]
        }
      ]
    },
    {
      "type": "listItem",
      "content": [
        {
          "type": "paragraph",
          "content": [{"type": "text", "text": "Item two"}]
        }
      ]
    }
  ]
}
```

### Ordered List

Same structure as `bulletList` but with `"type": "orderedList"`.

### Code Block

```json
{
  "type": "codeBlock",
  "attrs": {"language": "python"},
  "content": [{"type": "text", "text": "def hello():\n    print('hi')"}]
}
```

The `language` attr is optional.

### Blockquote

```json
{
  "type": "blockquote",
  "content": [
    {
      "type": "paragraph",
      "content": [{"type": "text", "text": "Quoted text"}]
    }
  ]
}
```

### Rule (Horizontal Line)

```json
{"type": "rule"}
```

### Table

```json
{
  "type": "table",
  "attrs": {"isNumberColumnEnabled": false, "layout": "default"},
  "content": [
    {
      "type": "tableRow",
      "content": [
        {
          "type": "tableHeader",
          "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Column A"}]}]
        },
        {
          "type": "tableHeader",
          "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Column B"}]}]
        }
      ]
    },
    {
      "type": "tableRow",
      "content": [
        {
          "type": "tableCell",
          "content": [{"type": "paragraph", "content": [{"type": "text", "text": "value 1"}]}]
        },
        {
          "type": "tableCell",
          "content": [{"type": "paragraph", "content": [{"type": "text", "text": "value 2"}]}]
        }
      ]
    }
  ]
}
```

### Panel

```json
{
  "type": "panel",
  "attrs": {"panelType": "info"},
  "content": [
    {
      "type": "paragraph",
      "content": [{"type": "text", "text": "Info panel content"}]
    }
  ]
}
```

Panel types: `info`, `note`, `warning`, `success`, `error`.

### Expand (Collapsible Section)

```json
{
  "type": "expand",
  "attrs": {"title": "Click to expand"},
  "content": [
    {
      "type": "paragraph",
      "content": [{"type": "text", "text": "Hidden content"}]
    }
  ]
}
```

## Inline Nodes

### Text

```json
{"type": "text", "text": "Plain text"}
```

### Text with Marks (Formatting)

```json
{"type": "text", "text": "Bold text", "marks": [{"type": "strong"}]}
```

```json
{"type": "text", "text": "Bold italic", "marks": [{"type": "strong"}, {"type": "em"}]}
```

### Hard Break

```json
{"type": "hardBreak"}
```

### Inline Code

```json
{"type": "text", "text": "some_var", "marks": [{"type": "code"}]}
```

### Link

```json
{
  "type": "text",
  "text": "Click here",
  "marks": [{"type": "link", "attrs": {"href": "https://example.com"}}]
}
```

### Mention

```json
{
  "type": "mention",
  "attrs": {"id": "accountId", "text": "@User Name"}
}
```

### Emoji

```json
{
  "type": "emoji",
  "attrs": {"shortName": ":thumbsup:", "id": "1f44d"}
}
```

### Status Lozenge

```json
{
  "type": "status",
  "attrs": {"text": "IN PROGRESS", "color": "blue"}
}
```

Colors: `neutral`, `purple`, `blue`, `red`, `yellow`, `green`.

### Date

```json
{
  "type": "date",
  "attrs": {"timestamp": "1712620800000"}
}
```

### Inline Card (Smart Link)

```json
{
  "type": "inlineCard",
  "attrs": {"url": "https://your-org.atlassian.net/browse/PROJ-100"}
}
```

## Available Marks

| Mark | Effect | Extra Attrs |
|------|--------|-------------|
| `strong` | **Bold** | — |
| `em` | *Italic* | — |
| `code` | `Inline code` | — |
| `strike` | ~~Strikethrough~~ | — |
| `underline` | Underline | — |
| `link` | Hyperlink | `{"href": "url"}` |
| `textColor` | Colored text | `{"color": "#ff0000"}` |
| `subsup` | Sub/superscript | `{"type": "sub"}` or `{"type": "sup"}` |

Multiple marks can be applied to the same text node.

## Complete Example

A typical Jira issue description:

```json
{
  "version": 1,
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": {"level": 2},
      "content": [{"type": "text", "text": "Background"}]
    },
    {
      "type": "paragraph",
      "content": [
        {"type": "text", "text": "The "},
        {"type": "text", "text": "login endpoint", "marks": [{"type": "code"}]},
        {"type": "text", "text": " currently returns 500 when the user's email contains a "},
        {"type": "text", "text": "+", "marks": [{"type": "code"}]},
        {"type": "text", "text": " character."}
      ]
    },
    {
      "type": "heading",
      "attrs": {"level": 2},
      "content": [{"type": "text", "text": "Task"}]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            {
              "type": "paragraph",
              "content": [{"type": "text", "text": "URL-encode the email parameter before passing to the auth backend"}]
            }
          ]
        },
        {
          "type": "listItem",
          "content": [
            {
              "type": "paragraph",
              "content": [{"type": "text", "text": "Add regression test for emails with special characters"}]
            }
          ]
        }
      ]
    },
    {
      "type": "heading",
      "attrs": {"level": 2},
      "content": [{"type": "text", "text": "Acceptance Criteria"}]
    },
    {
      "type": "orderedList",
      "content": [
        {
          "type": "listItem",
          "content": [
            {
              "type": "paragraph",
              "content": [{"type": "text", "text": "Users with + in email can log in successfully"}]
            }
          ]
        },
        {
          "type": "listItem",
          "content": [
            {
              "type": "paragraph",
              "content": [{"type": "text", "text": "No regression in standard email login flow"}]
            }
          ]
        }
      ]
    }
  ]
}
```

## Nested Lists

To nest a list inside a list item, add both the paragraph and the sub-list as children of the `listItem`:

```json
{
  "type": "listItem",
  "content": [
    {
      "type": "paragraph",
      "content": [{"type": "text", "text": "Parent item"}]
    },
    {
      "type": "bulletList",
      "content": [
        {
          "type": "listItem",
          "content": [
            {
              "type": "paragraph",
              "content": [{"type": "text", "text": "Child item"}]
            }
          ]
        }
      ]
    }
  ]
}
```

## Validation Rules

- The root must be `{"version": 1, "type": "doc", "content": [...]}`
- `content` arrays must not be empty (use at least one node)
- `listItem` must be a direct child of `bulletList` or `orderedList`
- `tableRow` must be a direct child of `table`
- `tableCell`/`tableHeader` must be a direct child of `tableRow`
- Text nodes cannot be empty strings — omit the node instead
- Block nodes cannot appear inside inline positions
