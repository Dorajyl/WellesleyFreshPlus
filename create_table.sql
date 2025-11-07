CREATE TABLE menu {
  mid INT PRIMARY KEY AUTO_INCREMENT
  dininghall ENUM ('lulu','stoned','bates','tower')
  mealtime ENUM('breakfast','lunch','dinner')
  dayofweek ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
}