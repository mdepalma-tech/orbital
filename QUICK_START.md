# 🚀 Quick Start Guide - Shopify Orders Upload

## Prerequisites

✅ Next.js app running  
✅ Supabase project configured  
✅ Node.js 18+ installed  

---

## Step 1: Install Dependencies

```bash
npm install csv-parse
```

---

## Step 2: Get Service Role Key

1. Go to https://app.supabase.com
2. Select your project: `aeevhrnpzbjrzofcwawo`
3. Click **Settings** → **API**
4. Find **service_role** key (NOT the anon key)
5. Copy the secret key

---

## Step 3: Add Environment Variable

Edit `.env.local` and add:

```bash
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.your-key-here...
```

**⚠️ Important:** This key has admin privileges. Never commit it to git or expose it to the client.

---

## Step 4: Run Database Migration

1. Go to https://app.supabase.com/project/aeevhrnpzbjrzofcwawo/sql/new
2. Open `supabase_schema.sql` from your project
3. Copy all SQL code
4. Paste into Supabase SQL Editor
5. Click **Run**

This creates:
- `projects` table
- `project_timeseries` table
- Indexes for performance
- Row Level Security policies

---

## Step 5: Create a Test Project

In Supabase SQL Editor, run:

```sql
-- Get your user ID first
SELECT auth.uid();

-- Then create a test project (replace YOUR_USER_ID)
INSERT INTO projects (id, user_id, name, shopify_domain)
VALUES (
  '550e8400-e29b-41d4-a716-446655440000',
  'YOUR_USER_ID',  -- Replace with actual user ID
  'Test Store',
  'test-store.myshopify.com'
);
```

---

## Step 6: Test the API

### Option A: Use cURL

```bash
curl -X POST \
  "http://localhost:3000/api/projects/550e8400-e29b-41d4-a716-446655440000/upload-orders" \
  -F "file=@test_orders.csv" \
  -F "timezone=America/New_York"
```

### Option B: Use Postman

1. Create new POST request
2. URL: `http://localhost:3000/api/projects/550e8400-e29b-41d4-a716-446655440000/upload-orders`
3. Body → form-data
4. Add key `file` (type: File) → select `test_orders.csv`
5. Add key `timezone` (type: Text) → value: `America/New_York`
6. Send

### Expected Response

```json
{
  "status": "success",
  "dateRange": {
    "start": "2024-01-01",
    "end": "2024-01-08"
  },
  "totalDays": 8,
  "totalOrders": 11,
  "totalRevenue": 1580.50,
  "averageDailyRevenue": 197.56
}
```

**Note:** Test CSV has 15 rows but only 11 are paid & not cancelled.

---

## Step 7: Verify Data in Database

In Supabase SQL Editor:

```sql
SELECT * FROM project_timeseries
WHERE project_id = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY ts;
```

You should see 8 rows (one per day from Jan 1-8, 2024).

---

## Step 8: Export Real Shopify Data

### Get Your Shopify Orders CSV

1. Log into your Shopify admin
2. Go to **Orders**
3. Click **Export**
4. Select:
   - Export type: **All orders** (or date range)
   - Format: **CSV for Excel, Numbers, or other spreadsheet programs**
5. Click **Export orders**
6. Download the CSV file

### Upload to Orbital

Use the same cURL/Postman command but with your real CSV file:

```bash
curl -X POST \
  "http://localhost:3000/api/projects/YOUR_PROJECT_ID/upload-orders" \
  -F "file=@path/to/shopify_orders_export.csv" \
  -F "timezone=America/New_York"  # Use your store's timezone
```

**Common Timezones:**
- Eastern: `America/New_York`
- Central: `America/Chicago`
- Mountain: `America/Denver`
- Pacific: `America/Los_Angeles`
- UTC: `UTC`

---

## Troubleshooting

### Error: "Missing Supabase environment variables"

