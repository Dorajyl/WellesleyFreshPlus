use wfresh_db;
-- 0) (optional) See which users will be affected
SELECT uid, name, email, hashed
FROM users
WHERE hashed = 'password';

-- 1) Delete comments owned by those users
DELETE c
FROM comments AS c
JOIN users AS u ON c.owner = u.uid
WHERE u.hashed = 'password';

-- 2) Delete notifications owned by those users
DELETE n
FROM notification AS n
JOIN users AS u ON n.owner = u.uid
WHERE u.hashed = 'password';

-- 3) Delete messages that either:
--    - are sent by those users, OR
--    - belong to threads whose posts are owned by those users
DELETE m
FROM messages AS m
LEFT JOIN threads t   ON m.parentthread = t.thid
LEFT JOIN post    p   ON t.postid       = p.postid
LEFT JOIN users   u_p ON p.owner        = u_p.uid
LEFT JOIN users   u_s ON m.sender       = u_s.uid
WHERE u_p.hashed = 'password'
   OR u_s.hashed = 'password';

-- 4) Delete threads whose posts are owned by those users
DELETE t
FROM threads AS t
JOIN post   p ON t.postid = p.postid
JOIN users  u ON p.owner  = u.uid
WHERE u.hashed = 'password';

-- 5) Delete posts owned by those users
DELETE p
FROM post AS p
JOIN users u ON p.owner = u.uid
WHERE u.hashed = 'password';

-- 6) Finally, delete the users with bad hashes
DELETE FROM users
WHERE hashed = 'password';
