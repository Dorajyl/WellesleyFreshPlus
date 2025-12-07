# copied 
from flask import (Flask, render_template, make_response, url_for, request,
                   redirect, flash, session, send_from_directory, jsonify)
from werkzeug.utils import secure_filename
import os
import secrets
import cs304dbi as dbi
import requests
from datetime import date, datetime, timedelta
import helper

app = Flask(__name__)

# we need a secret_key to use flash() and sessions
app.secret_key = secrets.token_hex()

# configure DBI

# For Lookup, use 'wmdb'
# For CRUD and Ajax, use your personal db
# For project work, use your team db

print(dbi.conf('wfresh_db'))

# This gets us better error messages for certain common request errors
app.config['TRAP_BAD_REQUEST_ERRORS'] = True

# Picture upload: Save images into static/uploads/
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB maximum

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    '''Return True if the filename has an allowed extension.'''
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

# Ensure the uploads directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/home/', methods=['GET', 'POST'])
def index():
    # POST from side bar: Wellesley Feast form submission
    if request.method == 'POST':
        # read form from the sidebar
        free_food = request.form.get('free_food', '').strip()
        location = request.form.get('location', '').strip()
        time_text = request.form.get('time_text', '').strip()
        details = request.form.get('description', '').strip()  # optional

        # ensure all fields are filled
        if not free_food or not location or not time_text:
            flash('Please fill out food name, location, and time for Wellesley Feast.')
            return redirect(url_for('index'))

        # store event name(title) & details together in description column
        db_description = f'{free_food} – {details}' if details else free_food

        dbi.conf('wfresh_db')
        conn = dbi.connect()
        curs = conn.cursor()
        curs.execute(
            '''
            INSERT INTO notification (time, location, description, owner)
            VALUES (%s, %s, %s, %s)
            ''',
            [time_text, location, db_description, None]  # owner=None for now
        )
        conn.commit()

        # flash message
        flash_msg = (
            f'Feast: {free_food}\n'
            f'Where: {location}\n'
            f'When: {time_text}'
        )
        if details:
            flash_msg += f'\nDetails: {details}'

        flash(flash_msg)
        return redirect(url_for('index'))  # POST-Redirect-GET

    DINING_HALLS = {
        95: {  # Bates
            "name": "Bates",
            "meals": {
                "Breakfast": 145,
                "Lunch": 146,
                "Dinner": 311,
            },
        },
        131: {  # Stone D
            "name": "Stone D",
            "meals": {
                "Breakfast": 261,
                "Lunch": 262,
                "Dinner": 263,
            },
        },
        96: {  # Lulu
            "name": "Lulu",
            "meals": {
                "Breakfast": 148,
                "Lunch": 149,
                "Dinner": 312,
            },
        },
        97: {  # Tower
            "name": "Tower",
            "meals": {
                "Breakfast": 153,
                "Lunch": 154,
                "Dinner": 310,
            },
        },
    }
    MEALS = ["Breakfast", "Lunch", "Dinner"]

    today = date.today()
    meal_order = ["Breakfast", "Lunch", "Dinner"] 
    # now = datetime.now()
    # helper.get_meal_order(now) # reorder meals so current meal(dinner/lunch..) is first

    # Fetch week menu data (uses cache if available)
    week_menu = helper.fetch_week_menu(today)

    days = []
    for offset in range(7):
        # label and date for the day
        d = today + timedelta(days=offset)
        label = "Today" if offset == 0 else d.strftime("%A %b %-d")
        date_key = d.isoformat()  # '2025-11-15'

        # Get menu data from cache/fetched data
        # menus[meal_time][hall_name] = list of dishes
        menus = {}
        if date_key in week_menu:
            menus = week_menu[date_key]
        else:
            # Fallback: if date not in cache, fetch individually (shouldn't happen normally)
            for meal in MEALS:
                menus[meal] = {}
                for dhall_id, info in DINING_HALLS.items():
                    dishes = helper.fetch_menu_for(d, dhall_id, meal)
                    if dishes:
                        menus[meal][info["name"]] = dishes

        days.append(
            {
                "date": d,
                "label": label,
                "menus": menus,
            }
        )

    # fetch most recent 3 Wellesley Feast notifications for display
    dbi.conf('wfresh_db')
    conn = dbi.connect()
    curs = conn.cursor()
    curs.execute(
        '''
        SELECT nid, time, location, description
        FROM notification
        ORDER BY nid DESC
        LIMIT 3
        '''
    )
    feast_events = curs.fetchall()
    conn.close()

    return render_template(
        "main.html",
        days=days,
        meal_order=meal_order,
        feast_events=feast_events,
        page_title='Home'
    )

