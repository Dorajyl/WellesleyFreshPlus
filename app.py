# copied 
from flask import (Flask, render_template, make_response, url_for, request,
                   redirect, flash, session, send_from_directory, jsonify)
from werkzeug.utils import secure_filename
app = Flask(__name__)

import secrets
import cs304dbi as dbi
import requests
from datetime import date, datetime, timedelta
import helper

# we need a secret_key to use flash() and sessions
app.secret_key = secrets.token_hex()

# configure DBI

# For Lookup, use 'wmdb'
# For CRUD and Ajax, use your personal db
# For project work, use your team db

print(dbi.conf('wfresh_db'))

# This gets us better error messages for certain common request errors
app.config['TRAP_BAD_REQUEST_ERRORS'] = True

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
    now = datetime.now()
    meal_order = ["Breakfast", "Lunch", "Dinner"] # helper.get_meal_order(now) # reorder meals so current meal(dinner/lunch..) is first

    days = []
    for offset in range(7):
        d = today + timedelta(days=offset)
        label = "Today" if offset == 0 else d.strftime("%A %b %-d")

        # menus[meal][hall_name] = list of dishes
        menus = {}
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
    flash('this is a flashed message')
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
        
        # Validate required fields
        if not comment_text:
            flash('Comment cannot be empty')
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
            
            # Insert comment
            cur.execute('''INSERT INTO comments (owner, type, comment, dish)
                           VALUES (%s, %s, %s, %s)''',
                        (owner_id, comment_type, comment_text, did))
            conn.commit()
            flash('Comment added successfully!')
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
    
    return render_template('dish.html', dish=dish, comments=comments)

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