**Fix:** Add `SUPABASE_SERVICE_ROLE_KEY` to `.env.local` and restart dev server

### Error: "Project not found"

**Fix:** Create the project in the database first (see Step 5)

### Error: "Missing required columns"

**Fix:** Ensure your CSV has these columns (case-insensitive):
- `Created at`
- `Total`
- `Financial Status`

### Error: "Insufficient data: only X distinct days"

**Fix:** Upload CSV with at least 60 days of paid orders

### Error: "No paid orders found"

**Fix:** Ensure CSV contains orders with `Financial Status = "paid"` and no cancellation date

---

## Next Steps

### 1. Add Authentication

Update `route.ts` to verify user owns the project:

```typescript
import { createClient as createSupabaseClient } from "@/lib/supabase/server";

// Add at start of POST handler
const supabaseAuth = await createSupabaseClient();
const { data: { user } } = await supabaseAuth.auth.getUser();

if (!user) {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}

// Verify user owns project
const supabase = getSupabaseServiceClient();
const { data: project } = await supabase
  .from("projects")
  .select("user_id")
  .eq("id", projectId)
  .single();

if (project?.user_id !== user.id) {
  return NextResponse.json({ error: "Forbidden" }, { status: 403 });
}
```

### 2. Create Upload UI

Add to dashboard:

```tsx
// app/dashboard/projects/[projectId]/upload/page.tsx
"use client";

import { useState } from "react";

export default function UploadPage({ params }: { params: { projectId: string } }) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setUploading(true);

    const formData = new FormData(e.currentTarget);
    
    try {
      const response = await fetch(
        `/api/projects/${params.projectId}/upload-orders`,
        { method: "POST", body: formData }
      );
      const data = await response.json();
      setResult(data);
    } catch (error) {
      setResult({ status: "error", message: "Upload failed" });
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl mb-4">Upload Shopify Orders</h1>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block mb-2">CSV File</label>
          <input
            type="file"
            name="file"
            accept=".csv"
            required
            className="w-full"
          />
        </div>

        <div>
          <label className="block mb-2">Timezone</label>
          <select name="timezone" className="w-full p-2 border rounded">
            <option value="UTC">UTC</option>
            <option value="America/New_York">Eastern Time</option>
            <option value="America/Chicago">Central Time</option>
            <option value="America/Denver">Mountain Time</option>
            <option value="America/Los_Angeles">Pacific Time</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={uploading}
          className="px-6 py-2 bg-blue-500 text-white rounded"
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </form>

      {result && (
        <div className="mt-4 p-4 border rounded">
          {result.status === "success" ? (
            <>
              <p className="text-green-600">✅ Success!</p>
              <p>Date range: {result.dateRange.start} to {result.dateRange.end}</p>
              <p>Total days: {result.totalDays}</p>
              <p>Total orders: {result.totalOrders}</p>
              <p>Total revenue: ${result.totalRevenue}</p>
            </>
          ) : (
            <p className="text-red-600">❌ {result.message}</p>
          )}
        </div>
      )}
    </div>
  );
}
```

### 3. Add to Dashboard Navigation

Update sidebar to include upload link.

---

## Support

### Documentation
- `API_UPLOAD_ORDERS.md` - Complete API reference
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- This guide - Quick start

### Test Files
- `test_orders.csv` - Sample CSV for testing
- `supabase_schema.sql` - Database schema

---

## Checklist

Before going to production:

- [ ] Service role key added to `.env.local`
- [ ] Database migration executed
- [ ] Test project created
- [ ] API tested with test CSV
- [ ] API tested with real Shopify CSV
- [ ] Authentication added
- [ ] Authorization added (verify user owns project)
- [ ] File size limit added (10MB recommended)
- [ ] Rate limiting added
- [ ] Upload UI created
- [ ] Error handling tested
- [ ] Data verified in database

---

**Ready to upload!** 🚀

Start with the test CSV, then move to real Shopify data once confirmed working.
