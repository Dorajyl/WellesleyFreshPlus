CREATE TABLE `users` (
  `uid` integer PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(50),
  `email` varchar(30),
  `bio` text
);

CREATE TABLE `dish` (
  `did` integer PRIMARY KEY AUTO_INCREMENT,
  `description` text,
  `ingredient` text
);

CREATE TABLE `post` (
  `postid` integer PRIMARY KEY AUTO_INCREMENT,
  `owner` integer,
  `description` text
);

CREATE TABLE `messages` (
  `mid` integer PRIMARY KEY AUTO_INCREMENT,
  `replyto` integer,
  `sender` integer,
  `content` text,
  `parentthread` integer,
  `sent_at` datetime
);

CREATE TABLE `threads` (
  `thid` integer PRIMARY KEY AUTO_INCREMENT,
  `postid` integer
);

CREATE TABLE `menu` (
  `mid` integer PRIMARY KEY AUTO_INCREMENT,
  `dininghall` enum(lulu,stoned,bates,tower),
  `mealtime` enum(breakfast,lunch,dinner),
  `dayofweek` enum(Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday)
);

CREATE TABLE `comments` (
  `commentid` integer PRIMARY KEY AUTO_INCREMENT,
  `owner` integer,
  `type` enum(yum,yuck),
  `comment` text,
  `filepath` text,
  `dish` integer
);

CREATE TABLE `notification` (
  `nid` integer PRIMARY KEY AUTO_INCREMENT,
  `time` text,
  `location` text,
  `description` text,
  `owner` integer
);

ALTER TABLE `post` ADD FOREIGN KEY (`owner`) REFERENCES `users` (`uid`);

ALTER TABLE `messages` ADD FOREIGN KEY (`replyto`) REFERENCES `messages` (`mid`);

ALTER TABLE `messages` ADD FOREIGN KEY (`sender`) REFERENCES `users` (`uid`);

ALTER TABLE `messages` ADD FOREIGN KEY (`parentthread`) REFERENCES `threads` (`thid`);

ALTER TABLE `threads` ADD FOREIGN KEY (`postid`) REFERENCES `post` (`postid`);

ALTER TABLE `comments` ADD FOREIGN KEY (`owner`) REFERENCES `users` (`uid`);

ALTER TABLE `comments` ADD FOREIGN KEY (`dish`) REFERENCES `dish` (`did`);

ALTER TABLE `notification` ADD FOREIGN KEY (`owner`) REFERENCES `users` (`uid`);

CREATE TABLE `menu_dish` (
  `menu_mid` integer,
  `dish_did` integer,
  PRIMARY KEY (`menu_mid`, `dish_did`)
);

ALTER TABLE `menu_dish` ADD FOREIGN KEY (`menu_mid`) REFERENCES `menu` (`mid`);

ALTER TABLE `menu_dish` ADD FOREIGN KEY (`dish_did`) REFERENCES `dish` (`did`);

