-- Create projects table if it doesn't exist
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  shopify_domain TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create project_timeseries table if it doesn't exist
CREATE TABLE IF NOT EXISTS project_timeseries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  ts DATE NOT NULL,
  revenue NUMERIC NOT NULL DEFAULT 0,
  sessions INTEGER,
  orders INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT unique_project_date UNIQUE(project_id, ts)
);

-- Create project_channel_spend table for ad spend data
CREATE TABLE IF NOT EXISTS project_channel_spend (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  ts DATE NOT NULL,
  channel TEXT NOT NULL,
  spend NUMERIC(12,2) NOT NULL DEFAULT 0,
  impressions INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT unique_project_date_channel UNIQUE(project_id, ts, channel)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_project_timeseries_project_id 
  ON project_timeseries(project_id);

CREATE INDEX IF NOT EXISTS idx_project_timeseries_ts 
  ON project_timeseries(ts);

CREATE INDEX IF NOT EXISTS idx_project_timeseries_project_ts 
  ON project_timeseries(project_id, ts);

CREATE INDEX IF NOT EXISTS idx_project_channel_spend_project_id
  ON project_channel_spend(project_id);

CREATE INDEX IF NOT EXISTS idx_project_channel_spend_project_ts
  ON project_channel_spend(project_id, ts);

CREATE INDEX IF NOT EXISTS idx_project_channel_spend_channel
  ON project_channel_spend(project_id, channel);

-- Add Row Level Security (RLS) policies
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_timeseries ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_channel_spend ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own projects
CREATE POLICY IF NOT EXISTS "Users can view own projects"
  ON projects FOR SELECT
  USING (auth.uid() = user_id);

-- Policy: Users can insert their own projects
CREATE POLICY IF NOT EXISTS "Users can insert own projects"
  ON projects FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update their own projects
CREATE POLICY IF NOT EXISTS "Users can update own projects"
  ON projects FOR UPDATE
  USING (auth.uid() = user_id);

-- Policy: Users can delete their own projects
CREATE POLICY IF NOT EXISTS "Users can delete own projects"
  ON projects FOR DELETE
  USING (auth.uid() = user_id);

-- Policy: Users can view timeseries for their projects
CREATE POLICY IF NOT EXISTS "Users can view own project timeseries"
  ON project_timeseries FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = project_timeseries.project_id
      AND projects.user_id = auth.uid()
    )
  );

-- Policy: Users can view channel spend for their projects
CREATE POLICY IF NOT EXISTS "Users can view own project channel spend"
  ON project_channel_spend FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = project_channel_spend.project_id
      AND projects.user_id = auth.uid()
    )
  );

-- Policy: Service role can insert/update timeseries and channel spend (for API uploads)
-- Note: This is handled by service_role key, which bypasses RLS

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_project_timeseries_updated_at
  BEFORE UPDATE ON project_timeseries
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_project_channel_spend_updated_at
  BEFORE UPDATE ON project_channel_spend
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE projects IS 'User projects with Shopify store connections';
COMMENT ON TABLE project_timeseries IS 'Daily aggregated metrics for each project';
COMMENT ON COLUMN project_timeseries.ts IS 'Date in local timezone';
COMMENT ON COLUMN project_timeseries.revenue IS 'Daily total revenue';
COMMENT ON COLUMN project_timeseries.sessions IS 'Daily session count (optional, from GA)';
COMMENT ON COLUMN project_timeseries.orders IS 'Daily order count';
COMMENT ON TABLE project_channel_spend IS 'Daily ad spend by channel for each project';
COMMENT ON COLUMN project_channel_spend.ts IS 'Date of spend';
COMMENT ON COLUMN project_channel_spend.channel IS 'Marketing channel name (e.g. Facebook, Google)';
COMMENT ON COLUMN project_channel_spend.spend IS 'Daily spend amount for channel';
COMMENT ON COLUMN project_channel_spend.impressions IS 'Daily impressions (optional)';
COMMENT ON COLUMN project_channel_spend.clicks IS 'Daily clicks (optional)';
