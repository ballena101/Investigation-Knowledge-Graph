-- IKF Databricks cost audit
--
-- Purpose:
--   Read-only cost visibility before any future IKF cloud validation session.
--   This query does not launch model inference or IKF processing jobs.
--
-- Usage:
--   1. Run before an IKF release-candidate validation session.
--   2. Adjust the start date if required.
--   3. Review the result sets in order: overall -> jobs -> daily trend -> Apps
--      -> model serving -> serverless notebooks/jobs.
--
-- Cost values use Databricks effective list price. Contract discounts,
-- committed-use discounts, cloud-provider charges and taxes can make the
-- invoice amount different.
--
-- Billing data can arrive with a delay (typically within ~12 hours), so this
-- audit is suitable for historical/current exposure review but not as a
-- second-by-second spend meter.

-- -------------------------------------------------------------------------
-- A. Account/workspace usage summary since IKF active development began
-- -------------------------------------------------------------------------
WITH priced_usage AS (
    SELECT
        u.workspace_id,
        u.billing_origin_product,
        u.sku_name,
        u.usage_unit,
        u.usage_quantity,
        u.usage_start_time,
        u.usage_end_time,
        u.usage_date,
        u.usage_metadata,
        u.identity_metadata,
        u.custom_tags,
        p.currency_code,
        p.pricing.effective_list.default AS unit_list_price,
        u.usage_quantity * p.pricing.effective_list.default AS effective_list_cost
    FROM system.billing.usage AS u
    INNER JOIN system.billing.list_prices AS p
        ON u.cloud = p.cloud
        AND u.sku_name = p.sku_name
        AND u.usage_unit = p.usage_unit
        AND u.usage_start_time >= p.price_start_time
        AND (p.price_end_time IS NULL OR u.usage_end_time <= p.price_end_time)
    WHERE u.usage_date >= DATE '2026-09-01'
)
SELECT
    billing_origin_product,
    sku_name,
    usage_unit,
    currency_code,
    ROUND(SUM(usage_quantity), 4) AS usage_quantity,
    ROUND(SUM(effective_list_cost), 2) AS effective_list_cost,
    MIN(usage_start_time) AS first_usage,
    MAX(usage_end_time) AS last_usage
FROM priced_usage
GROUP BY
    billing_origin_product,
    sku_name,
    usage_unit,
    currency_code
ORDER BY effective_list_cost DESC;

-- -------------------------------------------------------------------------
-- B. Lakeflow / Jobs cost by job and run where metadata is available
-- -------------------------------------------------------------------------
WITH latest_jobs AS (
    SELECT
        workspace_id,
        job_id,
        name,
        ROW_NUMBER() OVER (
            PARTITION BY workspace_id, job_id
            ORDER BY change_time DESC
        ) AS rn
    FROM system.lakeflow.jobs
),
job_usage AS (
    SELECT
        u.workspace_id,
        u.usage_metadata.job_id AS job_id,
        u.usage_metadata.job_run_id AS job_run_id,
        u.usage_metadata.job_name AS metadata_job_name,
        u.sku_name,
        u.usage_quantity,
        u.usage_start_time,
        u.usage_end_time,
        p.currency_code,
        u.usage_quantity * p.pricing.effective_list.default AS effective_list_cost
    FROM system.billing.usage AS u
    INNER JOIN system.billing.list_prices AS p
        ON u.cloud = p.cloud
        AND u.sku_name = p.sku_name
        AND u.usage_unit = p.usage_unit
        AND u.usage_start_time >= p.price_start_time
        AND (p.price_end_time IS NULL OR u.usage_end_time <= p.price_end_time)
    WHERE u.billing_origin_product = 'JOBS'
      AND u.usage_date >= DATE '2026-09-01'
)
SELECT
    COALESCE(
        j.name,
        u.metadata_job_name,
        CONCAT('job_id=', CAST(u.job_id AS STRING))
    ) AS job_name,
    u.job_id,
    u.job_run_id,
    u.currency_code,
    ROUND(SUM(u.usage_quantity), 4) AS usage_quantity,
    ROUND(SUM(u.effective_list_cost), 2) AS effective_list_cost,
    MIN(u.usage_start_time) AS first_usage,
    MAX(u.usage_end_time) AS last_usage
FROM job_usage AS u
LEFT JOIN latest_jobs AS j
    ON u.workspace_id = j.workspace_id
    AND u.job_id = j.job_id
    AND j.rn = 1
GROUP BY
    COALESCE(
        j.name,
        u.metadata_job_name,
        CONCAT('job_id=', CAST(u.job_id AS STRING))
    ),
    u.job_id,
    u.job_run_id,
    u.currency_code
ORDER BY effective_list_cost DESC;

-- -------------------------------------------------------------------------
-- C. Daily trend: useful for spotting days with accidental running resources
-- -------------------------------------------------------------------------
WITH daily_priced AS (
    SELECT
        u.usage_date,
        u.billing_origin_product,
        p.currency_code,
        u.usage_quantity * p.pricing.effective_list.default AS effective_list_cost
    FROM system.billing.usage AS u
    INNER JOIN system.billing.list_prices AS p
        ON u.cloud = p.cloud
        AND u.sku_name = p.sku_name
        AND u.usage_unit = p.usage_unit
        AND u.usage_start_time >= p.price_start_time
        AND (p.price_end_time IS NULL OR u.usage_end_time <= p.price_end_time)
    WHERE u.usage_date >= DATE '2026-09-01'
)
SELECT
    usage_date,
    billing_origin_product,
    currency_code,
    ROUND(SUM(effective_list_cost), 2) AS effective_list_cost
