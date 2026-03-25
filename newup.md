import os
from google import genai
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

client = genai.Client()
STORE_NAME = os.getenv("GEMINI_FILE_STORE")

if not STORE_NAME:
    print("❌ GEMINI_FILE_STORE environment variable is missing.")
    exit(1)

print(f"📦 Fetching documents from: {STORE_NAME}\n")

# ── Fetch all documents ──────────────────────────────────────────────────────
try:
    docs = list(client.file_search_stores.documents.list(parent=STORE_NAME))
except Exception as e:
    print(f"❌ Error fetching documents: {e}")
    exit(1)

print(f"📄 Total documents found: {len(docs)}")
print("─" * 45)
for i, doc in enumerate(docs, 1):
    display_name = getattr(doc, 'display_name', None) or doc.name
    print(f"  {i}. {display_name}")
print("─" * 45)

# ── Group by display_name to find duplicates ─────────────────────────────────
groups = defaultdict(list)
for doc in docs:
    display_name = getattr(doc, 'display_name', None) or doc.name
    groups[display_name].append(doc)

duplicates = {name: doc_list for name, doc_list in groups.items() if len(doc_list) > 1}

if not duplicates:
    print("\n✅ No duplicates found. Your store is already clean!")
    exit(0)

# ── Preview duplicates before deletion ──────────────────────────────────────
print(f"\n⚠️  Found {len(duplicates)} duplicate group(s):\n")
for display_name, doc_list in duplicates.items():
    print(f"  📄 '{display_name}' → {len(doc_list)} copies (will delete {len(doc_list) - 1})")

print()
confirm = input("🗑️  Proceed with deletion? (yes/no): ").strip().lower()

if confirm != "yes":
    print("⛔ Deletion cancelled.")
    exit(0)

# ── Delete duplicates ────────────────────────────────────────────────────────
print("\n🔄 Deleting duplicates...\n")
deleted_count = 0
failed_count = 0

for display_name, doc_list in duplicates.items():
    keep = doc_list[0]
    to_delete = doc_list[1:]
    keep_name = getattr(keep, 'display_name', None) or keep.name

    print(f"  📄 '{display_name}'")
    print(f"     ✅ Keeping : {keep.name}")

    for doc in to_delete:
        try:
            client.file_search_stores.documents.delete(name=doc.name)
            print(f"     🗑️  Deleted : {doc.name}")
            deleted_count += 1
        except Exception as e:
            print(f"     ❌ Failed  : {doc.name} → {e}")
            failed_count += 1
    print()

# ── Final verification ───────────────────────────────────────────────────────
print("─" * 45)
print(f"✅ Deleted : {deleted_count} document(s)")
if failed_count:
    print(f"❌ Failed  : {failed_count} document(s)")

remaining = list(client.file_search_stores.documents.list(parent=STORE_NAME))
print(f"📦 Remaining documents: {len(remaining)}\n")
for i, doc in enumerate(remaining, 1):
    name = getattr(doc, 'display_name', None) or doc.name
    print(f"  {i}. {name}")