@app.route('/')
def about():
    return render_template('about.html', page_title='About Us')

# Login and Logout routes
@app.route('/login/', methods=['GET', 'POST'])
def login():
    dbi.conf('wfresh_db')
    
    if request.method == 'POST':
        email_handle = request.form.get('email_handle', '').strip()
        
        if not email_handle:
            flash('Please enter your email handle')
            return redirect(url_for('about'))
        
        conn = dbi.connect()
        cur = conn.cursor()
        
        # check if user exists with this email handle
        cur.execute('SELECT uid, name, email FROM users WHERE name = %s OR email = %s OR email LIKE %s', 
                   (email_handle, email_handle, f'{email_handle}@%'))
        user = cur.fetchone()
        
        if user is None:
            # First time login - create new user
            email = f'{email_handle}@wellesley.edu'
            cur.execute('''INSERT INTO users (name, email) 
                           VALUES (%s, %s)''',
                       (email_handle, email))
            conn.commit()
            user_id = cur.lastrowid
            
            # Fetch the newly created user
            cur.execute('SELECT uid, name, email FROM users WHERE uid = %s', (user_id,))
            user = cur.fetchone()
            flash(f'Welcome! Your account has been created. User ID: {user_id}')
        else:
            flash(f'Welcome back, {user[1]}!')
        
        # Store user info in session
        session['uid'] = user[0]
        session['name'] = user[1]
        session['email'] = user[2]
        
        conn.close()
        return redirect(url_for('about'))
    
    # GET request - just redirect to about page
    return redirect(url_for('about'))

@app.route('/logout/')
def logout():
    session.clear()
    flash('You have been logged out')
    return redirect(url_for('about'))

@app.route('/dishdash/', methods=['GET', 'POST'])
def dishdash():
    """DishDash front page: list threads and create new ones."""
    conn = dbi.connect()
    cur = dbi.dict_cursor(conn)

    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        if not description:
            flash('Please write something for your thread.')
            return redirect(url_for('dishdash'))

        # Get user ID from session (logged in user)
        owner_id = session.get('uid')
        if owner_id is None:
            flash('Please log in to create a thread')
            return redirect(url_for('about'))

        # 1) create post
        cur.execute(
            'INSERT INTO post (owner, description) VALUES (%s, %s)',
            (owner_id, description)
        )
        conn.commit()
        postid = cur.lastrowid

        # 2) create thread linked to that post
        cur.execute(
            'INSERT INTO threads (postid) VALUES (%s)',
            (postid,)
        )
        conn.commit()
        thid = cur.lastrowid

        flash('Thread created!')
        return redirect(url_for('view_thread', thid=thid))

    # GET: list all threads with basic info + message count
    cur.execute(
        '''
        SELECT t.thid,
               p.postid,
               p.description,
               u.name AS owner_name,
               (SELECT COUNT(*) FROM messages m WHERE m.parentthread = t.thid) AS msg_count
        FROM threads t
        JOIN post p ON t.postid = p.postid
        LEFT JOIN users u ON p.owner = u.uid
        ORDER BY t.thid DESC
        '''
    )
    threads = cur.fetchall()
    conn.close()

    return render_template('dishdash.html',
                           page_title='DishDash Forum',
                           threads=threads)