FROM daily_priced
GROUP BY usage_date, billing_origin_product, currency_code
ORDER BY usage_date DESC, effective_list_cost DESC;

-- -------------------------------------------------------------------------
-- D. Databricks Apps cost by named App
--
-- IKF's current App name is expected to include investigation-kg-poc. Do not
-- filter it out here: showing all Apps helps detect accidental unrelated or
-- duplicate running Apps in the same workspace/account.
-- -------------------------------------------------------------------------
SELECT
    u.usage_metadata.app_name AS app_name,
    u.usage_metadata.app_id AS app_id,
    p.currency_code,
    ROUND(SUM(u.usage_quantity), 4) AS usage_quantity,
    ROUND(
        SUM(u.usage_quantity * p.pricing.effective_list.default),
        2
    ) AS effective_list_cost,
    MIN(u.usage_start_time) AS first_usage,
    MAX(u.usage_end_time) AS last_usage
FROM system.billing.usage AS u
INNER JOIN system.billing.list_prices AS p
    ON u.cloud = p.cloud
    AND u.sku_name = p.sku_name
    AND u.usage_unit = p.usage_unit
    AND u.usage_start_time >= p.price_start_time
    AND (p.price_end_time IS NULL OR u.usage_end_time <= p.price_end_time)
WHERE u.billing_origin_product = 'APPS'
  AND u.usage_date >= DATE '2026-09-01'
GROUP BY
    u.usage_metadata.app_name,
    u.usage_metadata.app_id,
    p.currency_code
ORDER BY effective_list_cost DESC;

-- -------------------------------------------------------------------------
-- E. Model Serving cost by endpoint
--
-- This is particularly important for Class-D dedicated endpoints. A serving
-- endpoint that remains provisioned or repeatedly launches can cost more than
-- App deployment itself. Endpoint names are taken directly from billing
-- metadata so unexpected endpoints remain visible.
-- -------------------------------------------------------------------------
SELECT
    u.usage_metadata.endpoint_name AS endpoint_name,
    u.sku_name,
    p.currency_code,
    ROUND(SUM(u.usage_quantity), 4) AS usage_quantity,
    ROUND(
        SUM(u.usage_quantity * p.pricing.effective_list.default),
        2
    ) AS effective_list_cost,
    MIN(u.usage_start_time) AS first_usage,
    MAX(u.usage_end_time) AS last_usage
FROM system.billing.usage AS u
INNER JOIN system.billing.list_prices AS p
    ON u.cloud = p.cloud
    AND u.sku_name = p.sku_name
    AND u.usage_unit = p.usage_unit
    AND u.usage_start_time >= p.price_start_time
    AND (p.price_end_time IS NULL OR u.usage_end_time <= p.price_end_time)
WHERE u.usage_date >= DATE '2026-09-01'
  AND (
      u.usage_metadata.endpoint_name IS NOT NULL
      OR u.sku_name LIKE '%REAL_TIME_INFERENCE%'
  )
GROUP BY
    u.usage_metadata.endpoint_name,
    u.sku_name,
    p.currency_code
ORDER BY effective_list_cost DESC;

-- -------------------------------------------------------------------------
-- F. Serverless notebook/job detail
--
-- This helps distinguish deliberate IKF workload execution from general
-- serverless usage when job attribution is incomplete. Notebook path and job
-- metadata are populated only where Databricks can attribute the record.
-- -------------------------------------------------------------------------
SELECT
    u.usage_date,
    u.usage_metadata.notebook_path AS notebook_path,
    u.usage_metadata.job_name AS job_name,
    u.usage_metadata.job_id AS job_id,
    u.usage_metadata.job_run_id AS job_run_id,
    u.identity_metadata.run_as AS run_as,
    u.sku_name,
    p.currency_code,
    ROUND(SUM(u.usage_quantity), 4) AS usage_quantity,
    ROUND(
        SUM(u.usage_quantity * p.pricing.effective_list.default),
        2
    ) AS effective_list_cost
FROM system.billing.usage AS u
INNER JOIN system.billing.list_prices AS p
    ON u.cloud = p.cloud
    AND u.sku_name = p.sku_name
    AND u.usage_unit = p.usage_unit
    AND u.usage_start_time >= p.price_start_time
    AND (p.price_end_time IS NULL OR u.usage_end_time <= p.price_end_time)
WHERE u.usage_date >= DATE '2026-09-01'
  AND (
      u.usage_metadata.notebook_path IS NOT NULL
      OR u.usage_metadata.job_id IS NOT NULL
      OR u.usage_metadata.job_name IS NOT NULL
  )
GROUP BY
    u.usage_date,
    u.usage_metadata.notebook_path,
    u.usage_metadata.job_name,
    u.usage_metadata.job_id,
    u.usage_metadata.job_run_id,
    u.identity_metadata.run_as,
    u.sku_name,
    p.currency_code
ORDER BY usage_date DESC, effective_list_cost DESC;
