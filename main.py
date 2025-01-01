from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm,RegisterForm,Login_user,CommentForm
import os



app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_KEY")

ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URL",'sqlite:///posts.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
# CONFIGURE TABLES

# TODO: Create a User table for all your registered users.
class User(UserMixin,db.Model):
    __tablename__ = "users"
    id:Mapped[int] = mapped_column(Integer,primary_key=True)
    name:Mapped[str] = mapped_column(String(250))
    password:Mapped[str] = mapped_column(String(250))
    email:Mapped[str] = mapped_column(String(250),unique=True)
    posts:Mapped["BlogPost"] = relationship(back_populates="author")
    comments:Mapped["Comment"] = relationship(back_populates="comment_author")








class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id:Mapped[int] =mapped_column(Integer,db.ForeignKey("users.id"))
    author:Mapped["User"] =relationship(back_populates="posts")
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    comments:Mapped[list["Comment"]] = relationship("Comment",back_populates="parent_post",lazy="select")

class Comment(db.Model):
    __tablename__ = "comments"
    id:Mapped[int] = mapped_column(Integer,primary_key=True)
    author_id:Mapped[int] = mapped_column(Integer,db.ForeignKey("users.id"))
    posts_id:Mapped[int] = mapped_column(Integer,db.ForeignKey("blog_posts.id"))
    parent_post:Mapped["BlogPost"]=relationship(back_populates="comments")
    comment_author :Mapped["User"]= relationship(back_populates="comments")
    text:Mapped[str] = mapped_column(Text,nullable=False)


gravatar = Gravatar(app,
                    size=100,
                    rating="g",
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

with app.app_context():
    db.create_all()
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User,user_id)
def only_admin(f):
    @wraps(f)
    def check_is_admin(*args,**kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args,**kwargs)
    return check_is_admin
def only_commenter(function):
    @wraps(function)
    def check(*args,**kwargs):
        user_unlisted = db.session.execute(db.select(Comment).where(Comment.author_id == current_user.id))
        user = user_unlisted.scalar()
        if not current_user.is_authenticated or current_user.id != user.author_id:
            return abort(403)
        return function(*args,**kwargs)
    return check
# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register',methods=["GET","POST"])
def register():
    register_form = RegisterForm()
    password = register_form.password.data
    if register_form.validate_on_submit():


          result = db.session.execute(db.select(User).where(User.email == register_form.email.data))
          user = result.scalar()
          if user:
              flash("your email already exists ,you better try to log in!")
              return  redirect(url_for("login"))

          hass_password = generate_password_hash(password,method="pbkdf2:sha256",salt_length=6)
          new_user = User(
                          email=register_form.email.data,
                          name=register_form.name.data,
                          password=hass_password,
                         )
          db.session.add(new_user)
          db.session.commit()
          login_user(new_user)
          return redirect(url_for("get_all_posts"))

    return render_template("register.html",form=register_form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login',methods=["GET","POST"])
def login():
    forms = Login_user()
    if forms.validate_on_submit():
        email = forms.email.data
        password = forms.password.data
        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()
        if not user:
            flash("incorrect email,try again!")
            return redirect(url_for("login"))

        elif not  check_password_hash(user.password,password):
            flash("incorrect password,try again!")
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))
    return render_template("login.html",form=forms)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>",methods=["GET","POST"])
def show_post(post_id):
    comment_form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if comment_form.validate_on_submit():
        if not  current_user.is_authenticated:
            flash("you need to log in or register to comment.")
            return redirect(url_for("login"))
        new_comment=Comment(
            text=comment_form.comment.data,
            author_id=current_user.id,
            posts_id=requested_post.id,

        )
        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post,form = comment_form,current_user=current_user)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@only_admin
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@only_admin
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@only_admin
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

@app.route("/delete/comment/<int:comment_id>/<int:post_id>")
@only_commenter
def delete_comment(post_id,comment_id):
    post_to_delete = db.get_or_404(Comment,comment_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('show_post',post_id=post_id))
@app.route("/about")
def about():
    return render_template("about.html",current_user=current_user )


@app.route("/contact")
def contact():
    return render_template("contact.html",current_user=current_user)


if __name__ == "__main__":
    app.run(debug=False)
