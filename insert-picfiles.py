'''Populates the picfile table from files in the 'uploads' directory.
'''

import os
import cs304dbi as dbi

def do_files(dirname, conn, func):
    '''iterates over all files in the given directory (e.g. 'uploads'),
invoking function on conn, the full pathname, the filename and the
digits before the dot (e.g. 123.jpq).

    '''
    for name in os.listdir(dirname):
        path = os.path.join(dirname, name)
        if os.path.isfile(path):
            # note that we are reading a *binary* file not text
            with open(path,'rb') as f:
                print('{} of size {}'
                      .format(path,os.fstat(f.fileno()).st_size))
            nm,ext = name.split('.')
            if nm.isdigit():
                func(conn, path, name, nm)
    
def insert_picfile(conn, path, name, nm):
    '''Insert name into the picfile table under key nm.'''
    curs = dbi.cursor(conn)
    try:
        curs.execute('''insert into picfile(nm,filename) values (%s,%s)
                        on duplicate key update filename = %s''',
                     [nm,name,name])
        conn.commit()
    except Exception as err:
        print('Exception on insert of {}: {}'.format(name, repr(err)))

if __name__ == '__main__':
    dbi.cache_cnf()
    conn = dbi.connect()
    do_files('uploads', conn, insert_picfile)
