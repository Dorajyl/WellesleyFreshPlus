"""
helper.py

Shared helper module for WFresh.

Contains:
1) AVI menu API + caching utilities
2) Database utility functions (connect, cursors)
3) Database CRUD helpers used by app.py routes:
   - Feast notifications
   - DishDash forum (threads/messages)
   - Dish pages (comments/pictures)
"""

import threading
import os
import json
from datetime import date, datetime, timedelta
import requests
import cs304dbi as dbi

DB_NAME = "wfresh_db"

# Lock for anything that touches global-ish config or shared files
_dbi_lock = threading.Lock()
_cache_lock = threading.Lock()

# Wellesley Fresh API
AVI_API = "https://dish.avifoodsystems.com/api/menu-items/week"

# ------------------------------------------------------------------------------------
# Menu API + caching (AVI)
# ------------------------------------------------------------------------------------

# Dining hall + meal IDs
DINING_HALLS = {
    95: {"name": "Bates", "meals": {"Breakfast": 145, "Lunch": 146, "Dinner": 311}},
    131: {"name": "Stone D", "meals": {"Breakfast": 261, "Lunch": 262, "Dinner": 263}},
    96: {"name": "Lulu", "meals": {"Breakfast": 148, "Lunch": 149, "Dinner": 312}},
    97: {"name": "Tower", "meals": {"Breakfast": 153, "Lunch": 154, "Dinner": 310}},
}
MEALS = ["Breakfast", "Lunch", "Dinner"]

# Upload extensions we accept for pictures
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename: str) -> bool:
    """
    Return True if filename extension is allowed (png/jpg/jpeg/gif).
    """
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_meal_order(now: datetime) -> list[str]:
    """
    Reorder Breakfast/Lunch/Dinner so that the "current" meal appears first.
    """
    h = now.hour
    if h < 10:
        return ["Breakfast", "Lunch", "Dinner"]
    elif h < 15:
        return ["Lunch", "Dinner", "Breakfast"]
    else:
        return ["Dinner", "Breakfast", "Lunch"]


