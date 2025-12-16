"""
app.py

Flask application entrypoint for WFresh.

Responsibilities:
- Define routes and render templates
- Enforce authentication (uid in session) for all mutating actions (POST deletes/creates/uploads)
- Delegate database work and non-route logic to wfresh_helper.py
"""

from flask import (
    Flask, render_template, url_for, request,
    redirect, flash, session, jsonify
)
from werkzeug.utils import secure_filename
import os
import secrets
import cs304login as auth
import wfresh_helper

# -----------------------------------------------------------------------------
# Flask app setup
# -----------------------------------------------------------------------------
app = Flask(__name__)

# Secret key enables sessions + flash messages.
app.secret_key = secrets.token_hex()

# Better error messages for certain common request errors.
app.config['TRAP_BAD_REQUEST_ERRORS'] = True

# -----------------------------------------------------------------------------
# Upload configuration (for dish pictures)
# -----------------------------------------------------------------------------
# Save images into static/uploads/
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

# Limit uploads to 5MB
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Ensure the upload folder exists at runtime.
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# -----------------------------------------------------------------------------
# Auth utilities
# -----------------------------------------------------------------------------
def current_uid():
    """
    Return the current user's uid from the session, or None if not logged in.
    """
    return session.get('uid', None)


def require_login():
    """
    Enforce that a user is logged in before performing an action that mutates state.

    If not logged in:
      - For normal routes, redirect to about page with a flash message.
      - For AJAX, return a JSON error with 401.

    Returns:
        uid (int/str) if logged in,
        otherwise a Flask response (redirect/json) that should be returned immediately.
    """
    uid = current_uid()
    if uid is None:
        flash("Please log in to do that.")
        return redirect(url_for('about'))
    return uid


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route('/')
def about():
    """
    About page.
    Displays info about the app and offers login/join forms.
    """
    return render_template('about.html', page_title='About Us')


@app.route('/join/', methods=["POST"])
def join():
    """
    User registration.

    Reads username + password1/password2.
    - If passwords mismatch -> flash error.
    - Otherwise create new user via cs304login, store uid in session.
    """
    username = request.form.get('username')
    passwd1 = request.form.get('password1')
    passwd2 = request.form.get('password2')

    if passwd1 != passwd2:
        flash('passwords do not match')
        return redirect(url_for('about'))

    # cs304login expects a connection object.
    conn = wfresh_helper.db_connect(dict_cursor=False)
    (uid, is_dup, other_err) = auth.insert_user(conn, username, passwd1)
    conn.close()

    if other_err:
        raise other_err
    if is_dup:
        flash('Sorry; that username is taken')
        return redirect(url_for('about'))

    # Successful registration: store session variables.
    flash(f'FYI, you were issued UID {uid}')
    session['username'] = username
    session['uid'] = uid
    session['logged_in'] = True
    return redirect(url_for('about'))


@app.route('/login/', methods=["POST"])
def login():
    """
    User login.

    Reads username + password.
    - If invalid -> flash error.
    - If valid -> store uid/username in session.
    """
    username = request.form.get('username')
    passwd = request.form.get('password')

    conn = wfresh_helper.db_connect(dict_cursor=False)
    (ok, uid) = auth.login_user(conn, username, passwd)
    conn.close()

    if not ok:
        flash('login incorrect, please try again or join')
        return redirect(url_for('about'))

    flash('successfully logged in as ' + username)
    session['username'] = username
    session['uid'] = uid
    session['logged_in'] = True
    return redirect(url_for('about'))


@app.route('/logout/')
def logout():
    """
    User logout.

    Clears session keys if present.
    """
    if 'username' in session:
        session.pop('username', None)
        session.pop('uid', None)
        session.pop('logged_in', None)
        flash('You are logged out')
        return redirect(url_for('about'))
    else:
        flash('you are not logged in. Please login or join')
        return redirect(url_for('about'))


