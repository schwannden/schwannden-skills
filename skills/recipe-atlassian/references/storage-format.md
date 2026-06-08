# Confluence Storage Format Reference

Confluence storage format is XHTML-based. This is the native format Confluence stores internally and the default for all API operations in `recipe-atlassian`.

## Contents

- Basic Elements
- Lists
- Tables
- Code Blocks
- Macros
- Images
- Complete Page Example
- Validation Rules

## Basic Elements

### Headings

```xml
<h1>Heading 1</h1>
<h2>Heading 2</h2>
<h3>Heading 3</h3>
```

### Paragraphs

```xml
<p>Paragraph text with <strong>bold</strong>, <em>italic</em>, and <code>inline code</code>.</p>
```

### Links

```xml
<p><a href="https://example.com">Link text</a></p>
```

### Line Break

```xml
<p>Line one<br/>Line two</p>
```

## Lists

### Bullet List

```xml
<ul>
  <li>Item one</li>
  <li>Item two</li>
</ul>
```

### Numbered List

```xml
<ol>
  <li>Step one</li>
  <li>Step two</li>
</ol>
```

### Nested List

```xml
<ul>
  <li>Parent item
    <ul>
      <li>Child item</li>
    </ul>
  </li>
</ul>
```

## Tables

```xml
<table data-layout="default">
  <colgroup><col style="width: 50%"/><col style="width: 50%"/></colgroup>
  <thead>
    <tr>
      <th><p>Column A</p></th>
      <th><p>Column B</p></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><p>Value 1</p></td>
      <td><p>Value 2</p></td>
    </tr>
  </tbody>
</table>
```

## Code Blocks

```xml
<ac:structured-macro ac:name="code" ac:schema-version="1">
  <ac:parameter ac:name="language">python</ac:parameter>
  <ac:plain-text-body><![CDATA[def hello():
    print("hi")]]></ac:plain-text-body>
</ac:structured-macro>
```

## Macros

### Table of Contents

Add at top of page when it has 3+ sections:

```xml
<ac:structured-macro ac:name="toc" ac:schema-version="1"/>
```

### Info / Note / Warning Panels

```xml
<ac:structured-macro ac:name="info" ac:schema-version="1">
  <ac:rich-text-body>
    <p>This is an info panel.</p>
  </ac:rich-text-body>
</ac:structured-macro>
```

Replace `info` with `note`, `warning`, or `tip` for different panel types.

### Expand (Collapsible Section)

```xml
<ac:structured-macro ac:name="expand" ac:schema-version="1">
  <ac:parameter ac:name="title">Click to expand</ac:parameter>
  <ac:rich-text-body>
    <p>Hidden content here.</p>
  </ac:rich-text-body>
</ac:structured-macro>
```

### Status Lozenge

```xml
<ac:structured-macro ac:name="status" ac:schema-version="1">
  <ac:parameter ac:name="title">IN PROGRESS</ac:parameter>
  <ac:parameter ac:name="colour">Blue</ac:parameter>
</ac:structured-macro>
```

Colours: `Grey`, `Red`, `Yellow`, `Blue`, `Green`.

### Mermaid Diagram (Attachment-Backed)

Requires a Mermaid macro app (e.g. "Mermaid Diagrams for Confluence") installed on the instance.

```xml
<ac:structured-macro ac:name="mermaid-cloud" ac:schema-version="1" data-layout="default">
  <ac:parameter ac:name="filename">Diagram Name</ac:parameter>
  <ac:parameter ac:name="revision">1</ac:parameter>
</ac:structured-macro>
```

Workflow:
1. Write Mermaid syntax to a local file named `<Descriptive Name>` (no extension)
2. Upload as attachment to the page
3. Confirm title and revision via get-attachments
4. Insert this macro with matching filename and revision

### Task List (Checkboxes)

```xml
<ac:task-list>
  <ac:task>
    <ac:task-status>incomplete</ac:task-status>
    <ac:task-body>Review the design document</ac:task-body>
  </ac:task>
  <ac:task>
    <ac:task-status>complete</ac:task-status>
    <ac:task-body>Set up the repository</ac:task-body>
  </ac:task>
</ac:task-list>
```

### Jira Issue Macro

```xml
<ac:structured-macro ac:name="jira" ac:schema-version="1">
  <ac:parameter ac:name="key">PROJ-12345</ac:parameter>
</ac:structured-macro>
```

## Images

### Inline Image (Attached)

```xml
<ac:image ac:align="center" ac:layout="center">
  <ri:attachment ri:filename="screenshot.png"/>
</ac:image>
```

### External Image

```xml
<ac:image>
  <ri:url ri:value="https://example.com/image.png"/>
</ac:image>
```

## Complete Page Example

```xml
<ac:structured-macro ac:name="toc" ac:schema-version="1"/>

<h2>Background</h2>
<p>This page documents the checkout service redesign.</p>

<h2>Architecture</h2>
<p>The system consists of three components:</p>
<ul>
  <li><strong>API Gateway</strong> — handles initial request routing</li>
  <li><strong>Order Service</strong> — manages order state</li>
  <li><strong>Payment Service</strong> — processes payments</li>
</ul>

<ac:structured-macro ac:name="mermaid-cloud" ac:schema-version="1" data-layout="default">
  <ac:parameter ac:name="filename">Checkout Flow Diagram</ac:parameter>
  <ac:parameter ac:name="revision">1</ac:parameter>
</ac:structured-macro>

<h2>Implementation Plan</h2>
<ac:task-list>
  <ac:task>
    <ac:task-status>complete</ac:task-status>
    <ac:task-body>Design the API gateway routes</ac:task-body>
  </ac:task>
  <ac:task>
    <ac:task-status>incomplete</ac:task-status>
    <ac:task-body>Implement order service</ac:task-body>
  </ac:task>
</ac:task-list>

<h2>API Reference</h2>
<table data-layout="default">
  <colgroup><col style="width: 33%"/><col style="width: 33%"/><col style="width: 34%"/></colgroup>
  <thead>
    <tr>
      <th><p>Endpoint</p></th>
      <th><p>Method</p></th>
      <th><p>Description</p></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><p><code>/api/v1/orders</code></p></td>
      <td><p>POST</p></td>
      <td><p>Create an order</p></td>
    </tr>
  </tbody>
</table>
```

## Validation Rules

- All tags must be properly closed (XHTML, not HTML5)
- Macro parameter values must not contain unescaped `<`, `>`, `&` — use `&lt;`, `&gt;`, `&amp;`
- `ac:plain-text-body` content should use `<![CDATA[...]]>` for code blocks
- `ac:rich-text-body` can contain any standard storage-format elements
- Empty paragraphs (`<p/>` or `<p></p>`) are valid and render as blank lines
```
