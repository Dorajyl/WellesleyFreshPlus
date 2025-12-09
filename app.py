# copied 
from flask import (Flask, render_template, make_response, url_for, request,
                   redirect, flash, session, send_from_directory, jsonify)
from werkzeug.utils import secure_filename
import os
import secrets
import cs304dbi as dbi
import cs304login as auth
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
    """
    Check if a filename has an allowed image extension.
    
    Args:
        filename (str): The filename to check
        
    Returns:
        bool: True if the file extension is in ALLOWED_EXTENSIONS, False otherwise
    """
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

# Ensure the uploads directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/home/', methods=['GET', 'POST'])
def index():
    """
    Home page route - displays weekly menu and handles Wellesley Feast submissions.
    
    GET: Displays the weekly menu for all dining halls with cached data,
         and shows the 3 most recent Wellesley Feast notifications.
    
    POST: Handles Wellesley Feast form submission from sidebar.
          Creates a new notification entry in the database.
    
    Returns:
        render_template: Renders main.html with menu data and feast events
        redirect: Redirects to index after POST (POST-Redirect-GET pattern)
    """
    # POST from side bar: Wellesley Feast form submission
    if request.method == 'POST':
        # read form from the sidebar
        free_food = request.form.get('free_food', '').strip()
        location = request.form.get('location', '').strip()
        time_text = request.form.get('time_text', '').strip()
        # details = request.form.get('description', '').strip()  # optional

        # ensure all fields are filled
        if not free_food or not location or not time_text:
            flash('Please fill out food name, location, and time for Wellesley Feast.')
            return redirect(url_for('index'))

        # store event name(title) & details together in description column
        # db_description = f'{free_food} – {details}' if details else free_food
        db_description = free_food
        
        dbi.conf('wfresh_db')
        conn = dbi.connect()
        curs = conn.cursor()
        curs.execute(
            '''
            INSERT INTO notification (time, location, description, owner)
            VALUES (%s, %s, %s, %s)
            ''',
            [time_text, location, db_description, session.get('uid', None)]  # owner=None for now
        )
        conn.commit()

        # flash message
        flash_msg = (
            f'Feast: {free_food}\n'
            f'Where: {location}\n'
            f'When: {time_text}'
        )
        # if details:
        #     flash_msg += f'\nDetails: {details}'

        flash(flash_msg)
        return redirect(url_for('index'))  # POST-Redirect-GET

    # GET request: show home page with menus
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
    """
    About page route - displays information about the application.
    
    Returns:
        render_template: Renders about.html with page title
    """
    return render_template('about.html', page_title='About Us')

@app.route('/join/', methods=["POST"])
def join():
    """
    User registration route - creates a new user account.
    
    Accepts username and password from form, validates that passwords match,
    and creates a new user in the database. On success, logs the user in
    and sets session variables.
    
    Returns:
        redirect: Redirects to about page with flash message indicating success or error
    """
    username = request.form.get('username')
    passwd1 = request.form.get('password1')
    passwd2 = request.form.get('password2')
    if passwd1 != passwd2:
        flash('passwords do not match')
        return redirect( url_for('about'))
    conn = dbi.connect()
    (uid, is_dup, other_err) = auth.insert_user(conn, username, passwd1)
    if other_err:
        raise other_err
    if is_dup:
        flash('Sorry; that username is taken')
        return redirect( url_for('about'))
    ## success
    flash('FYI, you were issued UID {}'.format(uid))
    session['username'] = username
    session['uid'] = uid
    session['logged_in'] = True
    return redirect( url_for('about'))

@app.route('/login/', methods=["POST"])
def login():
    """
    User login route - authenticates user and creates session.
    
    Accepts username and password from form, verifies credentials against database.
    On successful login, sets session variables (username, uid, logged_in).
    
    Returns:
        redirect: Redirects to about page with flash message indicating success or failure
    """
    username = request.form.get('username')
    passwd = request.form.get('password')
    conn = dbi.connect()
    (ok, uid) = auth.login_user(conn, username, passwd)
    if not ok:
        flash('login incorrect, please try again or join')
        return redirect( url_for('about'))
    ## success
    print('LOGIN', username)
    flash('successfully logged in as '+username)
    session['username'] = username
    session['uid'] = uid
    session['logged_in'] = True
    return redirect( url_for('about'))

