---
name: menu-import
description: Menu data import — use LLM intelligence to understand and extract dish information from ANY format, then offer to generate posts
user-invocable: true
argument-hint: "[menu file path, image, or text description]"
---

## 🎯 Core Philosophy

**DO NOT use rigid scripts.** Leverage the LLM's understanding capabilities to handle the infinite variety of user inputs.

## Trigger Conditions

User provides menu data in ANY form:
- CSV files (any column names, any format)
- Text descriptions (structured or unstructured)
- Screenshots of menus (physical menus, PDFs, phone photos)
- Mixed formats (text + images)
- Verbal descriptions
- Partial information

## 🧠 LLM-Powered Workflow

### 1. Understanding Phase

**When user provides input, USE YOUR INTELLIGENCE to:**

1. **Read the input** using appropriate tools:
   - CSV/text files → Use `Read` tool
   - Images/screenshots → Use `Read` tool (it supports images!)
   - Mixed content → Read all provided files

2. **Understand the content**:
   - What dishes are mentioned?
   - What information is available for each dish?
   - What format is this data in?
   - Is any information missing or unclear?

3. **Extract information flexibly**:
   - Don't expect specific column names
   - Understand context (e.g., "£8.50" is clearly a price)
   - Infer missing information when reasonable
   - Identify dish categories from names/descriptions

### 2. Progressive Disclosure

**Ask clarifying questions ONLY when necessary:**

❌ **DON'T ask**: "What column represents the price?"
✅ **DO**: Understand that "8.50", "£8.50", "Price: 8.50" all mean price

❌ **DON'T ask**: "Please provide data in format X"
✅ **DO**: Work with whatever format user provides

**When to ask questions:**
- Ambiguous information (e.g., "Spicy Noodles" - is this Main or Appetizer?)
- Missing critical information (e.g., all dishes lack names)
- Conflicting information
- User wants to confirm before saving

### 3. Data Transformation

**Transform extracted information into standardized structure:**

```json
{
  "id": "dish-{YYYYMMDDHHMMSS}",
  "name": "Dish Name",
  "category": "Main|Appetizer|Drink|Special",
  "description": "Full description",
  "price": "£8.50",
  "ingredients": ["ingredient1", "ingredient2"],
  "tags": ["spicy", "vegetarian", "popular"],
  "image": "URL or null",
  "createdAt": "ISO timestamp",
  "updatedAt": "ISO timestamp"
}
```

**Category normalization:**
- Main: Main courses, entrees, 主菜, mains
- Appetizer: Starters, 开胃菜, appetizers, sides
- Drink: Beverages, drinks, 饮料
- Special: Signature dishes, specials, 特色

### 4. Saving to menu.json

**Use Write/Edit tools directly:**

1. **Read current menu.json** with `Read` tool
2. **Parse the JSON** to understand existing dishes
3. **Merge new dishes** (avoid duplicates by name)
4. **Write updated JSON** with `Write` tool

**Example approach:**
```
1. Read data/menu.json
2. Parse JSON to get existing dishes array
3. For each new dish:
   - Generate unique ID
   - Add timestamps
   - Check for duplicates (by name, case-insensitive)
   - Add to dishes array
4. Update lastUpdated timestamp
5. Write complete JSON back to file
```

### 5. User Feedback

**After successful import, report:**

```
✅ Imported {N} dishes to menu database

Distribution:
- Main: X dishes
- Appetizer: Y dishes
- Drink: Z dishes
- Special: W dishes

Images: {M} with images | {N-M} without images
```

**Then immediately offer to generate posts** (do not wait to be asked):

```
Want me to write posts for these? I can generate a week's worth and schedule them now.
Reply "yes" or "generate 7 posts" to go.
```

This hands off naturally to the **post** skill which handles generation, approval, and scheduling in one conversation.

## 🎨 Example Scenarios

### Scenario 1: Well-Structured CSV
User uploads CSV with clear columns → Read, understand, extract, save

### Scenario 2: Messy Text
```
Lamb burgers £8
really good noodles with sesame 7.50
dumplings - veggie ones and meat ones, both 6 pounds
```
→ Understand this is 3 dishes, infer structure, ask about categories if needed

### Scenario 3: Menu Photo
User sends photo of physical menu → Read image, OCR text, extract dishes, structure data

### Scenario 4: Partial Information
User: "Add Grilled Salmon, it's our signature dish, £14.50"
→ Extract: name, category (Main), price, tag (signature)
→ Don't ask for missing fields, just mark them as empty

### Scenario 5: Mixed Languages
User provides Chinese menu → Translate to English, structure appropriately

## 🚫 What NOT to Do

❌ **Don't call Python scripts** (unless truly necessary for specific tasks)
✅ **Do the work yourself** using Read/Write tools and LLM intelligence

❌ **Don't enforce rigid formats**
✅ **Accept any input and figure it out**

❌ **Don't ask unnecessary questions**
✅ **Infer what you can, ask only when critical**

❌ **Don't fail on unexpected input**
✅ **Adapt to whatever format user provides**

## 📊 Data Structure Reference

**Target JSON structure** (`data/menu.json`):
```json
{
  "dishes": [
    {
      "id": "dish-20260218001234",
      "name": "Grilled Salmon",
      "category": "Main",
      "description": "Fresh salmon fillet with lemon butter sauce",
      "price": "£14.50",
      "ingredients": ["salmon", "lemon", "butter"],
      "tags": ["signature", "grilled"],
      "image": "https://example.com/image.jpg",
      "createdAt": "2026-02-18T00:12:34Z",
      "updatedAt": "2026-02-18T00:12:34Z"
    }
  ],
  "lastUpdated": "2026-02-18T00:12:34Z"
}
```

**All fields except `id`, `name`, `createdAt`, `updatedAt` are optional.**

## 🎯 Success Criteria

✅ Can import from ANY format user provides
✅ Minimal user friction (few or no questions)
✅ Intelligent inference of structure
✅ Graceful handling of missing/unclear data
✅ Clear feedback on what was imported