@app.route('/dishdash/thread/<thid>', methods=['GET', 'POST'])
def view_thread(thid):
    """View a single thread + messages, and post replies."""
    conn = dbi.connect()
    cur = dbi.dict_cursor(conn)
    # show one thred and all its nested messages
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        # get reply to and convert to int or None
        replyto_raw = request.form.get('replyto')
        replyto = int(replyto_raw) if replyto_raw else None
        # if empty content, flash error and redirect
        if not content:
            flash('Message cannot be empty.')
            # reload same thread page
            return redirect(url_for('view_thread', thid=thid))

        # Get user ID from session (logged in user)
        sender_id = session.get('uid')
        if sender_id is None:
            flash('Please log in to post a message')
            return redirect(url_for('about'))
        # insert new message to database
        cur.execute(
            '''INSERT INTO messages (replyto, sender, content, parentthread)
               VALUES (%s, %s, %s, %s)''',
            (replyto, sender_id, content, thid)
        )
        conn.commit()
        flash('Reply posted!')
        return redirect(url_for('view_thread', thid=thid))

    # GET: add a new message or reply to the thread
    cur.execute(
        '''
        SELECT t.thid,
               p.postid,
               p.description,
               u.name AS owner_name
        FROM threads t
        JOIN post p ON t.postid = p.postid
        LEFT JOIN users u ON p.owner = u.uid
        WHERE t.thid = %s
        ''',
        (thid,)
    )
    thread = cur.fetchone()
    if not thread:
        conn.close()
        flash('Thread not found.')
        return redirect(url_for('dishdash'))

    # load messages for this thread
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
    rows = cur.fetchall()
    conn.close()
    def build_message_tree(rows):
        """Turn flat messages into a nested tree using replyto."""
        by_id = {}
        roots = []
        # create the nodes
        for row in rows:
            node = {
                'mid': row['mid'],
                'replyto': row['replyto'],
                'sender': row['sender'],
                'content': row['content'],
                'parentthread': row['parentthread'],
                'sent_at': row['sent_at'],
                'sender_name': row['sender_name'],
                'children': []
            }
            by_id[node['mid']] = node
        # check assign and parent and the children, and find roots
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
    messages = build_message_tree(rows)

    return render_template('thread.html',
                           thread=thread,
                           messages=messages)

@app.route('/dishdash/thread/<thid>/delete/<mid>', methods=['POST'])
def delete_message(thid, mid):
    """
    Delete a single message (and its replies) from a thread.
    """
     # Perform recursive delete
    def delete_message_recursive(cur, mid):
        """
        Delete a message and all of its descendants.

        With the self-referential FK messages.replyto → messages.mid,
        we must delete children BEFORE deleting the parent.
        """
        # 1. Find all direct children of this message
        cur.execute('SELECT mid FROM messages WHERE replyto = %s', (mid,))
        rows = cur.fetchall()          # rows are dicts because we use dict_cursor

        # Extract child IDs as a simple Python list
        child_ids = [row['mid'] for row in rows]

        # 2. Recursively delete each child (and its children, etc.)
        for child_mid in child_ids:
            delete_message_recursive(cur, child_mid)

        # 3. Now delete THIS message (all its children are already gone)
        cur.execute('DELETE FROM messages WHERE mid = %s', (mid,))

    conn = dbi.connect()
    cur = dbi.dict_cursor(conn)

    # Make sure the message actually belongs to this thread
    cur.execute(
        'SELECT parentthread FROM messages WHERE mid = %s',
        (mid,)
    )
    row = cur.fetchone()
    if not row:
        flash('Message not found.')
    elif int(row['parentthread']) != int(thid):
        flash('Message does not belong to this thread.')
    else:
        delete_message_recursive(cur, mid)
        conn.commit()
        flash('Message and its replies have been deleted.')

    return redirect(url_for('view_thread', thid=thid))