def fetch_menu_for(d: date, dhall_id: int, meal_name: str) -> list[dict]:
    """
    Call AVI API and return a list of dishes for a specific dining hall and meal, filtered to that date.

    Args:
        d: date object for which we want dishes
        dhall_id: AVI locationId
        meal_name: "Breakfast" | "Lunch" | "Dinner"

    Returns:
        List of dish dicts: {did, name, station}
    """
    meal_id = DINING_HALLS[dhall_id]["meals"][meal_name]

    resp = requests.get(
        AVI_API,
        params={
            "date": d.strftime("%-m/%-d/%y"),  # e.g. '11/15/25'
            "locationId": dhall_id,
            "mealId": meal_id,
        },
        verify=False,
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json() or []

    target_iso = d.isoformat()
    dishes: list[dict] = []

    # API returns a full week; filter to the requested day.
    for dish in data:
        dish_date_raw = (dish.get("date") or "")[:10]
        if dish_date_raw != target_iso:
            continue

        dishes.append(
            {
                "did": dish.get("id"),
                "name": dish.get("name"),
                "station": dish.get("stationName"),
            }
        )

    return dishes


def get_cache_filepath():
    """Return the absolute path to the menu cache file."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'menu_cache.json')



def is_cache_valid(cache_data: dict) -> bool:
    """
    Check if cached data is still valid (<= 1 day old).

    This helps avoid stale menus and handles late-night edge cases.
    """
    if not cache_data or 'cached_date' not in cache_data:
        return False

    cached_date_str = cache_data['cached_date']
    try:
        cached_date = datetime.fromisoformat(cached_date_str).date()
        today = date.today()
        return (today - cached_date).days <= 1
    except (ValueError, TypeError):
        return False


def load_menu_cache():
    """Thread-safe cache read."""
    cache_file = get_cache_filepath()

    with _cache_lock:
        if not os.path.exists(cache_file):
            return None
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            if is_cache_valid(cache_data):
                return cache_data.get('menu_data', None)
            return None
        except (json.JSONDecodeError, IOError, KeyError):
            return None



def save_menu_cache(menu_data: dict):
    """
    Thread-safe cache write:
    - lock to prevent concurrent writers
    - write to temp, then atomic replace
    """
    cache_file = get_cache_filepath()
    tmp_file = cache_file + ".tmp"

    cache_data = {
        'cached_date': datetime.now().isoformat(),
        'menu_data': menu_data
    }

    with _cache_lock:
        try:
            with open(tmp_file, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            os.replace(tmp_file, cache_file)  # atomic on POSIX
        except IOError:
            # If we can't write the cache, continue without it
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except OSError:
                pass


def fetch_week_menu(start_date: date = None):
    """
    Fetch menu data for 7 days starting at start_date (or today if None).
    Uses cache when available.

    Returns:
        dict:
          { "YYYY-MM-DD": { "Breakfast": {"Bates": [...], ...}, "Lunch": {...}, ... }, ... }
    """
    if start_date is None:
        start_date = date.today()

    cached_data = load_menu_cache()
    if cached_data is not None:
        return cached_data

    # Cache miss: fetch fresh.
    week_menu = {}
    for offset in range(7):
        d = start_date + timedelta(days=offset)
        date_key = d.isoformat()
        week_menu[date_key] = {}

        for meal in MEALS:
            week_menu[date_key][meal] = {}
            for dhall_id, info in DINING_HALLS.items():
                dishes = fetch_menu_for(d, dhall_id, meal)
                if dishes:
                    week_menu[date_key][meal][info["name"]] = dishes

    save_menu_cache(week_menu)
    return week_menu

# ------------------------------------------------------------------------------------
# Database helpers (thread-safe)
# ------------------------------------------------------------------------------------
DB_NAME = "wfresh_db"

# Lock to protect dbi.conf() (may mutate global state inside cs304dbi)
_dbi_lock = threading.Lock()


def db_connect(dict_cursor: bool = False):
    """
    Create and return a new DB connection for the current request/thread.

    Thread-safe approach:
    - Never reuse a global connection
    - Protect dbi.conf() since it may mutate shared/global config

    Args:
        dict_cursor: if True, returns a dict_cursor; otherwise normal cursor

    Returns:
        (conn, cursor)
    """
    with _dbi_lock:
        dbi.conf(DB_NAME)

    conn = dbi.connect()
    if dict_cursor:
        return conn, dbi.dict_cursor(conn)
    return conn, conn.cursor()


# ------------------------------------------------------------------------------------
# Feast notifications (thread-safe)
# ------------------------------------------------------------------------------------
def insert_feast_notification(owner_uid, time_text: str, location: str, description: str):
    """
    Insert a new feast notification.

    Thread safe:
    - New connection per call
    - Transaction with commit/rollback
    - Always closes connection
    """
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            INSERT INTO notification (time, location, description, owner)
            VALUES (%s, %s, %s, %s)
            ''',
            (time_text, location, description, owner_uid)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_recent_feast_events(limit: int = 3):
    """
    Fetch the most recent feast notifications.

    Returns:
        list of tuples: (nid, time, location, description)
    """
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            SELECT nid, time, location, description
            FROM notification
            ORDER BY nid DESC
            LIMIT %s
            ''',
            (limit,)
        )
        return cur.fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------------------------
# DishDash forum: threads/messages (thread-safe)
# ------------------------------------------------------------------------------------
def create_thread(owner_uid, description: str) -> int:
    """
    Create a new thread.

    Implementation:
    - Insert into post(owner, description) -> postid
    - Insert into threads(postid) -> thid

    Thread safe:
    - Single transaction (commit once) to avoid partial state if an error occurs

    Returns:
        thid (int)
    """
    conn, cur = db_connect(dict_cursor=True)
    try:
        cur.execute(
            'INSERT INTO post (owner, description) VALUES (%s, %s)',
            (owner_uid, description)
        )
        postid = cur.lastrowid

        cur.execute('INSERT INTO threads (postid) VALUES (%s)', (postid,))
        thid = cur.lastrowid

        conn.commit()
        return thid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_threads():
    """
    List all threads with owner name and message count.

    Returns:
        list[dict]
    """
    conn, cur = db_connect(dict_cursor=True)
    try:
        cur.execute(
            '''
            SELECT t.thid,
                   p.postid,
                   p.description,
                   p.owner AS owner_id,
                   u.name AS owner_name,
                   (SELECT COUNT(*) FROM messages m
                     WHERE m.parentthread = t.thid) AS msg_count
            FROM threads t
            JOIN post p ON t.postid = p.postid
            LEFT JOIN users u ON p.owner = u.uid
            ORDER BY t.thid DESC
            '''
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_thread(thid: int):
    """
    Get a single thread row.

    Returns:
        dict row or None
    """
    conn, cur = db_connect(dict_cursor=True)
    try:
        cur.execute(
            '''
            SELECT t.thid,
                   p.postid,
                   p.description,
                   p.owner AS owner_id,
                   u.name AS owner_name
            FROM threads t
            JOIN post p ON t.postid = p.postid
            LEFT JOIN users u ON p.owner = u.uid
            WHERE t.thid = %s
            ''',
            (thid,)
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_thread_messages(thid: int):
    """
    Fetch all messages for a thread.

    Returns:
        list[dict] ordered by sent_at
    """
    conn, cur = db_connect(dict_cursor=True)
    try:
        cur.execute(
            '''
            SELECT m.mid, m.replyto, m.sender, m.content,
                   m.parentthread, m.sent_at,
                   u.name AS sender_name
            FROM messages m
            LEFT JOIN users u ON m.sender = u.uid
            WHERE m.parentthread = %s
            ORDER BY m.sent_at ASC
            ''',
            (thid,)
        )
        return cur.fetchall()
    finally:
        conn.close()


def insert_message(sender_uid, thid: int, content: str, replyto=None):
    """
    Insert a new message into a thread.

    Thread safe:
    - New connection per call
    - commit/rollback
    """
    conn, cur = db_connect(dict_cursor=True)
    try:
        cur.execute(
            '''
            INSERT INTO messages (replyto, sender, content, parentthread, sent_at)
            VALUES (%s, %s, %s, %s, NOW())
            ''',
            (replyto, sender_uid, content, thid)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_message_recursive(cur, mid: int):
    """
    Recursively delete message mid and all descendant replies.

    IMPORTANT:
    - Must delete children before parents to satisfy FK constraints.
    - This function expects a dict_cursor from the SAME connection/transaction.
    """
    cur.execute('SELECT mid FROM messages WHERE replyto = %s', (mid,))
    rows = cur.fetchall()

    child_ids = [row['mid'] for row in rows]

    for child_mid in child_ids:
        delete_message_recursive(cur, child_mid)

    cur.execute('DELETE FROM messages WHERE mid = %s', (mid,))


def delete_thread(owner_uid, thid: int):
    """
    Delete a thread if owner_uid owns it.

    Thread-safe:
    - Entire operation in one transaction
    - Optional row lock on thread row to avoid concurrent delete races

    Returns:
        (ok: bool, message: str)
    """
    conn, cur = db_connect(dict_cursor=True)
    try:
        # Lock the row so two deletes don't interleave (MySQL/InnoDB supports FOR UPDATE)
        cur.execute(
            '''
            SELECT t.thid, p.postid, p.owner AS owner_id
            FROM threads t
            JOIN post p ON t.postid = p.postid
            WHERE t.thid = %s
            FOR UPDATE
            ''',
            (thid,)
        )
        row = cur.fetchone()

        if not row:
            conn.rollback()
            return False, "Thread not found."

        if int(row['owner_id']) != int(owner_uid):
            conn.rollback()
            return False, "You can only delete threads you created."

        postid = row['postid']

        # Delete all messages in this thread (recursive)
        cur.execute('SELECT mid FROM messages WHERE parentthread = %s', (thid,))
        msg_rows = cur.fetchall()
        for m in msg_rows:
            delete_message_recursive(cur, m['mid'])

        # Delete thread + post
        cur.execute('DELETE FROM threads WHERE thid = %s', (thid,))
        cur.execute('DELETE FROM post WHERE postid = %s', (postid,))

        conn.commit()
        return True, "Thread deleted."
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_message(sender_uid, thid: int, mid: int):
    """
    Delete a message (and replies) if sender_uid owns it and it belongs to thid.

    Thread-safe:
    - Transaction + optional row lock on the message row

    Returns:
        (ok: bool, message: str)
    """
    conn, cur = db_connect(dict_cursor=True)
    try:
        # Lock the message row so concurrent deletes/edits can't race
        cur.execute(
            '''
            SELECT parentthread, sender
            FROM messages
            WHERE mid = %s
            FOR UPDATE
            ''',
            (mid,)
        )
        row = cur.fetchone()

        if not row:
            conn.rollback()
            return False, "Message not found."

        if int(row['parentthread']) != int(thid):
            conn.rollback()
            return False, "Message does not belong to this thread."

        if int(row['sender']) != int(sender_uid):
            conn.rollback()
            return False, "You can only delete your own messages."

        delete_message_recursive(cur, mid)
        conn.commit()
        return True, "Message and its replies have been deleted."
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_message_tree(rows):
    """
    Convert a flat list of message rows into a nested tree.

    Pure-Python (no shared state) => thread-safe.
    """
    by_id = {}
    roots = []

    for row in rows:
        node = {
            'mid': row['mid'],
            'replyto': row['replyto'],
            'sender': row['sender'],
            'content': row['content'],
            'parentthread': row['parentthread'],
            'sent_at': row['sent_at'],
            'sender_name': row.get('sender_name'),
            'children': []
        }
        by_id[node['mid']] = node

    for node in by_id.values():
        parent_id = node['replyto']
        if parent_id is None:
            roots.append(node)
        else:
            parent = by_id.get(parent_id)
            if parent:
                parent['children'].append(node)
            else:
                roots.append(node)

    return roots


# ------------------------------------------------------------------------------------
# Dish: comments/pictures (thread-safe)
# ------------------------------------------------------------------------------------
def get_dish(did):
    """Fetch dish info as dict or None."""
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute('SELECT did, name, description FROM dish WHERE did = %s', (did,))
        row = cur.fetchone()
        if row is None:
            return None
        return {'did': row[0], 'name': row[1], 'description': row[2]}
    finally:
        conn.close()


def get_dish_comments(did):
    """
    Fetch comments for dish with owner info.
    Returns rows:
      (commentid, owner_uid, type, comment_text, owner_name)
    """
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            SELECT c.commentid, c.owner, c.type, c.comment,
                   u.name as owner_name
            FROM comments c
            LEFT JOIN users u ON c.owner = u.uid
            WHERE c.dish = %s
            ORDER BY c.commentid DESC
            ''',
            (did,)
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_dish_pics(did):
    """
    Fetch pictures for dish with owner info.
    Returns rows:
      (pid, filename, owner_uid, owner_name)

    NOTE: requires dish_picture.owner column.
    """
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            SELECT dp.pid, dp.filename, dp.owner, u.name
            FROM dish_picture dp
            LEFT JOIN users u ON dp.owner = u.uid
            WHERE dp.did = %s
            ORDER BY dp.pid DESC
            ''',
            (did,)
        )
        return cur.fetchall()
    finally:
        conn.close()


def add_dish_comment(uid, did, comment_type: str, comment_text: str):
    """Insert a dish comment owned by uid (transaction safe)."""
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            INSERT INTO comments (dish, owner, type, comment)
            VALUES (%s, %s, %s, %s)
            ''',
            (did, uid, comment_type, comment_text)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_dish_picture(did, filename: str, owner_uid):
    """
    Insert a dish picture record owned by owner_uid.
    Requires dish_picture.owner column.
    """
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            INSERT INTO dish_picture (did, filename, owner)
            VALUES (%s, %s, %s)
            ''',
            (did, filename, owner_uid)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_dish_picture(did, pid: int, requester_uid):
    """
    Delete a dish picture if requester_uid owns it.

    Thread-safe:
    - Row lock on the target picture row (FOR UPDATE)
    - Transaction + commit/rollback
    """
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            SELECT filename, owner
            FROM dish_picture
            WHERE pid = %s AND did = %s
            FOR UPDATE
            ''',
            (pid, did)
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return False, "Picture not found.", None

        filename, owner = row[0], row[1]

        if owner is None or int(owner) != int(requester_uid):
            conn.rollback()
            return False, "You can only delete pictures you uploaded.", None

        cur.execute('DELETE FROM dish_picture WHERE pid = %s', (pid,))

        # Check if any other DB row references same filename BEFORE commit
        cur.execute('SELECT COUNT(*) FROM dish_picture WHERE filename = %s', (filename,))
        count = cur.fetchone()[0]

        conn.commit()

        if count == 0:
            return True, "Picture deleted.", filename
        return True, "Picture deleted.", None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_dish_comment(did, commentid: int, requester_uid):
    """
    Delete a dish comment only if requester_uid owns it.

    Thread-safe:
    - Row lock on comment row (FOR UPDATE)
    - Transaction + commit/rollback
    """
    conn, cur = db_connect(dict_cursor=False)
    try:
        cur.execute(
            '''
            SELECT owner
            FROM comments
            WHERE commentid = %s AND dish = %s
            FOR UPDATE
            ''',
            (commentid, did)
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return False, "Comment not found."

        owner = row[0]
        if owner is None or int(owner) != int(requester_uid):
            conn.rollback()
            return False, "You can only delete your own comments."

        cur.execute('DELETE FROM comments WHERE commentid = %s', (commentid,))
        conn.commit()
        return True, "Comment deleted."
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
