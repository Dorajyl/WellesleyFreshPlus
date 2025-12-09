import cs304dbi as dbi
import pymysql
import bcrypt

def insert_user(conn, name, password, verbose=False):
    '''inserts given name & password into the users table.  
Returns three values: the uid, whether there was a duplicate key error, 
and either false or an exception object.
    '''
    hashed = bcrypt.hashpw(password.encode('utf-8'),
                           bcrypt.gensalt())
    curs = dbi.cursor(conn)
    try: 
        curs.execute('''INSERT INTO users(name, hashed) 
                        VALUES(%s, %s)''',
                     [name, hashed.decode('utf-8')])
        conn.commit()
        curs.execute('select last_insert_id()')
        row = curs.fetchone()
        return (row[0], False, False)
    except pymysql.err.IntegrityError as err:
        details = err.args
        if verbose:
            print('error inserting user',details)
        if details[0] == pymysql.constants.ER.DUP_ENTRY:
            if verbose:
                print('duplicate key for name {}'.format(name))
            return (False, True, False)
        else:
            if verbose:
                print('some other error!')
            return (False, False, err)

def login_user(conn, name, password):
    '''tries to log the user in given name & password. 
Returns True if success and returns the uid as the second value.
Otherwise, False, False.'''
    curs = dbi.cursor(conn)
    curs.execute('''SELECT uid, hashed FROM users 
                    WHERE name = %s''',
                 [name])
    row = curs.fetchone()
    if row is None:
        # no such user
        return (False, False)
    uid, hashed = row
    hashed2_bytes = bcrypt.hashpw(password.encode('utf-8'),
                                  hashed.encode('utf-8'))
    hashed2 = hashed2_bytes.decode('utf-8')
    if hashed == hashed2:
        return (True, uid)
    else:
        # password incorrect
        return (False, False)

def delete_user(conn, name):
    curs = dbi.cursor(conn)
    curs.execute('''DELETE FROM users WHERE name = %s''',
                 [name])
    conn.commit()