# Testing data: hard boil egg 39186
@app.route('/dish/<did>', methods=['GET', 'POST'])
def get_dish(did):
    dbi.conf('wfresh_db')
    conn = dbi.connect()
    cur = conn.cursor()
    
    # Handle POST request (form submission)
    if request.method == 'POST':
        comment_text = request.form.get('comment', '').strip()
        comment_type = request.form.get('type', 'yum')
        file = request.files.get('picture') # upload dish pictures
        
        # Validate required fields
        # Allow either a comment, or a picture, or both
        if not comment_text and (not file or file.filename == ''):
            flash('You must enter a comment or upload a picture')
        else:
            # Get user ID from session (logged in user)
            owner_id = session.get('uid')
            
            # If user is not logged in, create or get anonymous user as fallback
            if owner_id is None:
                cur.execute('SELECT uid FROM users WHERE name = %s OR email = %s LIMIT 1', 
                           ('Anonymous', 'anonymous@example.com'))
                anonymous_user = cur.fetchone()
                
                if anonymous_user is None:
                    # Create an anonymous user if it doesn't exist
                    cur.execute('''INSERT INTO users (name, email) 
                                   VALUES (%s, %s)''',
                               ('Anonymous', 'anonymous@example.com'))
                    conn.commit()
                    owner_id = cur.lastrowid
                else:
                    owner_id = anonymous_user[0]
                
            # Picture upload path
            filepath = None
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"dish{did}_{filename}"
                fullpath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(fullpath)
                filepath = filename
            
            # Insert comment if comment_text is provided
            if comment_text:
                cur.execute(
                    '''INSERT INTO comments (dish, owner, type, comment)
                       VALUES (%s, %s, %s, %s)''',
                    (did, owner_id, comment_type, comment_text)
                )
                conn.commit()
            
            # Insert picture into dish_picture table if there's a picture but no comment
            if filepath and not comment_text:
                cur.execute(
                    '''INSERT INTO dish_picture (did, filename)
                       VALUES (%s, %s)''',
                    (did, filepath)
                )
                conn.commit()
            
            flash('Comment/Picture added successfully!')
            # Redirect to avoid duplicate submissions on refresh
            return redirect(url_for('get_dish', did=did))
    
    # Get dish information
    cur.execute('SELECT did, name, description FROM dish WHERE did = %s', (did,))
    row = cur.fetchone()
    if row is None:
        flash(f'No dish with id {did} found')
        return redirect(url_for('index'))
    
    dish = {
        'did': row[0],
        'name': row[1],
        'description': row[2]
    }
    
    # Get all comments for this dish
    cur.execute('''SELECT c.commentid, c.owner, c.type, c.comment,
                          u.name as owner_name
                   FROM comments c
                   LEFT JOIN users u ON c.owner = u.uid
                   WHERE c.dish = %s
                   ORDER BY c.commentid DESC''', (did,))
    comments = cur.fetchall()
    
    cur.execute('SELECT pid, filename FROM dish_picture WHERE did = %s', (did,))
    dish_pics = cur.fetchall()
    
    return render_template('dish.html', dish=dish, comments=comments, dish_pics=dish_pics)

# Delete pictures
@app.route('/dish/<did>/delete_pic/<int:pid>', methods=['POST'])
def delete_dish_pic(did, pid):
    dbi.conf('wfresh_db')
    conn = dbi.connect()
    cur = conn.cursor()

    # look up the filename for the pid + did
    cur.execute(
        'SELECT filename FROM dish_picture WHERE pid = %s AND did = %s',
        (pid, did)
    )
    row = cur.fetchone()
    if row is None:
        flash('Picture not found')
        return redirect(url_for('get_dish', did=did))

    filename = row[0]

    # delete the row from dish_picture
    cur.execute('DELETE FROM dish_picture WHERE pid = %s', (pid,))
    conn.commit()

    # delete the actual file from static/uploads
    cur.execute(
        'SELECT COUNT(*) FROM dish_picture WHERE filename = %s',
        (filename,)
    )
    count = cur.fetchone()[0]

    if count == 0:  # only delete file if no more db references
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass  # if it is already gone, ignore

    flash('Picture deleted.')
    return redirect(url_for('get_dish', did=did))

# Delete comments
@app.route('/dish/<did>/delete_comment/<int:commentid>', methods=['POST'])
def delete_comment(did, commentid):
    dbi.conf('wfresh_db')
    conn = dbi.connect()
    cur = conn.cursor()

    # Verify comment exists
    cur.execute(
        'SELECT commentid FROM comments WHERE commentid = %s AND dish = %s',
        (commentid, did)
    )
    row = cur.fetchone()
    if row is None:
        flash('Comment not found')
        return redirect(url_for('get_dish', did=did))

    # delete the comment from comments table
    cur.execute('DELETE FROM comments WHERE commentid = %s', (commentid,))
    conn.commit()

    flash('Comment deleted.')
    return redirect(url_for('get_dish', did=did))

if __name__ == '__main__':
    import sys, os
    if len(sys.argv) > 1:
        # arg, if any, is then the desired port number
        port = int(sys.argv[1])
        assert(port>1024)
    else:
        port = os.getuid()
    app.debug = True
    app.run('0.0.0.0',port)
