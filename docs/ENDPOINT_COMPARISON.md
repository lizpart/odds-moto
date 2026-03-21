# Endpoint Comparison Guide

When to use MD file endpoints vs messaging endpoints.

## Quick Decision Tree

```
Need file storage? → Use MD endpoints
Need JSON for bots? → Use messaging endpoints
Need detailed reports? → Use MD endpoints
Need fast responses? → Use messaging endpoints
```

## MD File Endpoints

### Use Cases

✅ **When to Use:**
- Storing match data as files
- Generating detailed reports
- File-based workflows
- Archiving match data
- Generating documentation
- Batch processing with file output

❌ **When NOT to Use:**
- Real-time bot responses
- Mobile applications
- Quick data lookups
- When you need structured JSON

### Characteristics

- **Response Type:** Markdown files
- **Size:** 10-50 KB per file
- **Format:** Text/Markdown
- **Speed:** Slower (file generation)
- **Structure:** Unstructured text

### Endpoints

- `/fixtures` - Match report MD files
- `/predict` - Analysis MD files
- `/analyze` - Complete workflow MD file
- `/batch` - Batch processing with file paths

---

## Messaging Endpoints

### Use Cases

✅ **When to Use:**
- WhatsApp/Telegram bots
- Mobile applications
- Real-time data display
- Quick lookups
- Structured data needs
- API integrations

❌ **When NOT to Use:**
- File storage needs
- Detailed documentation
- When you need full raw data

### Characteristics

- **Response Type:** Clean JSON
- **Size:** 1-5 KB per response
- **Format:** Structured JSON
- **Speed:** Fast (< 500ms)
- **Structure:** Type-safe objects

### Endpoints

- `/msg/fixtures` - Clean fixture JSON
- `/msg/analyze` - Clean prediction JSON
- `/msg/stats` - Clean stats JSON

---

## Side-by-Side Comparison

| Feature | MD Endpoints | Messaging Endpoints |
|---------|-------------|---------------------|
| **Response Format** | Markdown files | JSON |
| **Response Size** | 10-50 KB | 1-5 KB |
| **Response Time** | 2-5 seconds | < 500ms |
| **Data Structure** | Unstructured text | Structured objects |
| **Use Case** | File storage | Real-time apps |
| **Parsing Required** | Yes (text parsing) | No (direct use) |
| **Bot Friendly** | ❌ No | ✅ Yes |
| **File Storage** | ✅ Yes | ❌ No |
| **Type Safety** | ❌ No | ✅ Yes |

---

## Examples

### Scenario 1: Building a WhatsApp Bot

**Use:** Messaging endpoints

```python
# ✅ Good - Fast, clean JSON
response = requests.post(
    "http://localhost:8000/msg/fixtures",
    json={"date": "today"}
)
fixtures = response.json()["fixtures"]

# ❌ Bad - Slow, requires parsing
response = requests.post(
    "http://localhost:8000/fixtures",
    json={"date": "today"}
)
# Need to parse MD file content
```

### Scenario 2: Generating Match Reports

**Use:** MD endpoints

```python
# ✅ Good - Generates file for storage
response = requests.post(
    "http://localhost:8000/fixtures",
    json={"fixture_id": 1379137}
)
with open("match_report.md", "wb") as f:
    f.write(response.content)

# ❌ Bad - JSON not suitable for reports
response = requests.post(
    "http://localhost:8000/msg/fixtures",
    json={"fixture_id": 1379137}
)
# JSON doesn't provide detailed report format
```

### Scenario 3: Mobile App Dashboard

**Use:** Messaging endpoints

```python
# ✅ Good - Fast JSON for UI
fixtures = requests.post(
    "http://localhost:8000/msg/fixtures",
    json={"date": "today"}
).json()

# Display in UI
for fixture in fixtures["fixtures"]:
    display_fixture_card(fixture)
```

### Scenario 4: Batch Processing & Archiving

**Use:** MD endpoints

```python
# ✅ Good - Batch process and save files
response = requests.post(
    "http://localhost:8000/batch",
    json={
        "date": "2025-12-24",
        "analyze": True
    }
)
result = response.json()

# Archive all MD files
for md_file in result["md_files"]:
    archive_file(md_file)
```

---

## Performance Comparison

### Response Times

**MD Endpoints:**
- `/fixtures`: 2-5 seconds (file generation)
- `/predict`: 3-8 seconds (analysis generation)
- `/analyze`: 5-10 seconds (fetch + analyze)

**Messaging Endpoints:**
- `/msg/fixtures`: < 500ms
- `/msg/analyze`: 1-2 seconds (analysis parsing)
- `/msg/stats`: < 500ms

### Response Sizes

**MD Endpoints:**
- Average: 20-30 KB per file
- Range: 10-50 KB

**Messaging Endpoints:**
- `/msg/fixtures`: 1-5 KB (depends on count)
- `/msg/analyze`: 1-2 KB
- `/msg/stats`: < 1 KB

---

## Migration Guide

### From MD to Messaging

If you're currently using MD endpoints but need faster responses:

**Before:**
```python
response = requests.post("/fixtures", json={"date": "today"})
md_content = response.text
# Parse MD content manually
```

**After:**
```python
response = requests.post("/msg/fixtures", json={"date": "today"})
fixtures = response.json()["fixtures"]
# Direct use, no parsing needed
```

### From Messaging to MD

If you need file storage:

**Before:**
```python
response = requests.post("/msg/fixtures", json={"date": "today"})
fixtures = response.json()["fixtures"]
# No file storage
```

**After:**
```python
response = requests.post("/fixtures", json={"date": "today"})
with open("fixtures.md", "wb") as f:
    f.write(response.content)
# File saved for archiving
```

---

## Recommendations

### For Bots
👉 Always use messaging endpoints (`/msg/*`)

### For File Storage
👉 Always use MD endpoints (`/fixtures`, `/predict`, `/analyze`)

### For Hybrid Approach
👉 Use MD endpoints for generation, messaging endpoints for display

```python
# Generate once
md_response = requests.post("/analyze", json={"fixture_id": 1379137})
save_file(md_response.content)

# Display quickly
json_response = requests.post("/msg/analyze", json={"fixture_id": 1379137})
display_prediction(json_response.json())
```

---

## Next Steps

- **[API Reference](API_REFERENCE.md)** - Complete endpoint docs
- **[Bot Integration](BOT_INTEGRATION.md)** - Integration examples
- **[Response Formats](RESPONSE_FORMATS.md)** - Response structures


