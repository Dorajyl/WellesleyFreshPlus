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

@app.route('/')
def index():
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

    return render_template(
        "main.html",
        days=days,
        meal_order=meal_order,
    )

@app.route('/about/')
def about():
    return render_template('about.html', page_title='About Us')

@app.route('/dishdash/')
def dishdash():
    flash('this is a flashed message')
    return render_template('dishdash.html', page_title='Dish Dash')

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
            # Get or create an anonymous user for comments without owner
            # First, try to find an "Anonymous" user
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
                    '''INSERT INTO comments (dish, owner, type, comment, filepath)
                       VALUES (%s, %s, %s, %s, %s)''',
                    (did, owner_id, comment_type, comment_text, filepath)
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
    cur.execute('''SELECT c.commentid, c.owner, c.type, c.comment, c.filepath,
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

    # clear comment.filepath that uses this filename
    cur.execute(
        'UPDATE comments SET filepath = NULL WHERE dish = %s AND filepath = %s',
        (did, filename)
    )
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

    # look up the comment and its filepath
    cur.execute(
        'SELECT filepath FROM comments WHERE commentid = %s AND dish = %s',
        (commentid, did)
    )
    row = cur.fetchone()
    if row is None:
        flash('Comment not found')
        return redirect(url_for('get_dish', did=did))

    filename = row[0]

    # delete the comment from comments table
    cur.execute('DELETE FROM comments WHERE commentid = %s', (commentid,))
    conn.commit()

    # if the comment had a filepath, check if we should delete the file
    if filename:
        # check if this filename is still referenced in dish_picture or other comments
        cur.execute(
            'SELECT COUNT(*) FROM dish_picture WHERE filename = %s',
            (filename,)
        )
        dish_pic_count = cur.fetchone()[0]
        
        cur.execute(
            'SELECT COUNT(*) FROM comments WHERE filepath = %s',
            (filename,)
        )
        comment_count = cur.fetchone()[0]

        # only delete file if no more db references
        if dish_pic_count == 0 and comment_count == 0:
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                os.remove(path)
            except FileNotFoundError:
                pass  # if it is already gone, ignore

    flash('Comment deleted.')
    return redirect(url_for('get_dish', did=did))

if __name__ == '__main__':
    import sys, os
    if len(sys.argv) > 1:
        # arg, if any, is the desired port number
        port = int(sys.argv[1])
        assert(port>1024)
    else:
        port = os.getuid()
    app.debug = True
    app.run('0.0.0.0',port)
