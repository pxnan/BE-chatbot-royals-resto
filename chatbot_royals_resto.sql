-- --------------------------------------------------------
-- Host:                         127.0.0.1
-- Server version:               8.4.3 - MySQL Community Server - GPL
-- Server OS:                    Win64
-- HeidiSQL Version:             12.8.0.6908
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Dumping database structure for chatbot_royals_resto
CREATE DATABASE IF NOT EXISTS `chatbot_royals_resto` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `chatbot_royals_resto`;

-- Dumping structure for table chatbot_royals_resto.admin
CREATE TABLE IF NOT EXISTS `admin` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `email` varchar(100) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `role` enum('super_admin','admin') DEFAULT 'admin',
  `is_active` tinyint(1) DEFAULT '1',
  `last_login` datetime DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table chatbot_royals_resto.admin: ~3 rows (approximately)
INSERT INTO `admin` (`id`, `username`, `password`, `email`, `full_name`, `role`, `is_active`, `last_login`, `created_at`, `updated_at`) VALUES
	(3, 'admin', '$2b$12$Ue36V8knkMAUFriiozuVUOaeUg/grr/Ctis3PpGk2GyvXtSc5IeJC', 'admin@royalsresto.com', 'Administrator', 'super_admin', 1, '2026-04-28 23:23:10', '2026-04-19 14:17:41', '2026-04-28 14:23:10'),
	(4, 'pras', '$2b$12$twaNjT3Fmh.91w4UY.xGzuqTiQ4pk0M07gt86E99sybZV7YeuGwRu', 'prasastimuslim@gmail.com', 'Prasasti M Fernanday', 'admin', 1, '2026-04-28 23:20:46', '2026-04-19 14:25:34', '2026-04-28 14:20:46'),
	(5, 'manager', '$2b$12$7aXfe4BGaSVO2ggkC04NZOLsfmYB1EXCyQh88AiFppZDdWeu3Diii', 'manager@gmail.com', 'David', 'super_admin', 1, '2026-05-02 23:07:06', '2026-04-26 18:13:35', '2026-05-02 14:07:06');

