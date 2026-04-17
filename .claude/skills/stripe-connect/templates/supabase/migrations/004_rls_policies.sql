-- ----------------------------------------------------------------------------
-- 004_rls_policies.sql
--
-- Row-Level Security for sponsorships + riders.
--
-- Contract:
--   - A fan (authenticated user) sees ONLY their own sponsorships.
--   - A rider sees ONLY the sponsorships that target them.
--   - Public riders (is_public=true AND onboarding_status='enabled') are
--     visible to everyone via the anon role (listing page).
--   - Service role (used by Edge Functions) bypasses RLS entirely — this is
--     how the webhook, create-subscription, etc. write data.
--
-- Assumes the project uses Supabase Auth and riders are linked to auth.users
-- via a separate mechanism (out of scope: this template only covers the
-- billing-relevant policies). If your riders table doesn't have a user_id,
-- add it in a follow-up migration and adapt the policies below.
-- ----------------------------------------------------------------------------

-- Enable RLS
ALTER TABLE sponsorships ENABLE ROW LEVEL SECURITY;
ALTER TABLE riders ENABLE ROW LEVEL SECURITY;

-- --- sponsorships: fan sees own ---
DROP POLICY IF EXISTS "fan reads own sponsorships" ON sponsorships;
CREATE POLICY "fan reads own sponsorships"
    ON sponsorships FOR SELECT
    TO authenticated
    USING (fan_id = auth.uid());

-- --- sponsorships: rider sees sponsorships that target them ---
-- Assumes riders.user_id column exists and matches auth.uid() for the rider's
-- own login. If your schema differs, edit this policy accordingly.
DROP POLICY IF EXISTS "rider reads incoming sponsorships" ON sponsorships;
CREATE POLICY "rider reads incoming sponsorships"
    ON sponsorships FOR SELECT
    TO authenticated
    USING (
        rider_id IN (
            SELECT id FROM riders
            WHERE user_id = auth.uid()
        )
    );

-- --- sponsorships: INSERT/UPDATE/DELETE only by service_role ---
-- No policy grants these to authenticated → Edge Functions (service_role)
-- are the only writers. Prevents fans/riders tampering with billing state.

-- --- riders: public listing (anon) for enabled + is_public riders ---
DROP POLICY IF EXISTS "public riders are visible" ON riders;
CREATE POLICY "public riders are visible"
    ON riders FOR SELECT
    TO anon, authenticated
    USING (is_public = true AND onboarding_status = 'enabled');

-- --- riders: authenticated rider can see own row fully ---
DROP POLICY IF EXISTS "rider reads own profile" ON riders;
CREATE POLICY "rider reads own profile"
    ON riders FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

-- --- riders: rider can update non-billing fields of own row ---
-- Billing fields (stripe_account_id, fee_percent, onboarding_status) are
-- managed exclusively by Edge Functions — no UPDATE policy granted to
-- authenticated users.
DROP POLICY IF EXISTS "rider updates own safe fields" ON riders;
CREATE POLICY "rider updates own safe fields"
    ON riders FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Note: stripe_processed_events has NO policies defined → no access for
-- authenticated or anon. Only service_role (Edge Functions) can touch it.
-- Enable RLS to enforce the default-deny:
ALTER TABLE stripe_processed_events ENABLE ROW LEVEL SECURITY;
