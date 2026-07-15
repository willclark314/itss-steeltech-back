-- project.sql — 项目模块复杂查询
-- 调用: from app.utils.sql_mapper import mapper; mapper("project").one("get_rank", ...)

-- name: get_rank
-- params: p0, p1, p2, project_no
-- 注意：此查询的 WHERE 条件由 Python 端动态构建，占位符按实际数量传入
WITH ranked AS (
  SELECT p.project_no,
         ROW_NUMBER() OVER (
           ORDER BY COALESCE(
             NULLIF(TRIM(p.received_date), ''),
             (SELECT MIN(cf.received_date)
              FROM contact_form_projects cfp
              INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id
              WHERE cfp.project_no = p.project_no),
             NULLIF(TRIM(p.planned_start_date), ''),
             ''
           ) DESC, p.project_no DESC
         ) - 1 AS `rank`
  FROM projects p
  WHERE 1=1
)
SELECT `rank` FROM ranked WHERE project_no = :project_no

-- name: get_contact_form_ids
-- params: project_no
SELECT cfp.contact_form_id
FROM contact_form_projects cfp
INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id AND cf.deleted_at IS NULL
WHERE cfp.project_no = :project_no
ORDER BY cfp.contact_form_id

-- name: get_assigned_personnel
-- params: project_no
SELECT p.id, p.name, p.team
FROM project_personnel pp
INNER JOIN personnel p ON p.id = pp.personnel_id
WHERE pp.project_no = :project_no

-- name: get_received_date_from_contacts
-- params: project_no
SELECT MIN(cf.received_date)
FROM contact_form_projects cfp
INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id
WHERE cfp.project_no = :project_no AND cf.deleted_at IS NULL
