-- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
--
-- Host: host.docker.internal    Database: itss_steeltech
-- ------------------------------------------------------
-- Server version	8.0.30

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `account_passwords`
--

DROP TABLE IF EXISTS `account_passwords`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `account_passwords` (
  `account` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `backup_records`
--

DROP TABLE IF EXISTS `backup_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `backup_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `filename` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size` int NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `trigger_type` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `change_order_pdfs`
--

DROP TABLE IF EXISTS `change_order_pdfs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `change_order_pdfs` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `change_order_id` int NOT NULL,
  `file_name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_md5` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_size` int DEFAULT NULL,
  `mime_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'application/pdf',
  `attachment_type` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'supplement',
  `sort_order` int NOT NULL DEFAULT '0',
  `is_current` int NOT NULL DEFAULT '1',
  `original_file_name` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `deleted_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_change_order_pdfs_order_id` (`change_order_id`),
  KEY `idx_change_order_pdfs_md5` (`file_md5`),
  KEY `idx_change_order_pdfs_deleted_at` (`deleted_at`),
  CONSTRAINT `change_order_pdfs_ibfk_1` FOREIGN KEY (`change_order_id`) REFERENCES `change_orders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `change_order_projects`
--

DROP TABLE IF EXISTS `change_order_projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `change_order_projects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `change_order_id` int NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `change_order_id` (`change_order_id`,`project_no`),
  KEY `idx_cop_change_order_id` (`change_order_id`),
  KEY `idx_cop_project_no` (`project_no`),
  CONSTRAINT `change_order_projects_ibfk_1` FOREIGN KEY (`change_order_id`) REFERENCES `change_orders` (`id`) ON DELETE CASCADE,
  CONSTRAINT `change_order_projects_ibfk_2` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `change_orders`
--

DROP TABLE IF EXISTS `change_orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `change_orders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `order_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `received_date` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `content` text COLLATE utf8mb4_unicode_ci,
  `deleted_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_change_orders_order_no` (`order_no`),
  KEY `idx_change_orders_deleted_at` (`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `contact_form_pdfs`
--

DROP TABLE IF EXISTS `contact_form_pdfs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contact_form_pdfs` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact_form_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_md5` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_size` int DEFAULT NULL,
  `mime_type` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `attachment_type` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `is_current` int NOT NULL,
  `original_file_name` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `deleted_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `contact_form_id` (`contact_form_id`),
  KEY `idx_contact_form_pdfs_md5` (`file_md5`),
  KEY `idx_contact_form_pdfs_deleted_at` (`deleted_at`),
  CONSTRAINT `contact_form_pdfs_ibfk_1` FOREIGN KEY (`contact_form_id`) REFERENCES `contact_forms` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `contact_form_project_cancellations`
--

DROP TABLE IF EXISTS `contact_form_project_cancellations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contact_form_project_cancellations` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cancel_contact_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `target_contact_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cancelled_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `contact_form_projects`
--

DROP TABLE IF EXISTS `contact_form_projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contact_form_projects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `contact_form_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_type` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_contact_form_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  UNIQUE KEY `uq_cfp_contact_project` (`contact_form_id`,`project_no`),
  KEY `project_no` (`project_no`),
  KEY `idx_cfp_contact_form_id` (`contact_form_id`),
  CONSTRAINT `contact_form_projects_ibfk_1` FOREIGN KEY (`contact_form_id`) REFERENCES `contact_forms` (`id`) ON DELETE CASCADE,
  CONSTRAINT `contact_form_projects_ibfk_2` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1010 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `contact_form_tags`
--

DROP TABLE IF EXISTS `contact_form_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contact_form_tags` (
  `contact_form_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tag_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`contact_form_id`,`tag_id`),
  KEY `idx_contact_form_tags_contact` (`contact_form_id`),
  KEY `idx_contact_form_tags_tag` (`tag_id`),
  CONSTRAINT `contact_form_tags_ibfk_1` FOREIGN KEY (`contact_form_id`) REFERENCES `contact_forms` (`id`) ON DELETE CASCADE,
  CONSTRAINT `contact_form_tags_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `contact_forms`
--

DROP TABLE IF EXISTS `contact_forms`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contact_forms` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `received_date` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `urgency` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text COLLATE utf8mb4_unicode_ci,
  `expect_reply_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `parent_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `root_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `relation_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `cancel_scope` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `deleted_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `derived_family_max_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_contact_forms_received_date` (`received_date`),
  KEY `idx_contact_forms_deleted_at` (`deleted_at`),
  KEY `idx_contact_forms_root_id` (`root_id`),
  KEY `idx_contact_forms_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `design_drawing_issue_plans`
--

DROP TABLE IF EXISTS `design_drawing_issue_plans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `design_drawing_issue_plans` (
  `id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `year` int NOT NULL,
  `month` int NOT NULL,
  `seq` int NOT NULL,
  `project_name` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `component_weight_kg` float DEFAULT NULL,
  `planned_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `actual_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `material_prep_list_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `task_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'design',
  `design_planned_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `design_actual_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tile_layout_planned_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tile_layout_actual_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `floor_deck_planned_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `floor_deck_actual_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_design_drawing_issue_plans_year_month_seq` (`year`,`month`,`seq`),
  KEY `idx_design_drawing_issue_plans_year_month` (`year`,`month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `director_interview_images`
--

DROP TABLE IF EXISTS `director_interview_images`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `director_interview_images` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `interview_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size` int NOT NULL,
  `mime_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `interview_id` (`interview_id`),
  CONSTRAINT `director_interview_images_ibfk_1` FOREIGN KEY (`interview_id`) REFERENCES `director_interviews` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `director_interviews`
--

DROP TABLE IF EXISTS `director_interviews`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `director_interviews` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `employee_name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `employee_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `division` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `position` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `interview_date` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `interview_topic` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `interview_content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `conclusion` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `interviewer` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `interviewee` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `drawing_issue_plans`
--

DROP TABLE IF EXISTS `drawing_issue_plans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `drawing_issue_plans` (
  `id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `year` int NOT NULL,
  `month` int NOT NULL,
  `seq` int NOT NULL,
  `project_name` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `component_weight_kg` float DEFAULT NULL,
  `planned_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `actual_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `material_prep_list_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `detail_planned_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `detail_actual_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `floor_deck_planned_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `floor_deck_actual_issue_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_drawing_issue_plans_year_month_seq` (`year`,`month`,`seq`),
  KEY `idx_drawing_issue_plans_year_month` (`year`,`month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `monthly_rest`
--

DROP TABLE IF EXISTS `monthly_rest`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `monthly_rest` (
  `id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `personnel_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `year` int NOT NULL,
  `month` int NOT NULL,
  `rest_days` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_monthly_rest_personnel_id` (`personnel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `monthly_rest_lock`
--

DROP TABLE IF EXISTS `monthly_rest_lock`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `monthly_rest_lock` (
  `year` int NOT NULL,
  `month` int NOT NULL,
  `locked_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `locked_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`year`,`month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `monthly_training_materials`
--

DROP TABLE IF EXISTS `monthly_training_materials`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `monthly_training_materials` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `training_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size` int NOT NULL,
  `mime_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `material_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `training_id` (`training_id`),
  CONSTRAINT `monthly_training_materials_ibfk_1` FOREIGN KEY (`training_id`) REFERENCES `monthly_trainings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `monthly_training_photos`
--

DROP TABLE IF EXISTS `monthly_training_photos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `monthly_training_photos` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `training_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size` int NOT NULL,
  `mime_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `training_id` (`training_id`),
  CONSTRAINT `monthly_training_photos_ibfk_1` FOREIGN KEY (`training_id`) REFERENCES `monthly_trainings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `monthly_trainings`
--

DROP TABLE IF EXISTS `monthly_trainings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `monthly_trainings` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `training_year` varchar(4) COLLATE utf8mb4_unicode_ci NOT NULL,
  `training_month` varchar(2) COLLATE utf8mb4_unicode_ci NOT NULL,
  `item_seq` int NOT NULL,
  `category_tag` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trainer` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `content_file_name` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `content_file_path` text COLLATE utf8mb4_unicode_ci,
  `content_file_size` int DEFAULT NULL,
  `content_mime_type` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `archive_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `training_date` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `permissions`
--

DROP TABLE IF EXISTS `permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `permissions` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `code` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `module` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `path` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `page_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `page_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `personnel`
--

DROP TABLE IF EXISTS `personnel`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `personnel` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `employee_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `id_card_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `passport_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `passport_expiry` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `position` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nationality` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `workshop` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `team` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `birth_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `age` int DEFAULT NULL,
  `gender` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ethnicity` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `native_place` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `education` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `home_address` text COLLATE utf8mb4_unicode_ci,
  `graduation_school` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `major` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `indonesia_phone` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `domestic_phone` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dormitory_no` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_personnel_employee_no` (`employee_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `personnel_leave_entries`
--

DROP TABLE IF EXISTS `personnel_leave_entries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `personnel_leave_entries` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `personnel_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `end_date` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `planned_days` int NOT NULL,
  `actual_days` int DEFAULT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `parent_entry_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reason` text COLLATE utf8mb4_unicode_ci,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_personnel_leave_entries_personnel_id` (`personnel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `personnel_leave_policies`
--

DROP TABLE IF EXISTS `personnel_leave_policies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `personnel_leave_policies` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `personnel_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `work_days` int NOT NULL,
  `leave_days` int NOT NULL,
  `cycle_start_date` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `effective_from` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_personnel_leave_policies_personnel_id` (`personnel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `project_design_workflows`
--

DROP TABLE IF EXISTS `project_design_workflows`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_design_workflows` (
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `design_started_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `design_completed_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `design_area_sqm` double DEFAULT NULL,
  `design_area_updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `design_area_updated_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`project_no`),
  CONSTRAINT `project_design_workflows_ibfk_1` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `project_detail_workflows`
--

DROP TABLE IF EXISTS `project_detail_workflows`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_detail_workflows` (
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modeling_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `drawing_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `plate_layout_enabled` tinyint(1) NOT NULL,
  `plate_layout_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `modeling_started_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `modeling_completed_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `drawing_started_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `drawing_completed_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `plate_layout_started_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `plate_layout_completed_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model_weight_tons` float DEFAULT NULL,
  `model_weight_updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `model_weight_updated_by` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`project_no`),
  KEY `model_weight_updated_by` (`model_weight_updated_by`),
  CONSTRAINT `project_detail_workflows_ibfk_1` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE,
  CONSTRAINT `project_detail_workflows_ibfk_2` FOREIGN KEY (`model_weight_updated_by`) REFERENCES `personnel` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `project_models`
--

DROP TABLE IF EXISTS `project_models`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_models` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_weight_tons` float DEFAULT NULL,
  `model_path` text COLLATE utf8mb4_unicode_ci,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `seq` int NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_project_models_project_no` (`project_no`),
  KEY `idx_project_models_model_type` (`model_type`),
  KEY `idx_project_models_status` (`status`),
  KEY `idx_project_models_project_no_seq` (`project_no`,`seq`),
  CONSTRAINT `project_models_ibfk_1` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `project_natures`
--

DROP TABLE IF EXISTS `project_natures`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_natures` (
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nature` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`project_no`,`nature`),
  CONSTRAINT `project_natures_ibfk_1` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `project_personnel`
--

DROP TABLE IF EXISTS `project_personnel`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_personnel` (
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `personnel_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`project_no`,`personnel_id`),
  KEY `personnel_id` (`personnel_id`),
  CONSTRAINT `project_personnel_ibfk_1` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE,
  CONSTRAINT `project_personnel_ibfk_2` FOREIGN KEY (`personnel_id`) REFERENCES `personnel` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `project_tags`
--

DROP TABLE IF EXISTS `project_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_tags` (
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tag_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`project_no`,`tag_id`),
  KEY `idx_project_tags_project_no` (`project_no`),
  KEY `idx_project_tags_tag_id` (`tag_id`),
  CONSTRAINT `project_tags_ibfk_1` FOREIGN KEY (`project_no`) REFERENCES `projects` (`project_no`) ON DELETE CASCADE,
  CONSTRAINT `project_tags_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `projects`
--

DROP TABLE IF EXISTS `projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `projects` (
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `customer` varchar(256) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `design_completed` tinyint(1) NOT NULL,
  `detail_completed` tinyint(1) NOT NULL,
  `tile_layout_completed` tinyint(1) NOT NULL,
  `floor_deck_layout_completed` tinyint(1) NOT NULL,
  `drawing_issue_enabled` tinyint(1) NOT NULL,
  `drawing_issue_year_month` varchar(7) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `received_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `planned_start_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `planned_end_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `actual_start_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `actual_end_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `design_work_path` text COLLATE utf8mb4_unicode_ci,
  `detail_work_path` text COLLATE utf8mb4_unicode_ci,
  `local_work_path` text COLLATE utf8mb4_unicode_ci,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `derived_received_date` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_jiagongdan` tinyint(1) NOT NULL DEFAULT '0',
  `structure_type` text COLLATE utf8mb4_unicode_ci,
  `estimated_weight_tons` double DEFAULT NULL,
  PRIMARY KEY (`project_no`),
  KEY `idx_projects_status` (`status`),
  KEY `idx_projects_derived_received_date` (`derived_received_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role_permissions`
--

DROP TABLE IF EXISTS `role_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `role_permissions` (
  `role_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `permission_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`role_id`,`permission_id`),
  KEY `permission_id` (`permission_id`),
  CONSTRAINT `role_permissions_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `role_permissions_ibfk_2` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role_personnel`
--

DROP TABLE IF EXISTS `role_personnel`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `role_personnel` (
  `role_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `personnel_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`role_id`,`personnel_id`),
  KEY `personnel_id` (`personnel_id`),
  CONSTRAINT `role_personnel_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `role_personnel_ibfk_2` FOREIGN KEY (`personnel_id`) REFERENCES `personnel` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role_workshops`
--

DROP TABLE IF EXISTS `role_workshops`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `role_workshops` (
  `role_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `workshop` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`role_id`,`workshop`),
  KEY `idx_role_workshops_workshop` (`workshop`),
  CONSTRAINT `role_workshops_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `code` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settlement_pending_items`
--

DROP TABLE IF EXISTS `settlement_pending_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `settlement_pending_items` (
  `id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `seq` int NOT NULL,
  `name` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quantity` float NOT NULL,
  `unit` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `unit_price` float NOT NULL,
  `total_price` float NOT NULL,
  `coefficient` float NOT NULL,
  `pricing_code` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `issue_year` int DEFAULT NULL,
  `issue_month` int DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_settlement_pending_category_seq` (`category`,`seq`),
  KEY `idx_settlement_pending_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settlement_pricing_basis`
--

DROP TABLE IF EXISTS `settlement_pricing_basis`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `settlement_pricing_basis` (
  `id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `pricing_code` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `item_name` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `calc_process` text COLLATE utf8mb4_unicode_ci,
  `unit_price` float NOT NULL,
  `unit` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `remark` text COLLATE utf8mb4_unicode_ci,
  `seq` int NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_settlement_pricing_code` (`category`,`pricing_code`),
  KEY `idx_settlement_pricing_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `settlement_records`
--

DROP TABLE IF EXISTS `settlement_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `settlement_records` (
  `id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `year` int NOT NULL,
  `month` int NOT NULL,
  `seq` int NOT NULL,
  `category` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quantity` float NOT NULL,
  `unit` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `unit_price` float NOT NULL,
  `total_price` float NOT NULL,
  `coefficient` float NOT NULL,
  `pricing_code` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `settlement_year` int DEFAULT NULL,
  `settlement_month` int DEFAULT NULL,
  `issue_year` int DEFAULT NULL,
  `issue_month` int DEFAULT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_settlement_records_year_month_category_seq` (`year`,`month`,`category`,`seq`),
  KEY `idx_settlement_records_year_month` (`year`,`month`),
  KEY `idx_settlement_records_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `system_settings`
--

DROP TABLE IF EXISTS `system_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_settings` (
  `key` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `value` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tags`
--

DROP TABLE IF EXISTS `tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tags` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `temp_task_personnel`
--

DROP TABLE IF EXISTS `temp_task_personnel`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `temp_task_personnel` (
  `temp_task_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `personnel_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`temp_task_id`,`personnel_id`),
  KEY `ix_temp_task_personnel_personnel_id` (`personnel_id`),
  KEY `idx_temp_task_personnel_personnel` (`personnel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `temp_tasks`
--

DROP TABLE IF EXISTS `temp_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `temp_tasks` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `start_time` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `completed_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_related_project` int NOT NULL,
  `related_project_no` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_by` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_temp_tasks_created_by` (`created_by`),
  KEY `idx_temp_tasks_created_by` (`created_by`),
  KEY `idx_temp_tasks_start_time` (`start_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_preferences`
--

DROP TABLE IF EXISTS `user_preferences`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_preferences` (
  `account` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `preference_key` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `preference_value` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`account`,`preference_key`),
  KEY `idx_user_preferences_account` (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `weekly_meeting_images`
--

DROP TABLE IF EXISTS `weekly_meeting_images`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `weekly_meeting_images` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `meeting_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size` int NOT NULL,
  `mime_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` int NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `meeting_id` (`meeting_id`),
  CONSTRAINT `weekly_meeting_images_ibfk_1` FOREIGN KEY (`meeting_id`) REFERENCES `weekly_meetings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `weekly_meeting_scans`
--

DROP TABLE IF EXISTS `weekly_meeting_scans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `weekly_meeting_scans` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `meeting_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_name` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size` int NOT NULL,
  `mime_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `meeting_id` (`meeting_id`),
  CONSTRAINT `weekly_meeting_scans_ibfk_1` FOREIGN KEY (`meeting_id`) REFERENCES `weekly_meetings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `weekly_meetings`
--

DROP TABLE IF EXISTS `weekly_meetings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `weekly_meetings` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `meeting_date` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `meeting_theme` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `location` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
  `host` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `recorder` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `attendees` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_items` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping routines for database 'itss_steeltech'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-09-17 23:29:38