@app.route('/logout/')
def logout():
    """
    User logout route - clears session and logs user out.
    
    Removes username, uid, and logged_in from session. If user was not logged in,
    displays appropriate message.
    
    Returns:
        redirect: Redirects to about page with flash message
    """
    if 'username' in session:
        username = session['username']
        session.pop('username')
        session.pop('uid')
        session.pop('logged_in')
        flash('You are logged out')
        return redirect( url_for('about'))
    else:
        flash('you are not logged in. Please login or join')
        return redirect( url_for('about'))

@app.route('/dishdash/', methods=['GET', 'POST'])
def dishdash():
    """
    DishDash forum front page - lists all threads and handles thread creation.
    
    GET: Displays all threads with their descriptions, owners, and message counts.
         Threads are ordered by most recent first.
    
    POST: Creates a new thread from form submission. Creates both a post entry
          and a thread entry linked to that post.
    
    Returns:
        render_template: Renders dishdash.html with threads list and current user ID
        redirect: Redirects to view_thread after creating new thread, or back to dishdash on error
    """
    dbi.conf('wfresh_db')
    conn = dbi.connect()
    cur = dbi.dict_cursor(conn)

    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        if not description:
            flash('Please write something for your thread.')
            conn.close()
            return redirect(url_for('dishdash'))

        owner_id = session.get('uid',1)  # default to user 1 if not logged in

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

        conn.close()
        flash('Thread created!')
        return redirect(url_for('view_thread', thid=thid))

    # GET: list all threads with basic info + message count
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
    threads = cur.fetchall()
    conn.close()

    current_uid = session.get('uid')

    return render_template('dishdash.html',
                           page_title='DishDash Forum',
                           threads=threads,
                           current_uid=current_uid)

def build_message_tree(rows):
    """
    Convert a flat list of messages into a nested tree structure.
    
    Takes a list of message dictionaries and organizes them into a tree
    based on the replyto field. Messages with replyto=None become root nodes,
    and others are attached as children to their parent messages.
    
    Args:
        rows (list): List of message dictionaries, each containing:
            - mid: message ID
            - replyto: ID of parent message (None for root messages)
            - sender: user ID of sender
            - content: message content
            - parentthread: thread ID
            - sent_at: timestamp
            - sender_name: name of sender
    
    Returns:
        list: List of root message nodes, each with a 'children' list containing nested replies
    """
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
@app.route('/dishdash/thread/<int:thid>', methods=['GET', 'POST'])
def view_thread(thid):
    """
    View a single thread with all its messages and handle reply submissions.
    
    GET: Displays the thread post and all messages in a nested tree structure.
         Messages are organized hierarchically based on reply relationships.
    
    POST: Creates a new message/reply in the thread. Requires content and
          optionally a replyto field to reply to a specific message.
    
    Args:
        thid (int): The thread ID to display
    
    Returns:
        render_template: Renders thread.html with thread data and nested messages
        redirect: Redirects back to thread view after posting reply, or to dishdash if thread not found
    """
    conn = dbi.connect()
    cur = dbi.dict_cursor(conn)

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        replyto_raw = request.form.get('replyto')
        replyto = int(replyto_raw) if replyto_raw else None

        if not content:
            flash('Message cannot be empty.')
            conn.close()
            return redirect(url_for('view_thread', thid=thid))

        sender_id = session.get('uid', 1)  # default to user 1 if not logged in

        # Insert message with current timestamp
        cur.execute(
            '''INSERT INTO messages (replyto, sender, content, parentthread, sent_at)
               VALUES (%s, %s, %s, %s, NOW())''',
            (replyto, sender_id, content, thid)
        )
        conn.commit()
        conn.close()
        flash('Reply posted!')
        return redirect(url_for('view_thread', thid=thid))

    # GET: load thread + post info
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

    messages = build_message_tree(rows)
    current_uid = session.get('uid')

    return render_template('thread.html',
                           thread=thread,
                           messages=messages,
                           current_uid=current_uid)

