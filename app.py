from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import pytz
from markupsafe import escape
import os

app = Flask(__name__)

#############################################ひろき
#データベース構築
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:140286TakaHiro@localhost/site5db_3'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://site5user:140286TakaHiro@localhost/site5db_3'
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey('thread.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    time = db.Column(db.DateTime, default=datetime.utcnow)

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.String(12000), nullable=False)
    posts = db.relationship('Post', backref='thread', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nickname=db.Column(db.Text, nullable=False)
    password=db.Column(db.Text, nullable=False)
    posts = db.relationship('Post', backref='user', lazy=True)

with app.app_context():
    db.create_all()

#############################################
#ログイン設定
app.config['SECRET_KEY'] = 'hiroki-secret-key'
from flask_login import LoginManager
from flask_login import login_user
from flask_login import logout_user
from flask_login import login_required
from flask_login import current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import hashlib

limiter = Limiter(get_remote_address, app=app, default_limits=["30 per minute"])

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def hash_password(password):
    hash_object = hashlib.sha256()
    hash_object.update(password.encode('utf-8'))
    hashed_password = hash_object.hexdigest()
    return hashed_password

def get_nickname():
    if current_user.is_authenticated:
        nickname = current_user.nickname
    else:
        nickname = "ログインしていません"
    return nickname

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("30/minute") 
def login():
    nickname=get_nickname()
    if request.method == 'POST':
        #認証
        user = User.query.filter_by(nickname=request.form['nickname']).first()
        if user and user.password == hash_password(request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        else:
            good_or_bad="nicknameかpasswordが間違っています。"
    elif request.method == 'GET':
        good_or_bad="コメント追加やコメント削除にはログインが必要です"
    return render_template('login.html', good_or_bad=good_or_bad, nickname=nickname)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    nickname=get_nickname()
    if request.method == 'POST':
        # サインアップ
        user = User.query.filter_by(nickname=request.form['nickname']).first()
        if user:
            already_used_or_not='すでに使われているnicknameです'
        else:
            #Userテーブルへ
            nickname = request.form['nickname']
            hashed_password = hash_password(request.form['password'])
            new_user = User(nickname=nickname, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('home'))
    elif request.method == 'GET':
        already_used_or_not='他のサービスで使っているパスワードや名前などは絶対に使用しないでください。'
    return render_template('signup.html', already_used_or_not=already_used_or_not, nickname=nickname)

@app.route('/superuser', methods=['GET', 'POST'])
def superuser():
    user = User.query.filter_by(nickname="ShiroatoHiro").first()
    login_user(user)
    return redirect(url_for('home'))

#############################################
#補助の関数
def preprocess_user_input(input_string):
    processed_string = str(escape(input_string)).replace('\n', '<br>')
    #print(processed_string) #コンソールで表示するとなぜか最初の行が消えてしまう。
    return processed_string

def post_thread(comment, thread_id):
    current_time = datetime.utcnow()
    current_time_japan = current_time.astimezone(pytz.timezone('Asia/Tokyo'))
    comment=preprocess_user_input(comment)
    new_post = Post(content=comment, thread_id=thread_id, user_id=current_user.id, time=current_time_japan)
    db.session.add(new_post)
    db.session.commit()

#############################################
#メインの関数
@app.route('/')
def home():
    nickname=get_nickname()
    #自分だけnew_threadを作れる
    only_me_new_thread=False
    if current_user.is_authenticated and current_user.nickname=="ShiroatoHiro":
        #new_thread_url = url_for('new_thread')
        #only_me_new_thread=f'<a href="{new_thread_url}">New Thread</a>'
        only_me_new_thread = True
    #Threadテーブルから
    threads = Thread.query.all()
    return render_template('home.html', threads=threads, nickname=nickname, only_me_new_thread=only_me_new_thread)

@app.route('/thread/new', methods=['GET', 'POST'])
def new_thread():
    nickname=get_nickname()
    if current_user.is_authenticated and current_user.nickname=="ShiroatoHiro":
        if request.method == 'POST' and current_user.is_authenticated and current_user.nickname=="ShiroatoHiro":
            #Threadテーブルへ
            title = request.form['title']
            content = request.form['blog_content']
            new_thread = Thread(title=title, content=content)
            db.session.add(new_thread)
            db.session.commit()
            return redirect(url_for('home'))
        else:
            return render_template('new_thread.html', nickname=nickname)
    else:
        return "管理者のみがアクセスできる場所です"

@app.route('/thread/<int:thread_id>', methods=['GET', 'POST'])
def view_thread(thread_id):
    nickname=get_nickname()
    me_input_place=""
    massage_for_delete=""
    if "me_blog" in request.form:
        #blogのcontentの更新
        title = request.form['blog_title']
        content = request.form['me_blog']
        thread = Thread.query.get(thread_id)
        thread.title = title
        thread.content = content
        db.session.commit()
    elif "comment" in request.form:
        #ログインしているのか
        if current_user.is_authenticated:
            #Postテーブルへ
            comment = request.form['comment']
            post_thread(comment, thread_id)
        else:
            return redirect(url_for('login'))
    elif "delete_comment" in request.form:
        if current_user.is_authenticated:
            delete_id = request.form['delete_comment']
            post = Post.query.get(delete_id)  
            if post and current_user.id == post.user_id: 
                db.session.delete(post)  
                db.session.commit()
                massage_for_delete="コメントID="+str(delete_id)+"を削除しました"
            else:
                massage_for_delete="コメントIDが間違っています"
        else:
            return redirect(url_for('login'))

    #Threadテーブル、Postテーブルから
    thread = Thread.query.get(thread_id)
    posts = Post.query.filter_by(thread_id=thread_id)
    posts_with_nicknames = [(post, post.user.nickname) for post in posts]
    #編集前のブログと編集form
    blog_title_before=Thread.query.filter_by(id=thread_id).first().title
    me_blog_before=Thread.query.filter_by(id=thread_id).first().content
    if current_user.is_authenticated and current_user.nickname=="ShiroatoHiro":
        current_dir = os.path.dirname(os.path.realpath(__file__))
        me_input_txt_path = os.path.join(current_dir, 'me_input.txt')
        with open(me_input_txt_path, 'r') as file:
            me_input_file = file.read()
            me_input_place=me_input_file.format(blog_title_before, me_blog_before)
    return render_template('thread.html', thread=thread, posts_with_nicknames=posts_with_nicknames, nickname=nickname, me_input_place=me_input_place, me_blog_before=me_blog_before, massage_for_delete=massage_for_delete)
    
#############################################
#実行
if __name__ == '__main__':
    app.run(debug=True)