@app.route('/home/', methods=['GET', 'POST'])
def index():
    """
    Home page.

    GET:
      - Show 7-day dining hall menus (cached in wfresh_helper.py)
      - Show most recent feast notifications (db)

    POST:
      - Create a new Wellesley Feast notification (requires login)
      - Implements POST-Redirect-GET (redirect back to /home/)
    """
    # -------------------------
    # POST: Feast submission
    # -------------------------
    if request.method == 'POST':
        uid_or_resp = require_login()
        if not isinstance(uid_or_resp, (int, str)):
            return uid_or_resp
        uid = uid_or_resp

        free_food = request.form.get('free_food', '').strip()
        location = request.form.get('location', '').strip()
        time_text = request.form.get('time_text', '').strip()

        # Basic validation
        if not free_food or not location or not time_text:
            flash('Please fill out food name, location, and time for Wellesley Feast.')
            return redirect(url_for('index'))

        # Insert into DB (wfresh_helper handles SQL + commit + close)
        wfresh_helper.insert_feast_notification(
            owner_uid=uid,
            time_text=time_text,
            location=location,
            description=free_food
        )

        flash(f'Feast: {free_food}\nWhere: {location}\nWhen: {time_text}')
        return redirect(url_for('index'))

    # -------------------------
    # GET: Menu + feast display
    # -------------------------
    today = wfresh_helper.date.today()

    # You can also use wfresh_helper.get_meal_order(datetime.now()) if you want dynamic ordering.
    meal_order = ["Breakfast", "Lunch", "Dinner"]

    # Week menu uses caching in wfresh_helper.py
    week_menu = wfresh_helper.fetch_week_menu(today)

    # Build "days" structure the template expects
    days = []
    for offset in range(7):
        d = today + wfresh_helper.timedelta(days=offset)
        label = "Today" if offset == 0 else d.strftime("%A %b %-d")
        date_key = d.isoformat()

        menus = week_menu.get(date_key, {})
        if not menus:
            # Fallback fetch (rare / defensive)
            menus = {}
            for meal in wfresh_helper.MEALS:
                menus[meal] = {}
                for dhall_id, info in wfresh_helper.DINING_HALLS.items():
                    dishes = wfresh_helper.fetch_menu_for(d, dhall_id, meal)
                    if dishes:
                        menus[meal][info["name"]] = dishes

        days.append({"date": d, "label": label, "menus": menus})

    feast_events = wfresh_helper.get_recent_feast_events(limit=3)

    return render_template(
        "main.html",
        days=days,
        meal_order=meal_order,
        feast_events=feast_events,
        page_title='Home'
    )


@app.route('/dishdash/', methods=['GET', 'POST'])
def dishdash():
    """
    DishDash forum landing page.

    GET:
      - List threads (most recent first)

    POST:
      - Create a new thread (requires login)
    """
    if request.method == 'POST':
        uid_or_resp = require_login()
        if not isinstance(uid_or_resp, (int, str)):
            return uid_or_resp
        uid = uid_or_resp

        description = request.form.get('description', '').strip()
        if not description:
            flash('Please write something for your thread.')
            return redirect(url_for('dishdash'))

        thid = wfresh_helper.create_thread(owner_uid=uid, description=description)
        flash('Thread created!')
        return redirect(url_for('view_thread', thid=thid))

    threads = wfresh_helper.list_threads()
    return render_template(
        'dishdash.html',
        page_title='DishDash Forum',
        threads=threads,
        current_uid=current_uid()
    )


@app.route('/dishdash/thread/<int:thid>', methods=['GET', 'POST'])
def view_thread(thid):
    """
    View a single thread.

    GET:
      - Load thread info (post text + owner)
      - Load all messages and build nested message tree for rendering

    POST:
      - Add a new message reply (requires login)
    """
    if request.method == 'POST':
        uid_or_resp = require_login()
        if not isinstance(uid_or_resp, (int, str)):
            return uid_or_resp
        uid = uid_or_resp

        content = request.form.get('content', '').strip()
        replyto_raw = request.form.get('replyto')
        replyto = int(replyto_raw) if replyto_raw else None

        if not content:
            flash('Message cannot be empty.')
            return redirect(url_for('view_thread', thid=thid))

        wfresh_helper.insert_message(sender_uid=uid, thid=thid, content=content, replyto=replyto)
        flash('Reply posted!')
        return redirect(url_for('view_thread', thid=thid))

    thread = wfresh_helper.get_thread(thid)
    if not thread:
        flash('Thread not found.')
        return redirect(url_for('dishdash'))

    rows = wfresh_helper.get_thread_messages(thid)
    messages = wfresh_helper.build_message_tree(rows)

    return render_template(
        'thread.html',
        thread=thread,
        messages=messages,
        current_uid=current_uid()
    )


@app.route('/dishdash/thread/<int:thid>/delete_thread', methods=['POST'])
def delete_thread(thid):
    """
    Delete an entire thread (requires login).

    Authorization:
      - Only the owner of the thread (post.owner) can delete.
    """
    uid_or_resp = require_login()
    if not isinstance(uid_or_resp, (int, str)):
        return uid_or_resp
    uid = uid_or_resp

    ok, msg = wfresh_helper.delete_thread(owner_uid=uid, thid=thid)
    flash(msg)

    if ok:
        return redirect(url_for('dishdash'))
    return redirect(url_for('view_thread', thid=thid))