-- Dumping structure for table chatbot_royals_resto.admin_sessions
CREATE TABLE IF NOT EXISTS `admin_sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int NOT NULL,
  `session_token` varchar(255) NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` text,
  `expires_at` datetime NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `session_token` (`session_token`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `admin_sessions_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table chatbot_royals_resto.admin_sessions: ~4 rows (approximately)
INSERT INTO `admin_sessions` (`id`, `admin_id`, `session_token`, `ip_address`, `user_agent`, `expires_at`, `created_at`) VALUES
	(22, 5, 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbl9pZCI6NSwidXNlcm5hbWUiOiJtYW5hZ2VyIiwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzc3MzI4NzM0LCJpYXQiOjE3NzcyNDIzMzR9.H4daaVY7TkZiGTux-y9o74Q-J7p8EoP2JPgkHeRWOlM', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', '2026-04-27 22:25:35', '2026-04-26 22:25:34'),
	(26, 5, 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbl9pZCI6NSwidXNlcm5hbWUiOiJtYW5hZ2VyIiwicm9sZSI6InN1cGVyX2FkbWluIiwiZXhwIjoxNzc3NDcyMjcwLCJpYXQiOjE3NzczODU4NzB9.-MlU0WTUW1hMRbWE91YL7_dm-EnXZMdMraIufp06P2U', '127.0.0.1', 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1', '2026-04-29 14:17:50', '2026-04-28 14:17:50'),
	(27, 4, 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbl9pZCI6NCwidXNlcm5hbWUiOiJwcmFzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzc3NDcyNDQ2LCJpYXQiOjE3NzczODYwNDZ9._a2x4kP6ci6ZqDXIi6fHDRMMa46XXoqFvAwVaH2kde0', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', '2026-04-29 14:20:47', '2026-04-28 14:20:46'),
	(28, 3, 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbl9pZCI6MywidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJzdXBlcl9hZG1pbiIsImV4cCI6MTc3NzQ3MjUyMCwiaWF0IjoxNzc3Mzg2MTIwfQ.ZrHaIi4pFRsGF6iJblWV3_UPeNMNSg69GWaoM9lF-Yo', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', '2026-04-29 14:22:01', '2026-04-28 14:22:00');

-- Dumping structure for table chatbot_royals_resto.login_logs
CREATE TABLE IF NOT EXISTS `login_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `admin_id` int DEFAULT NULL,
  `username` varchar(50) NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` text,
  `login_status` enum('success','failed') NOT NULL,
  `failed_reason` varchar(255) DEFAULT NULL,
  `login_time` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `admin_id` (`admin_id`),
  CONSTRAINT `login_logs_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `admin` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=39 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Dumping data for table chatbot_royals_resto.login_logs: ~35 rows (approximately)
INSERT INTO `login_logs` (`id`, `admin_id`, `username`, `ip_address`, `user_agent`, `login_status`, `failed_reason`, `login_time`) VALUES
	(1, NULL, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Password salah', '2026-04-19 14:12:04'),
	(2, NULL, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Password salah', '2026-04-19 14:12:29'),
	(3, NULL, 'admin@royalsresto.com', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Username tidak ditemukan', '2026-04-19 14:12:55'),
	(4, NULL, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Password salah', '2026-04-19 14:12:59'),
	(5, NULL, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Password salah', '2026-04-19 14:15:45'),
	(6, NULL, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Password salah', '2026-04-19 14:15:47'),
	(7, NULL, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Password salah', '2026-04-19 14:15:51'),
	(8, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:18:10'),
	(9, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:18:25'),
	(10, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:22:51'),
	(11, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:25:58'),
	(12, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:26:15'),
	(13, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:28:55'),
	(14, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:41:15'),
	(15, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-19 14:41:50'),
	(16, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 16:47:04'),
	(17, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 16:48:25'),
	(18, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 17:36:40'),
	(19, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 17:36:54'),
	(20, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 17:39:54'),
	(21, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 17:40:13'),
	(22, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 18:06:17'),
	(23, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1', 'success', NULL, '2026-04-26 18:10:29'),
	(24, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 18:11:26'),
	(25, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 18:12:13'),
	(26, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 18:12:21'),
	(27, 5, 'manager', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 18:15:15'),
	(28, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'failed', 'Akun tidak aktif', '2026-04-26 18:15:29'),
	(29, 5, 'manager', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 18:15:35'),
	(30, 5, 'manager', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-26 22:25:34'),
	(31, 5, 'manager', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-28 14:12:09'),
	(32, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-28 14:13:03'),
	(33, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-28 14:13:16'),
	(34, 5, 'manager', '127.0.0.1', 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1', 'success', NULL, '2026-04-28 14:17:50'),
	(35, 4, 'pras', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-28 14:20:46'),
	(36, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-04-28 14:22:00'),
	(37, 3, 'admin', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0', 'success', NULL, '2026-04-28 14:23:10'),
	(38, 5, 'manager', '127.0.0.1', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36', 'success', NULL, '2026-05-02 14:07:06');

-- Dumping structure for table chatbot_royals_resto.pertanyaan_unknow
CREATE TABLE IF NOT EXISTS `pertanyaan_unknow` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pertanyaan` varchar(300) COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=130 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Dumping data for table chatbot_royals_resto.pertanyaan_unknow: ~15 rows (approximately)
INSERT INTO `pertanyaan_unknow` (`id`, `pertanyaan`, `created_at`) VALUES
	(105, 'motogp 2026 marc marquez JUARAAAA', '2026-04-17 02:29:26'),
	(106, 'MARC JUARA 1', '2026-04-17 02:29:26'),
	(107, 'marc vs bezzeci', '2026-04-17 02:29:26'),
	(112, 'motogp 2026', '2026-04-17 02:29:26'),
	(113, 'motogp 2025', '2026-04-17 02:29:26'),
	(114, 'f1 2026 lando norris', '2026-04-17 02:29:26'),
	(115, 'vegetariant?', '2026-04-17 02:29:26'),
	(116, 'ada parkiran?', '2026-04-17 02:29:26'),
	(117, 'ada menu apa saja?', '2026-04-17 02:29:26'),
	(118, 'dftr mnu?', '2026-04-17 02:29:26'),
	(121, 'blablablabal', '2026-04-27 02:43:05'),
	(122, 'fasfe', '2026-04-27 02:50:52'),
	(123, 'faefsrf', '2026-04-27 02:51:22'),
	(124, 'vsadv', '2026-04-27 03:07:40'),
	(129, 'ada menu apa saja?', '2026-04-27 08:52:12');

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
