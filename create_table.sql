-- Do not run this file, tables are already created

-- USE `wfresh_db`;

-- === users ===
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `uid` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(50),
  `email` VARCHAR(30),
  `bio` TEXT
);

-- === dish ===
DROP TABLE IF EXISTS `dish`;
CREATE TABLE `dish` (
  `did` INT PRIMARY KEY AUTO_INCREMENT,
  `description` TEXT,
  `ingredient` TEXT
);

-- === post ===
DROP TABLE IF EXISTS `post`;
CREATE TABLE `post` (
  `postid` INT PRIMARY KEY AUTO_INCREMENT,
  `owner` INT,
  `description` TEXT
);

-- === threads ===
DROP TABLE IF EXISTS `threads`;
CREATE TABLE `threads` (
  `thid` INT PRIMARY KEY AUTO_INCREMENT,
  `postid` INT
);

-- === messages ===
DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages` (
  `mid` INT PRIMARY KEY AUTO_INCREMENT,
  `replyto` INT NULL,
  `sender` INT,
  `content` TEXT,
  `parentthread` INT,
  `sent_at` DATETIME
);

-- === menu ===
DROP TABLE IF EXISTS `menu`;
CREATE TABLE `menu` (
  `mid` INT PRIMARY KEY AUTO_INCREMENT,
  `dininghall` ENUM('lulu','stoned','bates','tower'),
  `mealtime`   ENUM('breakfast','lunch','dinner'),
  `dayofweek`  ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
);

-- === comments ===
DROP TABLE IF EXISTS `comments`;
CREATE TABLE `comments` (
  `commentid` INT PRIMARY KEY AUTO_INCREMENT,
  `owner` INT,
  `type` ENUM('yum','yuck'),
  `comment` TEXT,
  `filepath` TEXT,
  `dish` INT
);

-- === notification ===
DROP TABLE IF EXISTS `notification`;
CREATE TABLE `notification` (
  `nid` INT PRIMARY KEY AUTO_INCREMENT,
  `time` TEXT,
  `location` TEXT,
  `description` TEXT,
  `owner` INT
);

-- === dish_pictures ===
DROP TABLE IF EXISTS `dish_picture`;
CREATE TABLE `dish_picture` (
  `pid` INT PRIMARY KEY AUTO_INCREMENT, 
  `did` INT,
  filename VARCHAR(100),
);

-- === menu_dish (join) ===
DROP TABLE IF EXISTS `menu_dish`;
CREATE TABLE `menu_dish` (
  `menu_mid` INT,
  `dish_did` INT,
  PRIMARY KEY (`menu_mid`, `dish_did`)
);

-- === Foreign keys (defaults: RESTRICT/NO ACTION) ===
ALTER TABLE `post`
  ADD FOREIGN KEY (`owner`) REFERENCES `users` (`uid`);

ALTER TABLE `threads`
  ADD FOREIGN KEY (`postid`) REFERENCES `post` (`postid`);

ALTER TABLE `messages`
  ADD FOREIGN KEY (`replyto`) REFERENCES `messages` (`mid`);

ALTER TABLE `messages`
  ADD FOREIGN KEY (`sender`) REFERENCES `users` (`uid`);

ALTER TABLE `messages`
  ADD FOREIGN KEY (`parentthread`) REFERENCES `threads` (`thid`);

ALTER TABLE `comments`
  ADD FOREIGN KEY (`owner`) REFERENCES `users` (`uid`);

ALTER TABLE `comments`
  ADD FOREIGN KEY (`dish`) REFERENCES `dish` (`did`);

ALTER TABLE `notification`
  ADD FOREIGN KEY (`owner`) REFERENCES `users` (`uid`);

ALTER TABLE `menu_dish`
  ADD FOREIGN KEY (`menu_mid`) REFERENCES `menu` (`mid`);

ALTER TABLE `menu_dish`
  ADD FOREIGN KEY (`dish_did`) REFERENCES `dish` (`did`);

ALTER TABLE `dish_picture`
  ADD FOREIGN KEY (`did`) REFERENCES `dish` (`did`);