@app.route('/dishdash/thread/<int:thid>/delete_thread', methods=['POST'])
def delete_thread(thid):
    """
    Delete an entire thread and its associated post.
    
    Only allows deletion if the current logged-in user is the owner of the thread's post.
    Recursively deletes all messages in the thread before deleting the thread and post.
    
    Args:
        thid (int): The thread ID to delete
    
    Returns:
        redirect: Redirects to dishdash after deletion, or back to thread view with error message
    """
    dbi.conf('wfresh_db')
    conn = dbi.connect()
    cur = dbi.dict_cursor(conn)

    # Load thread and owner
    cur.execute(
        '''
        SELECT t.thid, p.postid, p.owner AS owner_id
        FROM threads t
        JOIN post p ON t.postid = p.postid
        WHERE t.thid = %s
        ''',
        (thid,)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        flash('Thread not found.')
        return redirect(url_for('dishdash'))

    current_uid = session.get('uid')
    if current_uid is None:
        conn.close()
        flash('You must be logged in to delete threads.')
        return redirect(url_for('view_thread', thid=thid))

    if int(row['owner_id']) != int(current_uid):
        conn.close()
        flash('You can only delete threads you created.')
        return redirect(url_for('view_thread', thid=thid))

    postid = row['postid']

    # Delete messages first
    cur.execute('SELECT mid FROM messages WHERE parentthread = %s', (thid,))
    msg_rows = cur.fetchall()
    for m in msg_rows:
        delete_message_recursive(cur, m['mid'])

    # Delete thread
    cur.execute('DELETE FROM threads WHERE thid = %s', (thid,))
    # Delete post
    cur.execute('DELETE FROM post WHERE postid = %s', (postid,))

    conn.commit()
    conn.close()

    flash('Thread deleted.')
    return redirect(url_for('dishdash'))

    
def delete_message_recursive(cur, mid):
    """
    Recursively delete a message and all of its descendant replies.
    
    Deletes messages in bottom-up order (children before parent) to handle
    the self-referential foreign key constraint (messages.replyto → messages.mid).
    
    Args:
        cur: Database cursor for executing queries
        mid (int): The message ID to delete along with all its children
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
@app.route('/dishdash/thread/<int:thid>/delete/<int:mid>', methods=['POST'])
def delete_message(thid, mid):
    """
    Delete a message and all its replies from a thread.
    
    Only allows deletion if the current logged-in user is the sender of the message.
    Verifies that the message belongs to the specified thread before deletion.
    Uses recursive deletion to remove all child messages.
    
    Args:
        thid (int): The thread ID containing the message
        mid (int): The message ID to delete
    
    Returns:
        redirect: Redirects back to thread view with success or error message
    """
    conn = dbi.connect()
    cur = dbi.dict_cursor(conn)

    cur.execute(
        'SELECT parentthread, sender FROM messages WHERE mid = %s',
        (mid,)
    )
    row = cur.fetchone()

    if not row:
        flash('Message not found.')
        conn.close()
        return redirect(url_for('view_thread', thid=thid))

    if int(row['parentthread']) != int(thid):
        flash('Message does not belong to this thread.')
        conn.close()
        return redirect(url_for('view_thread', thid=thid))

    current_uid = session.get('uid')
    if current_uid is None:
        flash('You must be logged in to delete messages.')
        conn.close()
        return redirect(url_for('view_thread', thid=thid))

    if int(row['sender']) != int(current_uid):
        flash('You can only delete your own messages.')
        conn.close()
        return redirect(url_for('view_thread', thid=thid))

    # All checks passed → delete recursively
    delete_message_recursive(cur, mid)
    conn.commit()

    flash('Message and its replies have been deleted.')
    return redirect(url_for('view_thread', thid=thid))



@app.route('/dish/<did>', methods=['GET', 'POST'])
def get_dish(did):
    """
    Display dish details page and handle comment/picture submissions.
    
    GET: Displays dish information, all comments, and all pictures for the dish.
         Shows forms for adding new comments and uploading pictures.
    
    POST: Handles form submissions for:
          - Adding comments (with rating type: yum/yuck)
          - Uploading pictures
          - Both comment and picture can be submitted together
    
    Args:
        did (str): The dish ID to display
    
    Returns:
        render_template: Renders dish.html with dish data, comments, and pictures
        redirect: Redirects back to dish page after POST, or to index if dish not found
    """
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

@app.route('/dish/<did>/delete_pic/<int:pid>', methods=['POST'])
def delete_dish_pic(did, pid):
    """
    Delete a picture from a dish's photo gallery.
    
    Removes the picture entry from the dish_picture table and deletes the
    actual file from the filesystem if no other references exist.
    
    Args:
        did (str): The dish ID
        pid (int): The picture ID to delete
    
    Returns:
        redirect: Redirects back to dish page with success or error message
    """
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

@app.route('/dish/<did>/delete_comment/<int:commentid>', methods=['POST'])
def delete_comment(did, commentid):
    """
    Delete a comment from a dish's comment section.
    
    Verifies that the comment exists and belongs to the specified dish,
    then removes it from the comments table.
    
    Args:
        did (str): The dish ID
        commentid (int): The comment ID to delete
    
    Returns:
        redirect: Redirects back to dish page with success or error message
    """
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
