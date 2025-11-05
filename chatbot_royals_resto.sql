-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Nov 05, 2025 at 07:32 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `chatbot_royals_resto`
--

-- --------------------------------------------------------

--
-- Table structure for table `pertanyaan_unknow`
--

CREATE TABLE `pertanyaan_unknow` (
  `id` int(11) NOT NULL,
  `pertanyaan` varchar(300) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `pertanyaan_unknow`
--

INSERT INTO `pertanyaan_unknow` (`id`, `pertanyaan`) VALUES
(85, 'fdgdsg'),
(86, 'lapangan basket'),
(87, 'motogp mulai kapan?'),
(88, 'saya mau nasi goreng spesial'),
(89, 'tampilkan'),
(90, 'buatkan aluur penelitian');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `pertanyaan_unknow`
--
ALTER TABLE `pertanyaan_unknow`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `pertanyaan_unknow`
--
ALTER TABLE `pertanyaan_unknow`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=91;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