@app.route('/dishdash/thread/<int:thid>/delete/<int:mid>', methods=['POST'])
def delete_message(thid, mid):
    """
    Delete a message (and all its descendant replies) (requires login).

    Authorization:
      - Only the sender of the message can delete it.
      - Message must belong to thread.
    """
    uid_or_resp = require_login()
    if not isinstance(uid_or_resp, (int, str)):
        return uid_or_resp
    uid = uid_or_resp

    ok, msg = wfresh_helper.delete_message(sender_uid=uid, thid=thid, mid=mid)
    flash(msg)
    return redirect(url_for('view_thread', thid=thid))


@app.route('/dish/<did>', methods=['GET', 'POST'])
def get_dish(did):
    """
    Dish detail page.

    GET:
      - Show dish info, comments, picture gallery.
    POST:
      - Add comment and/or upload picture (requires login).
      - Enforces: you must be logged in to post.
      - Stores picture owner uid in dish_picture.owner.
    """
    if request.method == 'POST':
        uid_or_resp = require_login()
        if not isinstance(uid_or_resp, (int, str)):
            return uid_or_resp
        uid = uid_or_resp

        comment_text = request.form.get('comment', '').strip()
        comment_type = request.form.get('type', 'yum')
        file = request.files.get('picture')

        # Require at least one of comment/picture
        if not comment_text and (not file or file.filename == ''):
            flash('You must enter a comment or upload a picture')
            return redirect(url_for('get_dish', did=did))

        # Save uploaded file (if present)
        filepath = None
        if file and file.filename:
            if not wfresh_helper.allowed_file(file.filename):
                flash('Unsupported file type. Please upload png/jpg/jpeg/gif.')
                return redirect(url_for('get_dish', did=did))

            filename = secure_filename(file.filename)
            filename = f"dish{did}_{filename}"
            fullpath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(fullpath)
            filepath = filename

        # Insert comment (owner = uid)
        if comment_text:
            wfresh_helper.add_dish_comment(
                uid=uid,
                did=did,
                comment_type=comment_type,
                comment_text=comment_text
            )

        # Insert picture record (owner = uid)
        if filepath:
            wfresh_helper.add_dish_picture(
                did=did,
                filename=filepath,
                owner_uid=uid
            )

        flash('Comment/Picture added successfully!')
        return redirect(url_for('get_dish', did=did))

    # GET
    dish = wfresh_helper.get_dish(did)
    if dish is None:
        flash(f'No dish with id {did} found')
        return redirect(url_for('index'))

    comments = wfresh_helper.get_dish_comments(did)
    dish_pics = wfresh_helper.get_dish_pics(did)

    return render_template(
        'dish.html',
        dish=dish,
        comments=comments,
        dish_pics=dish_pics,
        current_uid=current_uid()
    )


@app.route('/dish/<did>/delete_pic/<int:pid>', methods=['POST'])
def delete_dish_pic(did, pid):
    """
    Delete a dish picture (requires login).
    Enforces: only uploader (dish_picture.owner) can delete.
    """
    uid_or_resp = require_login()
    if not isinstance(uid_or_resp, (int, str)):
        return uid_or_resp
    uid = uid_or_resp

    ok, msg, filename_to_maybe_delete = wfresh_helper.delete_dish_picture(
        did=did,
        pid=pid,
        requester_uid=uid
    )

    # If DB says file no longer referenced, delete file from disk
    if ok and filename_to_maybe_delete:
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename_to_maybe_delete)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    flash(msg)
    return redirect(url_for('get_dish', did=did))


@app.route('/dish/<did>/delete_comment/<int:commentid>', methods=['POST'])
def delete_comment(did, commentid):
    """
    Delete a dish comment (requires login).
    Enforces: only comment owner can delete.
    """
    uid_or_resp = require_login()
    if not isinstance(uid_or_resp, (int, str)):
        return uid_or_resp
    uid = uid_or_resp

    ok, msg = wfresh_helper.delete_dish_comment(
        did=did,
        commentid=commentid,
        requester_uid=uid
    )

    flash(msg)
    return redirect(url_for('get_dish', did=did))



if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        assert port > 1024
    else:
        port = os.getuid()

    app.debug = True
    app.run('0.0.0.0', port)
