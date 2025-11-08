USE `wfresh_db`;


DROP TABLE IF EXISTS `menu_dish`;
DROP TABLE IF EXISTS `notification`;
DROP TABLE IF EXISTS `comments`;
DROP TABLE IF EXISTS `menu`;
DROP TABLE IF EXISTS `messages`;
DROP TABLE IF EXISTS `threads`;
DROP TABLE IF EXISTS `post`;
DROP TABLE IF EXISTS `dish`;
DROP TABLE IF EXISTS `users`;
-- === users ===
CREATE TABLE `users` (
  `uid` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(50),
  `email` VARCHAR(30),
  `bio` TEXT
);

-- === dish ===
CREATE TABLE `dish` (
  `did` INT PRIMARY KEY,
  `name` VARCHAR(100),
  `description` TEXT,
  `filepath` TEXT
);

-- === post ===
CREATE TABLE `post` (
  `postid` INT PRIMARY KEY AUTO_INCREMENT,
  `owner` INT,
  `description` TEXT
);

-- === threads ===
CREATE TABLE `threads` (
  `thid` INT PRIMARY KEY AUTO_INCREMENT,
  `postid` INT
);

-- === messages ===
CREATE TABLE `messages` (
  `mid` INT PRIMARY KEY AUTO_INCREMENT,
  `replyto` INT NULL,
  `sender` INT,
  `content` TEXT,
  `parentthread` INT,
  `sent_at` DATETIME
);

-- === menu ===
CREATE TABLE `menu` (
  `mid` INT PRIMARY KEY AUTO_INCREMENT,
  `dininghall` ENUM('lulu','stoned','bates','tower'),
  `mealtime`   ENUM('breakfast','lunch','dinner'),
  `dayofweek`  ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
);

-- === comments ===
CREATE TABLE `comments` (
  `commentid` INT PRIMARY KEY AUTO_INCREMENT,
  `owner` INT,
  `type` ENUM('yum','yuck'),
  `comment` TEXT,
  `filepath` TEXT,
  `dish` INT
);

-- === notification ===
CREATE TABLE `notification` (
  `nid` INT PRIMARY KEY AUTO_INCREMENT,
  `time` TEXT,
  `location` TEXT,
  `description` TEXT,
  `owner` INT
);

-- === menu_dish (join) ===
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
