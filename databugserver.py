import flask
from flask import request, url_for, redirect,session
import os.path
import psycopg2
import datetime
import time
import bcrypt
from contextlib import contextmanager
from contextlib import closing

app = flask.Flask(__name__)
app.secret_key = "test"
app.config.from_pyfile('settings.py')
if os.path.exists('localsettings.py'):
    app.config.from_pyfile('localsettings.py')

@contextmanager
def db_cursor():
    # Get the database connection from the configuration
    dbc = psycopg2.connect(**app.config['PG_ARGS'])
    try:
        cur = dbc.cursor()
        try:
            yield cur
        finally:
            cur.close()
    finally:
        dbc.close()


def db_connect():
    cxn = psycopg2.connect(**app.config['PG_ARGS'])
    return cxn


@app.route('/register',methods=['GET','POST'])
def register():
    registered = False
    if request.method == 'POST':
        user = {'username':request.form['username'],'name':request.form['name'],
            'email':request.form['usermail'],
            'password':request.form['pwd']}
        hash = bcrypt.hashpw(user.password.encode('UTF-8'), bcrypt.gensalt())
        with closing(db_connect()) as dbc:
            with dbc,dbc.cursor() as cur:
                cur.execute("insert into _user values (%s, %s, %s, %s)",
                            (user['username'],user['name'],user['email'],
                             hash.decode('UTF-8')))
        if registered:
            redirect(url_for('home_page'))
    return flask.render_template('register_page.html')


@app.route('/add_bug',methods =['GET','POST'])
def add_bug():
    with db_cursor() as cur:
        cur.execute ('''select bug_id from bug where bug_id = (select max(bug_id) from bug) ''')
        row = cur.fetchone()
        top = row[0]
        top += 1

    date = time.strftime("%m/%d/%Y")
    if request.method == 'POST':
        bug = {'bug_title':request.form['Bug Title'], 'assignee':request.form['Asigned To'], 'detail':request.form['Bug Description']}
        with closing(db_connect()) as dbc:
            with dbc,dbc.cursor() as cur:
                cur.execute("insert into bug (bug_id, date_created, creator, assignee, status, close_date, detail, bug_title) values (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (top, date, session['auth_user'],bug['assignee'],0,None,bug['detail'], bug['bug_title']))
                print("Bug added")
            redirect(url_for('profile'))

    return flask.render_template('add_bug.html')



@app.route('/login',methods=['GET','POST'])
def login():
    with db_cursor() as cur:
        error = None
        if request.method == 'POST':
            cur.execute('''
              Select password from _user where user_id = %s
              ''',(request.form['username'],))

            pwd = cur.fetchone()
            hash = bcrypt.hashpw(request.form['password'].encode('UTF-8'),
                                 pwd[0].encode('UTF-8'))
            if hash != pwd[0]:
                error = 'Invalid credentials, please try again.'
            else:
                session['logged_in'] = True
                session['auth_user'] = request.form['username']
                return redirect(url_for('profile'))
        return flask.render_template('login.html',error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in',None)
    return redirect(url_for('home_page'))


@app.route('/bug_list')
def bug_list():
    if 'logged_in' in flask.session:
        with db_cursor() as cur:
            cur.execute(''' Select bug_id,bug_title from bug order by bug_id;
                ''')
            bugs = []
            for id,title in cur:
                bugs.append({'id':id,'title':title})

    return flask.render_template('bug_list.html',bugs=bugs)


@app.route('/user_profile')
def profile():
    if 'logged_in' in flask.session:
        with db_cursor() as cur:
            cur.execute("Select name, user_id,email from _user where user_id = %s",(session['auth_user'],))
            row = cur.fetchone()
            name,uid,umail = row
            user = {'name':name,'uname':uid,'email':umail}
            bugs = []
            cur.execute("select bug_id,bug_title from user_bug"
                        " join bug using (bug_id) "
                        "where user_id = %s",(session['auth_user'],))
            for bid,title in cur:
                bugs.append({'bug_id':bid,'title':title})
        return flask.render_template('user_profile.html',user=user,bugs=bugs)


@app.route('/user_profile/<string:user_name>')
def profile2(user_name):
    if 'logged_in' in flask.session:
        with db_cursor() as cur:
            cur.execute("Select name, user_id,email from _user where name = %s",(user_name,))
            row = cur.fetchone()
            name,uid,umail = row
            user = {'name':name,'uname':uid,'email':umail}
            bugs = []
            cur.execute("select bug_id,bug_title from user_bug"
                        " join bug using (bug_id) "
                        "where user_id = %s",(session['auth_user'],))
            for bid,title in cur:
                bugs.append({'bug_id':bid,'title':title})
        return flask.render_template('user_profile.html',user=user,bugs=bugs)


@app.route('/indv_bug/<int:bid>')
def indiv_bug(bid):
    with db_cursor() as cur:
        cur.execute("Select bug_title, creator, detail, date_created, close_date, assignee"
                    " from bug where bug_id = %s", (bid,))
        row = cur.fetchone()
        bug_id,creat,details, date, close_date,assignee = row
        bug = {'title':bug_id,'author':creat,'open':date,'close':close_date,'text':details,
               'auser':assignee}

        return flask.render_template('indv_bug.html',bug=bug)



@app.route('/change_log')
def change_log():
    with db_cursor() as cur:
        cur.execute("SELECT bug_title, bug_id, date_of_view,  last_updated, date_closed, description, change_log.assignee"
                    " FROM change_log JOIN bug using (bug_id)")
        bugs = []
        for title, id,last_viewed,patch_date,date_closed,comment,assignee in cur:
            bugs.append({'title':title,'id':id,'last_viewed':last_viewed,'patch_date':patch_date,'comment':comment,
                         'close':date_closed,'user_close':assignee})

    return flask.render_template('change_log.html', bugs=bugs)


@app.route("/add_change_log",methods=['GET','POST'])
def add_change_log():
    if request.method == 'POST':
        i = datetime.datetime.now()
        change_log_index = '%d' % i.second
        change_log_added = False
        new_change_log = {'Title':request.form['Bug Title'],'Assignee':request.form['AsignedTo'],
            'Desc':request.form['Change Log Description']}
        with closing(db_connect()) as dbc:
            with dbc,dbc.cursor() as cur:
                cur.execute("insert into change_log values (%s, %s, %s, %s,%s, %s, %s)",
                            (change_log_index, new_change_log['Title'],i,None,i,new_change_log['Desc'],new_change_log['Assignee']))
                change_log_added = True
        if change_log_added:
            redirect(url_for('home_page'))
    return flask.render_template('add_change_log.html')


@app.route('/voting')
def votes():
    with db_cursor() as cur:
        bugs = []
        cur.execute(''' SELECT bug_title, count(votes) as rank,bug.bug_id as bid
                        FROM bug
                        LEFT OUTER JOIN votes USING (bug_id)
                        GROUP BY bug_title,date_created,bid
                        ORDER BY rank DESC
                        Limit 50''')
        for title,rank,id in cur:
            bugs.append({'id':id,'title':title,'total':rank})
    return flask.render_template('voting.html',bugs=bugs)

@app.route('/')
def home_page():
    return flask.render_template('home.html')




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5123)
